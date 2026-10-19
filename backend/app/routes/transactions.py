import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from ..analytics import analytics
from ..classify import Tree, counterparty_for, recategorize
from ..db import get_db
from ..importer import import_csv
from ..models import Counterparty, Transaction

router = APIRouter()


def out(t, tree, names):
    cid = t.eff_category_id
    return dict(
        id=t.id, date=t.eff_date, amount=t.eff_amount, counterparty_id=t.eff_counterparty_id,
        counterparty=names.get(t.eff_counterparty_id, t.raw_name), category_id=cid, category=tree.path(cid),
        flow=tree.flow(cid), uncategorized=tree.uncategorized(cid), description=t.description, tr_type=t.tr_type,
        manual=t.manual, recurring_id=t.recurring_id, overridden=t.overridden, excluded=t.excluded,
        original=None if t.manual else dict(date=t.date, amount=t.amount, counterparty=t.raw_name,
                                            category=tree.path(t.category_id)),
    )


def get_tx(db, tx_id):
    t = db.get(Transaction, tx_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    return t


def check_category(tree, cid):
    if cid is not None and cid not in tree.cats:
        raise HTTPException(400, "Unknown Category")


@router.post("/import/transactions")
async def upload_csv(file: UploadFile, db=Depends(get_db)):
    try:
        return import_csv(db, await file.read())
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/transactions")
def list_transactions(start: dt.date | None = None, end: dt.date | None = None, flow: str | None = None,
                      category_id: int | None = None, counterparty_id: int | None = None, q: str | None = None,
                      uncategorized: bool = False, excluded: bool = False, db=Depends(get_db)):
    # shortcut: filters in Python over all rows; move into SQL if the table grows past ~50k rows
    tree = Tree(db)
    names = dict(db.execute(select(Counterparty.id, Counterparty.name)).all())
    sub = set(tree.subtree(category_id)) if category_id in tree.cats else None
    res = []
    for t in db.scalars(select(Transaction).where(Transaction.excluded.is_(excluded))):
        cid, d = t.eff_category_id, t.eff_date
        if (start and d < start) or (end and d > end) or (flow and tree.flow(cid) != flow):
            continue
        if (sub and cid not in sub) or (counterparty_id and t.eff_counterparty_id != counterparty_id):
            continue
        if uncategorized and not tree.uncategorized(cid):
            continue
        if q and q.lower() not in f"{t.raw_name} {t.description} {names.get(t.eff_counterparty_id, '')}".lower():
            continue
        res.append(out(t, tree, names))
    return sorted(res, key=lambda r: (r["date"], r["id"]), reverse=True)


class TxIn(BaseModel):
    date: dt.date | None = None
    amount: float | None = None
    counterparty: str | None = None
    category_id: int | None = None
    description: str | None = None


@router.post("/transactions")
def create_manual(body: TxIn, db=Depends(get_db)):
    if body.date is None or body.amount is None or not body.counterparty or body.category_id is None:
        raise HTTPException(400, "date, amount, counterparty and category are required")
    check_category(Tree(db), body.category_id)
    t = Transaction(date=body.date, amount=body.amount, raw_name=body.counterparty, description=body.description or "",
                    counterparty_id=counterparty_for(db, body.counterparty), category_id=body.category_id)
    db.add(t)
    db.commit()
    return {"id": t.id}


@router.patch("/transactions/{tx_id}")
def edit(tx_id: int, body: TxIn, db=Depends(get_db)):
    """Manual Transactions are edited directly; imported ones get an Override."""
    t = get_tx(db, tx_id)
    f = body.model_dump(exclude_unset=True)
    check_category(Tree(db), f.get("category_id"))
    cp = counterparty_for(db, f["counterparty"]) if f.get("counterparty") else None
    if t.manual:
        for k in ("date", "amount", "category_id", "description"):
            if f.get(k) is not None:
                setattr(t, k, f[k])
        if cp:
            t.counterparty_id, t.raw_name = cp, f["counterparty"]
    else:
        if "date" in f: t.o_date = f["date"]
        if "amount" in f: t.o_amount = f["amount"]
        if "category_id" in f: t.o_category_id = f["category_id"]
        if cp: t.o_counterparty_id = cp
        recategorize(db)  # a new Counterparty may bring a different Default Category
    db.commit()
    return {"ok": True}


class CategoryChoice(BaseModel):
    category_id: int
    scope: Literal["counterparty", "this"]


@router.put("/transactions/{tx_id}/category")
def set_category(tx_id: int, body: CategoryChoice, db=Depends(get_db)):
    """'counterparty' sets the Default Category (applies to all non-overridden history); 'this' is an Override."""
    t = get_tx(db, tx_id)
    check_category(Tree(db), body.category_id)
    if t.manual:
        t.category_id = body.category_id
    elif body.scope == "this":
        t.o_category_id = body.category_id
    if body.scope == "counterparty" and t.eff_counterparty_id:
        db.get(Counterparty, t.eff_counterparty_id).default_category_id = body.category_id
        if not t.manual:
            t.o_category_id = None
            recategorize(db)
            if t.category_id != body.category_id:
                db.rollback()
                raise HTTPException(400, "That Category can't be this Counterparty's default here (different Flow Type, "
                                         "or the Trade Republic type decides it). Apply it to this Transaction only.")
    db.commit()
    return {"ok": True}


@router.delete("/transactions/{tx_id}/override")
def reset_override(tx_id: int, db=Depends(get_db)):
    t = get_tx(db, tx_id)
    t.o_amount = t.o_date = t.o_counterparty_id = t.o_category_id = None
    db.commit()
    return {"ok": True}


class ExcludeIn(BaseModel):
    excluded: bool


@router.post("/transactions/{tx_id}/exclude")
def exclude(tx_id: int, body: ExcludeIn, db=Depends(get_db)):
    t = get_tx(db, tx_id)
    if t.manual and not t.recurring_id:
        raise HTTPException(400, "Manual Transactions are deleted, not Excluded")
    t.excluded = body.excluded
    db.commit()
    return {"ok": True}


@router.delete("/transactions/{tx_id}")
def delete_manual(tx_id: int, db=Depends(get_db)):
    t = get_tx(db, tx_id)
    if not t.manual:
        raise HTTPException(400, "Imported Transactions can only be Excluded")
    if t.recurring_id:
        t.excluded = True  # deleting would let the Recurring Entry regenerate it
    else:
        db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/meta")
def meta(db=Depends(get_db)):
    """Date of the latest Transaction, so the UI can open on a period that has data."""
    return {"latest": max((t.eff_date for t in db.scalars(select(Transaction).where(Transaction.excluded.is_(False)))), default=None)}


@router.get("/analytics")
def get_analytics(start: dt.date, end: dt.date, db=Depends(get_db)):
    return analytics(db, start, end)
