import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update

from ..classify import INBOUND, OUTBOUND, DIRECT_DEBIT, Tree, counterparty_for, norm_iban, recategorize
from ..db import get_db
from ..models import Alias, Category, Counterparty, OwnAccount, RecurringEntry, Transaction, TypeMapping
from ..recurring import materialize

router = APIRouter()


# --- Categories ---------------------------------------------------------------

@router.get("/categories")
def categories(db=Depends(get_db)):
    tree = Tree(db)
    return [dict(id=c.id, name=c.name, parent_id=c.parent_id, flow=tree.flow(c.id), depth=tree.depth(c.id),
                 path=tree.path(c.id)) for c in sorted(tree.cats.values(), key=lambda c: tree.path(c.id))]


class CategoryIn(BaseModel):
    name: str
    parent_id: int | None = None


@router.post("/categories")
def add_category(body: CategoryIn, db=Depends(get_db)):
    tree = Tree(db)
    if body.parent_id not in tree.cats:
        raise HTTPException(400, "A Category needs a parent")
    if tree.depth(body.parent_id) >= 2:
        raise HTTPException(400, "At most two levels below a Flow Type")
    if not body.name.strip():
        raise HTTPException(400, "Name required")
    c = Category(name=body.name.strip(), parent_id=body.parent_id)
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.patch("/categories/{cid}")
def rename_category(cid: int, body: CategoryIn, db=Depends(get_db)):
    c = db.get(Category, cid)
    if not c or c.parent_id is None:
        raise HTTPException(400, "Flow Type roots can't be renamed")
    c.name = body.name.strip() or c.name
    db.commit()
    return {"ok": True}


def _deletion(db, cid):
    tree = Tree(db)
    c = tree.cats.get(cid)
    if not c or c.parent_id is None:
        raise HTTPException(400, "Flow Type roots can't be deleted")
    sub = tree.subtree(cid)
    count = lambda col: db.scalar(select(func.count()).where(col.in_(sub)))
    return c, sub, dict(
        transactions=db.scalar(select(func.count()).select_from(Transaction).where(
            func.coalesce(Transaction.o_category_id, Transaction.category_id).in_(sub))),
        default_categories=count(Counterparty.default_category_id),
        subcategories=len(sub) - 1,
        moved_to=tree.path(c.parent_id) if tree.cats[c.parent_id].parent_id else "Uncategorized",
    )


@router.get("/categories/{cid}/impact")
def deletion_impact(cid: int, db=Depends(get_db)):
    return _deletion(db, cid)[2]


@router.delete("/categories/{cid}")
def delete_category(cid: int, db=Depends(get_db)):
    """Everything in the deleted subtree moves to the parent; a first-level parent is the root (= Uncategorized)."""
    c, sub, impact = _deletion(db, cid)
    to = c.parent_id
    is_root = db.get(Category, to).parent_id is None
    for model, col in ((Transaction, "category_id"), (Transaction, "o_category_id"), (TypeMapping, "category_id"),
                       (RecurringEntry, "category_id")):
        db.execute(update(model).where(getattr(model, col).in_(sub)).values({col: to}))
    db.execute(update(Counterparty).where(Counterparty.default_category_id.in_(sub))
               .values(default_category_id=None if is_root else to))
    for sid in reversed(sub):
        db.delete(db.get(Category, sid))
    db.flush()
    recategorize(db)
    db.commit()
    return impact


# --- Counterparties -------------------------------------------------------------

@router.get("/counterparties")
def counterparties(db=Depends(get_db)):
    tree = Tree(db)
    counts = dict(db.execute(select(func.coalesce(Transaction.o_counterparty_id, Transaction.counterparty_id), func.count())
                             .group_by(func.coalesce(Transaction.o_counterparty_id, Transaction.counterparty_id))).all())
    return [dict(id=c.id, name=c.name, default_category_id=c.default_category_id,
                 default_category=tree.path(c.default_category_id) if c.default_category_id else None,
                 aliases=sorted(a.raw_name for a in c.aliases), transactions=counts.get(c.id, 0))
            for c in db.scalars(select(Counterparty).order_by(func.lower(Counterparty.name)))]


class CounterpartyIn(BaseModel):
    name: str | None = None
    default_category_id: int | None = None


@router.patch("/counterparties/{cp_id}")
def edit_counterparty(cp_id: int, body: CounterpartyIn, db=Depends(get_db)):
    cp = db.get(Counterparty, cp_id)
    if not cp:
        raise HTTPException(404)
    f = body.model_dump(exclude_unset=True)
    if f.get("name"):
        cp.name = f["name"].strip()
    if "default_category_id" in f:
        cp.default_category_id = f["default_category_id"]
        recategorize(db)
    db.commit()
    return {"ok": True}


class MergeIn(BaseModel):
    keep_id: int
    drop_id: int
    default_category_id: int | None  # required choice, may be None (= no default)


@router.post("/counterparties/merge")
def merge(body: MergeIn, db=Depends(get_db)):
    keep, drop = db.get(Counterparty, body.keep_id), db.get(Counterparty, body.drop_id)
    if not keep or not drop or keep is drop:
        raise HTTPException(400, "Pick two different Counterparties")
    for model, col in ((Alias, "counterparty_id"), (Transaction, "counterparty_id"), (Transaction, "o_counterparty_id"),
                       (RecurringEntry, "counterparty_id")):
        db.execute(update(model).where(getattr(model, col) == drop.id).values({col: keep.id}))
    db.expire_all()
    db.get(Counterparty, body.keep_id).default_category_id = body.default_category_id
    db.delete(db.get(Counterparty, body.drop_id))
    db.flush()
    recategorize(db)
    db.commit()
    return {"ok": True}


class SplitIn(BaseModel):
    raw_name: str


@router.post("/counterparties/split")
def split(body: SplitIn, db=Depends(get_db)):
    """Move one Alias (and its Transactions) to a new Counterparty of its own."""
    alias = db.get(Alias, body.raw_name)
    if not alias:
        raise HTTPException(404, "Alias not found")
    if len(alias.counterparty.aliases) < 2:
        raise HTTPException(400, "This is the Counterparty's only Alias")
    old = alias.counterparty_id
    cp = Counterparty(name=body.raw_name)
    db.add(cp)
    db.flush()
    alias.counterparty_id = cp.id
    db.execute(update(Transaction).where(Transaction.counterparty_id == old, Transaction.raw_name == body.raw_name)
               .values(counterparty_id=cp.id))
    recategorize(db)
    db.commit()
    return {"id": cp.id}


# --- Own Accounts --------------------------------------------------------------

@router.get("/own-accounts")
def own_accounts(db=Depends(get_db)):
    return [dict(iban=a.iban, label=a.label, income_source=a.income_source) for a in db.scalars(select(OwnAccount))]


class AccountIn(BaseModel):
    label: str = ""
    income_source: bool = False


@router.put("/own-accounts/{iban}")
def put_account(iban: str, body: AccountIn, db=Depends(get_db)):
    iban = norm_iban(iban)
    if not iban or len(iban) < 15:
        raise HTTPException(400, "Not an IBAN")
    a = db.get(OwnAccount, iban) or OwnAccount(iban=iban)
    a.label, a.income_source = body.label, body.income_source
    db.add(a)
    db.flush()
    recategorize(db)
    db.commit()
    return {"ok": True}


@router.delete("/own-accounts/{iban}")
def delete_account(iban: str, db=Depends(get_db)):
    if a := db.get(OwnAccount, norm_iban(iban)):
        db.delete(a)
        db.flush()
        recategorize(db)
        db.commit()
    return {"ok": True}


# --- Trade Republic type mappings ----------------------------------------------

@router.get("/type-mappings")
def type_mappings(db=Depends(get_db)):
    tree = Tree(db)
    mapped = {m.tr_type: m.category_id for m in db.scalars(select(TypeMapping))}
    unknown = db.execute(select(Transaction.tr_type, func.count()).where(
        Transaction.tx_id.is_not(None), Transaction.category_id.is_(None)).group_by(Transaction.tr_type)).all()
    return dict(
        mappings=[dict(tr_type=t, category_id=c, category=tree.path(c)) for t, c in sorted(mapped.items())],
        unknown=[dict(tr_type=t, count=n) for t, n in unknown if t not in mapped],
        builtin=sorted(INBOUND | OUTBOUND | DIRECT_DEBIT),
    )


class MappingIn(BaseModel):
    category_id: int


@router.put("/type-mappings/{tr_type}")
def put_mapping(tr_type: str, body: MappingIn, db=Depends(get_db)):
    if tr_type in INBOUND | OUTBOUND | DIRECT_DEBIT:
        raise HTTPException(400, "Transfer types are resolved by IBAN (Own Accounts)")
    if body.category_id not in Tree(db).cats:
        raise HTTPException(400, "Unknown Category")
    db.merge(TypeMapping(tr_type=tr_type, category_id=body.category_id))
    db.flush()
    recategorize(db)  # retroactive
    db.commit()
    return {"ok": True}


# --- Recurring Entries -----------------------------------------------------------

def recurring_out(r, tree, db):
    return dict(id=r.id, amount=r.amount, counterparty=db.get(Counterparty, r.counterparty_id).name,
                category_id=r.category_id, category=tree.path(r.category_id), interval=r.interval,
                start=r.start, end=r.end)


@router.get("/recurring")
def recurring(db=Depends(get_db)):
    tree = Tree(db)
    return [recurring_out(r, tree, db) for r in db.scalars(select(RecurringEntry))]


class RecurringIn(BaseModel):
    amount: float | None = None
    counterparty: str | None = None
    category_id: int | None = None
    interval: Literal["monthly", "quarterly", "yearly"] | None = None
    start: dt.date | None = None
    end: dt.date | None = None


@router.post("/recurring")
def add_recurring(body: RecurringIn, db=Depends(get_db)):
    if None in (body.amount, body.category_id, body.interval, body.start) or not body.counterparty:
        raise HTTPException(400, "amount, counterparty, category, interval and start are required")
    if body.category_id not in Tree(db).cats:
        raise HTTPException(400, "Unknown Category")
    r = RecurringEntry(amount=body.amount, counterparty_id=counterparty_for(db, body.counterparty),
                       category_id=body.category_id, interval=body.interval, start=body.start, end=body.end)
    db.add(r)
    db.commit()
    materialize(db)
    return {"id": r.id}


@router.patch("/recurring/{rid}")
def edit_recurring(rid: int, body: RecurringIn, db=Depends(get_db)):
    """Changes only the rule, so occurrences already generated keep their values."""
    r = db.get(RecurringEntry, rid)
    if not r:
        raise HTTPException(404)
    f = body.model_dump(exclude_unset=True)
    if f.get("amount") is not None: r.amount = f["amount"]
    if f.get("category_id") is not None: r.category_id = f["category_id"]
    if f.get("counterparty"): r.counterparty_id = counterparty_for(db, f["counterparty"])
    if "end" in f:
        r.end = f["end"]
        if r.end:  # ending removes occurrences after the end
            db.execute(Transaction.__table__.delete().where(Transaction.recurring_id == rid, Transaction.date > r.end))
    db.commit()
    materialize(db)
    return {"ok": True}


@router.delete("/recurring/{rid}")
def delete_recurring(rid: int, db=Depends(get_db)):
    """Deletes the rule; generated Manual Transactions stay as plain Manual Transactions."""
    db.execute(update(Transaction).where(Transaction.recurring_id == rid).values(recurring_id=None))
    if r := db.get(RecurringEntry, rid):
        db.delete(r)
    db.commit()
    return {"ok": True}
