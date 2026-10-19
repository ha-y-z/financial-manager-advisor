import calendar
from datetime import date

from sqlalchemy import select

from .models import Counterparty, RecurringEntry, Transaction

STEP = {"monthly": 1, "quarterly": 3, "yearly": 12}


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def materialize(db, today=None):
    """Create the missing Manual Transactions of every Recurring Entry up to today (or its end)."""
    today = today or date.today()
    for r in db.scalars(select(RecurringEntry)):
        until = min(today, r.end) if r.end else today
        have = set(db.scalars(select(Transaction.date).where(Transaction.recurring_id == r.id)))
        name = db.get(Counterparty, r.counterparty_id).name
        i = 0
        while (d := add_months(r.start, i * STEP[r.interval])) <= until:
            if d not in have:
                db.add(Transaction(recurring_id=r.id, date=d, amount=r.amount, raw_name=name,
                                   counterparty_id=r.counterparty_id, category_id=r.category_id))
            i += 1
    db.commit()
