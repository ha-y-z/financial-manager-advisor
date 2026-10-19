import csv
import io
from datetime import date

from sqlalchemy import select

from .classify import Tree, counterparty_for, norm_iban, recategorize
from .models import Transaction

REQUIRED = {"date", "type", "name", "amount", "transaction_id", "description", "counterparty_iban", "mcc_code"}


def import_csv(db, data: bytes):
    """Upsert a Trade Republic CSV by transaction id; bank fields only, never Overrides or Exclusion."""
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        missing = REQUIRED - set(reader.fieldnames or [])
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("This is not a readable CSV file.")
    if missing:
        raise ValueError(f"Not a Trade Republic CSV export (missing columns: {', '.join(sorted(missing))}).")

    rows = list(reader)
    existing = {t.tx_id: t for t in db.scalars(select(Transaction).where(Transaction.tx_id.in_([r["transaction_id"] for r in rows])))}
    known = set(existing)
    for n, r in enumerate(rows, start=2):
        try:
            values = dict(date=date.fromisoformat(r["date"]), amount=float(r["amount"]))
        except ValueError:
            raise ValueError(f"Line {n}: invalid date or amount.")
        if not r["transaction_id"]:
            raise ValueError(f"Line {n}: missing transaction_id.")
        t = existing.get(r["transaction_id"])
        if not t:
            t = existing[r["transaction_id"]] = Transaction(tx_id=r["transaction_id"])
            db.add(t)
        raw = r["name"] or r["counterparty_name"] or r["description"] or r["type"]
        t.date, t.amount = values["date"], values["amount"]
        t.raw_name, t.tr_type, t.description = raw, r["type"], r["description"]
        t.mcc, t.iban = r["mcc_code"] or None, norm_iban(r["counterparty_iban"])
        t.counterparty_id = counterparty_for(db, raw)
    recategorize(db)
    db.commit()

    tree = Tree(db)
    seen = list(existing.values())
    return {
        "new": len(seen) - len(known),
        "known": len(known),
        "uncategorized": sum(1 for t in seen if not t.excluded and tree.uncategorized(t.eff_category_id)),
        "excluded": sum(1 for t in seen if t.excluded),
    }
