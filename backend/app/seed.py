from sqlalchemy import select

from .models import Category, TypeMapping

ROOTS = ("Income", "Expense", "Investment Flow", "Internal Transfer")

TREE = {
    "Income": {"Salary": [], "Investment Income": ["Dividends", "Interest"], "Cashback": [], "Other Income": []},
    "Expense": {
        "Housing": ["Rent", "Utilities"],
        "Food": ["Groceries", "Restaurants & Cafés"],
        "Transport": ["Public Transport", "Fuel", "Taxi"],
        "Shopping": ["Clothing", "Electronics", "Household"],
        "Health & Drugstore": [],
        "Leisure": ["Subscriptions", "Travel", "Culture"],
        "Insurance": [],
        "Fees": [],
        "Other": [],
    },
    "Investment Flow": {"Buy": [], "Sell": [], "Saveback": []},
    "Internal Transfer": {},
}

# Trade Republic type -> (root, category name or None). TRANSFER_* types are resolved by IBAN in classify.py.
TYPE_MAP = {
    "CARD_TRANSACTION": ("Expense", None),
    "CARD_TRANSACTION_INTERNATIONAL": ("Expense", None),
    "CARD_ORDERING_FEE": ("Expense", "Fees"),
    "BUY": ("Investment Flow", "Buy"),
    "SELL": ("Investment Flow", "Sell"),
    "BENEFITS_SAVEBACK": ("Investment Flow", "Saveback"),
    "DIVIDEND": ("Income", "Dividends"),
    "INTEREST_PAYMENT": ("Income", "Interest"),
}

# Merchant category code -> Expense Category path, looked up by name: a deleted child falls back to its parent.
_MCC_GROUPS = {
    "Food/Groceries": "5411 5422 5441 5451 5499",
    "Food/Restaurants & Cafés": "5462 5811 5812 5813 5814",
    "Transport/Public Transport": "4011 4111 4112 4131 4789",
    "Transport/Taxi": "4121",
    "Transport/Fuel": "5541 5542 5552",
    "Shopping/Clothing": "5611 5621 5631 5641 5651 5655 5661 5691 5699",
    "Shopping/Electronics": "5045 5732 5734 5946",
    "Shopping/Household": "5200 5211 5251 5261 5310 5712 5719 5722",
    "Shopping": "5311 5399 5964 5999",
    "Health & Drugstore": "5912 5977 8011 8021 8042 8043 8062 8099",
    "Leisure/Subscriptions": "4816 4899 5815 5816 5817 5818",
    "Leisure/Travel": "3000 4411 4511 4722 7011 7012 7512",
    "Leisure/Culture": "5942 5994 7832 7922 7929 7991 7996 7997 7999",
    "Housing/Utilities": "4814 4900",
    "Insurance": "6300 6381",
}
MCC = {code: path.split("/") for path, codes in _MCC_GROUPS.items() for code in codes.split()}


def seed(db):
    if db.scalar(select(Category.id).limit(1)):
        return
    for root, children in TREE.items():
        r = Category(name=root)
        db.add(r)
        db.flush()
        for child, grandchildren in children.items():
            c = Category(name=child, parent_id=r.id)
            db.add(c)
            db.flush()
            db.add_all(Category(name=g, parent_id=c.id) for g in grandchildren)
    db.flush()
    by_name = {c.name: c.id for c in db.scalars(select(Category))}
    db.add_all(TypeMapping(tr_type=t, category_id=by_name[cat or root]) for t, (root, cat) in TYPE_MAP.items())
    db.commit()
