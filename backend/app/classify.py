import re

from sqlalchemy import func, select

from .models import Alias, Category, Counterparty, OwnAccount, Transaction, TypeMapping
from .seed import MCC

INBOUND = {"TRANSFER_INBOUND", "TRANSFER_INSTANT_INBOUND"}
OUTBOUND = {"TRANSFER_INSTANT_OUTBOUND"}
DIRECT_DEBIT = {"TRANSFER_DIRECT_DEBIT_INBOUND"}


class Tree:
    """The Category hierarchy loaded once; Flow Type = name of a Category's root (ADR 0001)."""

    def __init__(self, db):
        self.cats = {c.id: c for c in db.scalars(select(Category))}
        self.root = {c.name: c.id for c in self.cats.values() if c.parent_id is None}

    def root_of(self, cid):
        while self.cats[cid].parent_id:
            cid = self.cats[cid].parent_id
        return cid

    def flow(self, cid):
        return None if cid is None else self.cats[self.root_of(cid)].name

    def depth(self, cid):
        return 0 if self.cats[cid].parent_id is None else 1 + self.depth(self.cats[cid].parent_id)

    def children(self, cid):
        return [c.id for c in self.cats.values() if c.parent_id == cid]

    def subtree(self, cid):
        return [cid] + [d for c in self.children(cid) for d in self.subtree(c)]

    def path(self, cid):
        if cid is None:
            return "Uncategorized"
        names = []
        while cid:
            names.append(self.cats[cid].name)
            cid = self.cats[cid].parent_id
        return " › ".join(reversed(names))

    def find(self, root_name, names):
        """Deepest existing Category along a name path below a root, or None."""
        found, cur = None, self.root[root_name]
        for name in names:
            cur = next((c.id for c in self.cats.values() if c.parent_id == cur and c.name == name), None)
            if cur is None:
                break
            found = cur
        return found

    def uncategorized(self, cid):
        return cid is None or (self.cats[cid].parent_id is None and self.cats[cid].name != "Internal Transfer")


def normalize(raw):
    """Proposed Counterparty name for a raw Alias: drop branch ids and reference codes."""
    s = re.split(r"-?\s*\bFIL\.", raw, flags=re.I)[0]
    s = re.sub(r"\*\w*\d\w*$", "", s)  # "AMZN Mktp DE*1A2B3"; keeps "PAYPAL *SPOTIFY"
    toks = s.split()
    while len(toks) > 1 and re.search(r"\d", toks[-1]):
        toks.pop()
    return " ".join(toks).strip(" -.,") or raw.strip()


def norm_iban(iban):
    return re.sub(r"\s", "", iban or "").upper() or None


def counterparty_for(db, raw):
    """Counterparty id for a raw name, creating the Alias (and Counterparty) on first sight."""
    alias = db.get(Alias, raw)
    if alias:
        return alias.counterparty_id
    name = normalize(raw)
    cp = db.scalar(select(Counterparty).where(func.lower(Counterparty.name) == name.lower()))
    if not cp:
        cp = Counterparty(name=name)
        db.add(cp)
        db.flush()
    db.add(Alias(raw_name=raw, counterparty_id=cp.id))
    db.flush()
    return cp.id


def base_category(t, tree, mappings, accounts):
    """Flow Type root (or mapped Category) from the Trade Republic type and IBAN context; None = unknown type."""
    acct = accounts.get(norm_iban(t.iban))
    internal, income, expense = tree.root["Internal Transfer"], tree.root["Income"], tree.root["Expense"]
    if t.tr_type in INBOUND:
        return internal if acct and not acct.income_source else income
    if t.tr_type in OUTBOUND:
        return internal if acct else expense
    if t.tr_type in DIRECT_DEBIT:
        return internal if not t.iban or (acct and not acct.income_source) else income
    return mappings.get(t.tr_type)


class Categorizer:
    def __init__(self, db):
        self.tree = Tree(db)
        self.mappings = {m.tr_type: m.category_id for m in db.scalars(select(TypeMapping))}
        self.accounts = {a.iban: a for a in db.scalars(select(OwnAccount))}
        self.defaults = dict(db.execute(select(Counterparty.id, Counterparty.default_category_id)).all())

    def __call__(self, t):
        base = base_category(t, self.tree, self.mappings, self.accounts)
        if base is None:
            return None
        root = self.tree.root_of(base)
        if base != root:
            # a type-specific Category (Fees, Buy, Dividends…) beats the Counterparty's default,
            # otherwise one security's Buy default would also relabel its Sells
            return base
        mcc = self.tree.find("Expense", MCC.get(t.mcc or "", []))
        for cand in (self.defaults.get(t.eff_counterparty_id), mcc):
            if cand in self.tree.cats and self.tree.root_of(cand) == root:
                return cand
        return root


def recategorize(db):
    # shortcut: full recompute on every rule change; fine for a few thousand rows, scope it per Counterparty if slow
    cat = Categorizer(db)
    for t in db.scalars(select(Transaction).where(Transaction.tx_id.is_not(None))):
        t.category_id = cat(t)
    db.flush()
