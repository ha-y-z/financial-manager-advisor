from collections import defaultdict

from sqlalchemy import select

from .classify import Tree
from .models import Counterparty, Transaction


def effective_rows(db, tree, start, end):
    """Effective (Override-applied), non-Excluded Transactions in the period."""
    names = dict(db.execute(select(Counterparty.id, Counterparty.name)).all())
    rows = []
    for t in db.scalars(select(Transaction).where(Transaction.excluded.is_(False))):
        if start <= t.eff_date <= end:
            cid = t.eff_category_id
            rows.append(dict(date=t.eff_date, amount=t.eff_amount, cid=cid, flow=tree.flow(cid),
                             cp=t.eff_counterparty_id, cp_name=names.get(t.eff_counterparty_id, "?")))
    return rows


def summarize(rows, sign):
    """Hover detail: signed sum, count and top 3 Counterparties."""
    by_cp = defaultdict(float)
    for r in rows:
        by_cp[r["cp_name"]] += sign * r["amount"]
    top = sorted(by_cp.items(), key=lambda kv: -kv[1])[:3]
    return dict(sum=round(sign * sum(r["amount"] for r in rows), 2), count=len(rows),
                top=[dict(name=n, sum=round(v, 2)) for n, v in top])


def category_nodes(tree, rows, flow, sign):
    """Category hierarchy with positive net totals (Refunds netted), Uncategorized as an extra top node."""
    rows = [r for r in rows if r["flow"] == flow]
    root = tree.root[flow]

    def node(cid):
        sub = set(tree.subtree(cid))
        info = summarize([r for r in rows if r["cid"] in sub], sign)
        if info["sum"] <= 0:
            return None
        kids = [k for k in map(node, tree.children(cid)) if k]
        return dict(key=f"c{cid}", name=tree.cats[cid].name, value=info["sum"], info=info,
                    filter=dict(category_id=cid), children=kids)

    tops = [n for n in map(node, tree.children(root)) if n]
    info = summarize([r for r in rows if r["cid"] == root], sign)
    if info["sum"] > 0:
        tops.append(dict(key=f"u{root}", name=f"Uncategorized {flow.lower()}", value=info["sum"], info=info,
                         filter=dict(flow=flow, uncategorized=True), children=[]))
    return tops


def sankey(tree, rows):
    nodes, links = [dict(name="budget", label="Budget")], []

    def add(n, src, dst):
        nodes.append(dict(name=n["key"], label=n["name"], info=n["info"], filter=n["filter"]))
        links.append(dict(source=src, target=dst, value=n["value"], info=n["info"], filter=n["filter"]))

    income, expense = category_nodes(tree, rows, "Income", 1), category_nodes(tree, rows, "Expense", -1)
    for top in income:
        add(top, top["key"], "budget")
        for kid in top["children"]:
            add(kid, kid["key"], top["key"])
    for top in expense:
        add(top, "budget", top["key"])
        for kid in top["children"]:
            add(kid, top["key"], kid["key"])

    inv_rows = [r for r in rows if r["flow"] == "Investment Flow"]
    inv = summarize(inv_rows, -1)
    inv_node = dict(info=inv, filter=dict(flow="Investment Flow"), value=abs(inv["sum"]))
    inflow = sum(n["value"] for n in income)
    outflow = sum(n["value"] for n in expense)
    if inv["sum"] > 0:
        add(dict(inv_node, key="investments", name="Investments"), "budget", "investments")
        outflow += inv["sum"]
    elif inv["sum"] < 0:  # net selling funds the budget
        add(dict(inv_node, key="from_investments", name="From Investments"), "from_investments", "budget")
        inflow += -inv["sum"]

    gap = round(inflow - outflow, 2)
    rest = dict(info=None, filter=None, value=abs(gap))
    if gap > 0:
        add(dict(rest, key="saved", name="Saved"), "budget", "saved")
    elif gap < 0:
        add(dict(rest, key="reserves", name="From Reserves"), "reserves", "budget")
    return dict(nodes=nodes, links=links)


def monthly(rows, start, end):
    months = {}
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months[f"{y}-{m:02d}"] = dict(income=0.0, expense=0.0)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for r in rows:
        key = r["date"].strftime("%Y-%m")
        if r["flow"] == "Income":
            months[key]["income"] += r["amount"]
        elif r["flow"] == "Expense":
            months[key]["expense"] -= r["amount"]
    return [dict(month=k, income=round(v["income"], 2), expense=round(v["expense"], 2),
                 rate=round((v["income"] - v["expense"]) / v["income"], 4) if v["income"] > 0 else None)
            for k, v in months.items()]


def top_counterparties(rows, n=10):
    by_cp = defaultdict(list)
    for r in rows:
        if r["flow"] == "Expense":
            by_cp[(r["cp"], r["cp_name"])].append(r)
    ranked = [dict(name=name, info=summarize(rs, -1), filter=dict(counterparty_id=cp)) for (cp, name), rs in by_cp.items()]
    return sorted([x for x in ranked if x["info"]["sum"] > 0], key=lambda x: -x["info"]["sum"])[:n]


def analytics(db, start, end):
    tree = Tree(db)
    rows = effective_rows(db, tree, start, end)
    return dict(
        monthly=monthly(rows, start, end),
        sunburst=dict(Expense=category_nodes(tree, rows, "Expense", -1), Income=category_nodes(tree, rows, "Income", 1)),
        sankey=sankey(tree, rows),
        top=top_counterparties(rows),
        totals=dict(income=round(sum(r["amount"] for r in rows if r["flow"] == "Income"), 2),
                    expense=round(-sum(r["amount"] for r in rows if r["flow"] == "Expense"), 2),
                    invested=round(-sum(r["amount"] for r in rows if r["flow"] == "Investment Flow"), 2)),
    )
