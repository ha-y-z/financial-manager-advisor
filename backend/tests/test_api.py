import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.classify import normalize
from app.db import get_db
from app.main import app, init
from app.portfolio import de_num

HEADER = ("datetime,date,account_type,category,type,asset_class,name,symbol,shares,price,amount,fee,tax,currency,"
          "original_amount,original_currency,fx_rate,description,transaction_id,counterparty_name,counterparty_iban,"
          "payment_reference,mcc_code").split(",")
SALARY_IBAN, SAVINGS_IBAN, STRANGER_IBAN = "DE11111111111111111111", "DE22222222222222222222", "DE33333333333333333333"


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    factory = sessionmaker(engine, expire_on_commit=False)
    init(factory, engine)

    def db():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = db
    yield TestClient(app)  # no context manager: skip the lifespan that targets the real DB
    app.dependency_overrides.clear()


def row(tx_id, type="CARD_TRANSACTION", name="REWE Markt 123", amount=-10.0, day="2026-03-05", mcc="", iban=""):
    return dict(date=day, type=type, name=name, amount=amount, transaction_id=tx_id, mcc_code=mcc,
                counterparty_iban=iban, currency="EUR", description=name)


def upload(client, *rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, HEADER, quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows({k: r.get(k, "") for k in HEADER} for r in rows)
    return client.post("/api/import/transactions", files={"file": ("tr.csv", buf.getvalue().encode())})


def txs(client, **params):
    return {t["id"]: t for t in client.get("/api/transactions", params=params).json()}


def by_tx(client, **params):
    return {t["description"]: t for t in client.get("/api/transactions", params=params).json()}


def cat_id(client, path):
    return next(c["id"] for c in client.get("/api/categories").json() if c["path"] == path)


def analytics(client, start="2026-03-01", end="2026-03-31"):
    return client.get("/api/analytics", params=dict(start=start, end=end)).json()


# --- import ---------------------------------------------------------------------

def test_counterparty_from_name_then_description_never_counterparty_name(client):
    rows = [row("n1", name="REWE Markt 1"), row("n2", name=""), row("n3", name="12345")]
    rows[1]["description"], rows[2]["description"] = "Spotify AB", "Netflix"
    for r in rows:
        r["counterparty_name"] = "Max Mustermann"
    upload(client, *rows)
    assert {t["counterparty"] for t in txs(client).values()} == {"REWE Markt", "Spotify AB", "Netflix"}
    assert "Max Mustermann" not in {c["name"] for c in client.get("/api/counterparties").json()}


def test_reimport_is_idempotent_and_keeps_overrides_and_exclusions(client):
    rows = [row("a", amount=-10), row("b", name="Kino", amount=-20), row("c", name="Bar", amount=-5)]
    assert upload(client, *rows).json() == dict(new=3, known=0, uncategorized=3, excluded=0)
    t = {x["description"]: x for x in txs(client).values()}
    client.patch(f"/api/transactions/{t['REWE Markt 123']['id']}", json=dict(amount=-99))
    client.post(f"/api/transactions/{t['Kino']['id']}/exclude", json=dict(excluded=True))

    summary = upload(client, *rows, row("d", name="New", amount=-1)).json()
    assert summary == dict(new=1, known=3, uncategorized=3, excluded=1)
    after = by_tx(client)
    assert len(after) == 3 and "Kino" not in after
    assert after["REWE Markt 123"]["amount"] == -99 and after["REWE Markt 123"]["overridden"]
    assert after["REWE Markt 123"]["original"]["amount"] == -10

    client.delete(f"/api/transactions/{t['REWE Markt 123']['id']}/override")
    assert by_tx(client)["REWE Markt 123"]["amount"] == -10
    client.post(f"/api/transactions/{t['Kino']['id']}/exclude", json=dict(excluded=False))
    assert "Kino" in by_tx(client)


def test_rejects_non_trade_republic_csv(client):
    r = client.post("/api/import/transactions", files={"file": ("x.csv", b"foo,bar\n1,2\n")})
    assert r.status_code == 400 and "Trade Republic" in r.json()["detail"]


# --- Flow Types -------------------------------------------------------------------

def test_type_mapping_table(client):
    client.put(f"/api/own-accounts/{SALARY_IBAN}", json=dict(label="Salary", income_source=True))
    client.put(f"/api/own-accounts/{SAVINGS_IBAN}", json=dict(label="Savings"))
    cases = {
        "card": (row("1"), "Expense"),
        "intl": (row("2", type="CARD_TRANSACTION_INTERNATIONAL"), "Expense"),
        "fee": (row("3", type="CARD_ORDERING_FEE", name="Card fee"), "Expense › Fees"),
        "buy": (row("4", type="BUY", name="MSCI World"), "Investment Flow › Buy"),
        "sell": (row("5", type="SELL", name="MSCI World", amount=50), "Investment Flow › Sell"),
        "saveback": (row("6", type="BENEFITS_SAVEBACK", name="MSCI World", amount=-3), "Investment Flow › Saveback"),
        "dividend": (row("7", type="DIVIDEND", name="Apple", amount=2), "Income › Investment Income › Dividends"),
        "interest": (row("8", type="INTEREST_PAYMENT", name="Zinsen", amount=4), "Income › Investment Income › Interest"),
        "in_salary": (row("9", type="TRANSFER_INBOUND", name="Me", amount=2000, iban=SALARY_IBAN), "Income"),
        "in_own": (row("10", type="TRANSFER_INSTANT_INBOUND", name="Me", amount=100, iban=SAVINGS_IBAN), "Internal Transfer"),
        "in_other": (row("11", type="TRANSFER_INBOUND", name="Mum", amount=50, iban=STRANGER_IBAN), "Income"),
        "out_salary": (row("12", type="TRANSFER_INSTANT_OUTBOUND", name="Me", amount=-100, iban=SALARY_IBAN), "Internal Transfer"),
        "out_own": (row("13", type="TRANSFER_INSTANT_OUTBOUND", name="Me", amount=-100, iban=SAVINGS_IBAN), "Internal Transfer"),
        "out_other": (row("14", type="TRANSFER_INSTANT_OUTBOUND", name="Landlord", amount=-800, iban=STRANGER_IBAN), "Expense"),
        "dd_no_iban": (row("15", type="TRANSFER_DIRECT_DEBIT_INBOUND", name="Top-up", amount=300), "Internal Transfer"),
        "dd_salary": (row("16", type="TRANSFER_DIRECT_DEBIT_INBOUND", name="Me", amount=300, iban=SALARY_IBAN), "Income"),
        "dd_own": (row("17", type="TRANSFER_DIRECT_DEBIT_INBOUND", name="Me", amount=300, iban=SAVINGS_IBAN), "Internal Transfer"),
        "dd_other": (row("18", type="TRANSFER_DIRECT_DEBIT_INBOUND", name="X", amount=300, iban=STRANGER_IBAN), "Income"),
        "unknown": (row("19", type="WEIRD_NEW_TYPE", name="??", amount=1), "Uncategorized"),
    }
    for key, (r, _) in cases.items():
        r["description"] = key
    upload(client, *(r for r, _ in cases.values()))
    got = by_tx(client)
    assert {k: got[k]["category"] for k in cases} == {k: v for k, (_, v) in cases.items()}

    # Own Account changes apply retroactively
    client.delete(f"/api/own-accounts/{SAVINGS_IBAN}")
    assert by_tx(client)["in_own"]["category"] == "Income"


def test_unknown_type_goes_to_review_and_mapping_is_retroactive(client):
    upload(client, row("x1", type="GIFT", name="Gift", amount=5), row("x2", type="GIFT", name="Gift", amount=7))
    m = client.get("/api/type-mappings").json()
    assert m["unknown"] == [dict(tr_type="GIFT", count=2)]
    assert len(txs(client, uncategorized=True)) == 2
    client.put("/api/type-mappings/GIFT", json=dict(category_id=cat_id(client, "Income › Other Income")))
    assert {t["category"] for t in txs(client).values()} == {"Income › Other Income"}
    assert client.get("/api/type-mappings").json()["unknown"] == []
    upload(client, row("x3", type="GIFT", name="Gift", amount=1))
    assert len(txs(client, uncategorized=True)) == 0


# --- categorization ----------------------------------------------------------------

def test_pipeline_default_category_then_mcc(client):
    upload(client, row("m1", name="REWE Markt 1", mcc="5411"), row("m2", name="Unknown shop"))
    assert by_tx(client)["REWE Markt 1"]["category"] == "Expense › Food › Groceries"
    assert by_tx(client)["Unknown shop"]["uncategorized"]


def test_default_category_is_retroactive_but_spares_overrides(client):
    upload(client, *(row(f"a{i}", name=f"AMZN Mktp DE*{i}AB{i}", amount=-10 * (i + 1)) for i in range(3)))
    ids = sorted(txs(client))
    electronics, household = cat_id(client, "Expense › Shopping › Electronics"), cat_id(client, "Expense › Shopping › Household")
    client.put(f"/api/transactions/{ids[0]}/category", json=dict(category_id=electronics, scope="this"))
    client.put(f"/api/transactions/{ids[1]}/category", json=dict(category_id=household, scope="counterparty"))
    cats = {i: t["category"] for i, t in txs(client).items()}
    assert cats == {ids[0]: "Expense › Shopping › Electronics", ids[1]: "Expense › Shopping › Household",
                    ids[2]: "Expense › Shopping › Household"}
    # future imports follow the default
    upload(client, row("a9", name="AMZN Mktp DE*9ZZ9", amount=-1))
    assert by_tx(client)["AMZN Mktp DE*9ZZ9"]["category"] == "Expense › Shopping › Household"


def test_default_category_must_match_flow(client):
    upload(client, row("f1", name="Shop"))
    tid = next(iter(txs(client)))
    r = client.put(f"/api/transactions/{tid}/category", json=dict(category_id=cat_id(client, "Income › Salary"), scope="counterparty"))
    assert r.status_code == 400


# --- counterparties ------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("DM-FIL. A1EN", "DM"), ("DM-FIL. B2XY", "DM"), ("REWE Markt GmbH 1234", "REWE Markt GmbH"),
    ("AMZN Mktp DE*1A2B3", "AMZN Mktp DE"), ("PAYPAL *SPOTIFY", "PAYPAL *SPOTIFY"), ("Lidl", "Lidl"),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_merge_with_conflicting_defaults_and_split(client):
    upload(client, row("1", name="DM-FIL. A1EN"), row("2", name="DM-FIL. B2XY"), row("3", name="Rossmann 77"))
    cps = {c["name"]: c for c in client.get("/api/counterparties").json()}
    assert sorted(cps["DM"]["aliases"]) == ["DM-FIL. A1EN", "DM-FIL. B2XY"]
    drug, other = cat_id(client, "Expense › Health & Drugstore"), cat_id(client, "Expense › Other")
    client.patch(f"/api/counterparties/{cps['DM']['id']}", json=dict(default_category_id=drug))
    client.patch(f"/api/counterparties/{cps['Rossmann']['id']}", json=dict(default_category_id=other))

    client.post("/api/counterparties/merge", json=dict(keep_id=cps["DM"]["id"], drop_id=cps["Rossmann"]["id"],
                                                       default_category_id=other))
    after = client.get("/api/counterparties").json()
    assert len(after) == 1 and after[0]["default_category"] == "Expense › Other" and len(after[0]["aliases"]) == 3
    assert {t["category"] for t in txs(client).values()} == {"Expense › Other"}

    client.post("/api/counterparties/split", json=dict(raw_name="Rossmann 77"))
    t = by_tx(client)["Rossmann 77"]
    assert t["counterparty"] == "Rossmann 77" and t["uncategorized"]


# --- categories -----------------------------------------------------------------------

def test_category_delete_reassigns_and_roots_are_protected(client):
    upload(client, row("1", name="REWE", mcc="5411"), row("2", name="Cafe", mcc="5812"))
    groceries, food = cat_id(client, "Expense › Food › Groceries"), cat_id(client, "Expense › Food")
    assert client.get(f"/api/categories/{groceries}/impact").json()["transactions"] == 1
    client.delete(f"/api/categories/{groceries}")
    assert by_tx(client)["REWE"]["category"] == "Expense › Food"
    impact = client.get(f"/api/categories/{food}/impact").json()
    assert impact["transactions"] == 2 and impact["moved_to"] == "Uncategorized"
    client.delete(f"/api/categories/{food}")
    assert all(t["uncategorized"] and t["flow"] == "Expense" for t in txs(client).values())

    expense = cat_id(client, "Expense")
    assert client.delete(f"/api/categories/{expense}").status_code == 400
    assert client.patch(f"/api/categories/{expense}", json=dict(name="X")).status_code == 400
    lvl2 = cat_id(client, "Expense › Leisure › Travel")
    assert client.post("/api/categories", json=dict(name="Too deep", parent_id=lvl2)).status_code == 400


# --- manual and recurring ---------------------------------------------------------------

def test_recurring_entry_generates_and_edits_only_future(client):
    today = date.today()
    start = date(today.year - 1, today.month, 1)
    insurance = cat_id(client, "Expense › Insurance")
    rid = client.post("/api/recurring", json=dict(amount=-36, counterparty="HUK", category_id=insurance,
                                                  interval="monthly", start=str(start))).json()["id"]
    generated = txs(client)
    assert len(generated) == 13 and all(t["manual"] and t["amount"] == -36 for t in generated.values())
    client.patch(f"/api/recurring/{rid}", json=dict(amount=-40))
    assert {t["amount"] for t in txs(client).values()} == {-36}  # history unchanged

    end = date(today.year - 1, today.month, 15)
    client.patch(f"/api/recurring/{rid}", json=dict(end=str(end)))
    assert len(txs(client)) == 1


def test_manual_transactions_are_editable_and_deletable(client):
    tid = client.post("/api/transactions", json=dict(date="2026-03-02", amount=-12.5, counterparty="Bakery",
                                                     category_id=cat_id(client, "Expense › Food"))).json()["id"]
    client.patch(f"/api/transactions/{tid}", json=dict(amount=-13))
    t = txs(client)[tid]
    assert t["manual"] and not t["overridden"] and t["amount"] == -13
    client.delete(f"/api/transactions/{tid}")
    assert txs(client) == {}


# --- analytics -------------------------------------------------------------------------

def test_refunds_net_and_sankey_balances(client):
    client.put(f"/api/own-accounts/{SALARY_IBAN}", json=dict(income_source=True))
    upload(client,
           row("s", type="TRANSFER_INBOUND", name="Me", amount=1000, iban=SALARY_IBAN),
           row("g1", name="REWE", amount=-100, mcc="5411"),
           row("g2", name="REWE", amount=30, mcc="5411"),  # refund
           row("b", type="BUY", name="ETF", amount=-500),
           row("i", type="TRANSFER_INSTANT_OUTBOUND", name="Me", amount=-200, iban=SALARY_IBAN))
    a = analytics(client)
    assert a["totals"] == dict(income=1000, expense=70, invested=500)
    assert a["monthly"] == [dict(month="2026-03", income=1000, expense=70, rate=0.93)]
    food = a["sunburst"]["Expense"][0]
    assert food["name"] == "Food" and food["value"] == 70 and food["info"]["count"] == 2

    s = a["sankey"]
    into = sum(l["value"] for l in s["links"] if l["target"] == "budget")
    out_ = sum(l["value"] for l in s["links"] if l["source"] == "budget")
    assert into == out_ == 1000
    assert {"saved", "investments"} <= {n["name"] for n in s["nodes"]}


def test_sankey_from_reserves_on_deficit(client):
    upload(client, row("in", type="INTEREST_PAYMENT", name="Zinsen", amount=10), row("x", name="Shop", amount=-60))
    s = analytics(client)["sankey"]
    reserves = next(l for l in s["links"] if l["source"] == "reserves")
    assert reserves["value"] == 50
    assert sum(l["value"] for l in s["links"] if l["target"] == "budget") == \
           sum(l["value"] for l in s["links"] if l["source"] == "budget")


# --- portfolio -------------------------------------------------------------------------

def statement_pdf(day, holdings, count=None, total=None):
    """Synthetic Portfolio Statement modeled on the Trade Republic layout."""
    def de(x):
        return f"{x:,.2f}".replace(",", " ").replace(".", ",")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    lines = ["Synthetic Bank AG, Street 1, 10000 Berlin", "DATUM 01.04.2026", "DEPOTAUSZUG", f"zum {day}", "POSITIONEN",
             "STK. / NOMINALE WERTPAPIERBEZEICHNUNG KURS PRO STÜCK KURSWERT IN EUR"]
    for qty, name, price, isin in holdings:
        lines += [f"{qty:.6f}".replace(".", ",") + f" Stk. {name} {de(price)} {de(qty * price)}",
                  f"Acc. shares {day}", f"ISIN: {isin}", "Lagerland: Deutschland"]
    count = len(holdings) if count is None else count
    total = sum(q * p for q, _, p, _ in holdings) if total is None else total
    lines += [f"ANZAHL POSITIONEN: {count} {de(total)} EUR", "Seite 1 von 1"]
    for line in lines:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


HOLDINGS = [(12.5, "iShares Core MSCI World", 100.0, "IE00B4L5Y983"), (3.0, "S&P 500 1 Corp", 1234.5, "US0378331005")]


def import_pdf(client, data):
    return client.post("/api/import/portfolio", files={"file": ("statement.pdf", data)})


def test_german_numbers():
    assert de_num("1 234,56") == 1234.56 and de_num("1.234,56") == 1234.56 and de_num("0,123456") == 0.123456


def test_portfolio_import_snapshots_and_tags(client):
    r = import_pdf(client, statement_pdf("31.03.2026", HOLDINGS)).json()
    assert r["holdings"] == 2 and r["total"] == 4953.5 and not r["replaced"]
    sid = client.get("/api/portfolio/snapshots").json()[0]["id"]
    snap = client.get(f"/api/portfolio/snapshots/{sid}").json()
    assert [(h["isin"], h["quantity"], h["price"]) for h in snap["holdings"]] == [
        ("US0378331005", 3.0, 1234.5), ("IE00B4L5Y983", 12.5, 100.0)]

    client.put("/api/holdings/IE00B4L5Y983/tags", json=["ETF", "World"])
    assert import_pdf(client, statement_pdf("31.03.2026", HOLDINGS[:1])).json()["replaced"]
    import_pdf(client, statement_pdf("30.04.2026", HOLDINGS))
    snaps = client.get("/api/portfolio/snapshots").json()
    assert [s["date"] for s in snaps] == ["2026-03-31", "2026-04-30"] and snaps[0]["total"] == 1250
    latest = client.get(f"/api/portfolio/snapshots/{snaps[1]['id']}").json()
    assert {t["name"]: t["value"] for t in latest["by_tag"]} == {"Untagged": 3703.5, "ETF": 1250, "World": 1250}


def test_portfolio_mismatch_is_rejected(client):
    r = import_pdf(client, statement_pdf("31.03.2026", HOLDINGS, count=3))
    assert r.status_code == 422 and "2 Holdings" in r.json()["detail"] and "lists 3" in r.json()["detail"]
    r = import_pdf(client, statement_pdf("31.03.2026", HOLDINGS, total=9999))
    assert r.status_code == 422
    assert client.get("/api/portfolio/snapshots").json() == []
    assert import_pdf(client, b"not a pdf").status_code == 422


def test_factory_reset_restores_seed(client):
    defaults = client.get("/api/categories").json()
    upload(client, row("a"))
    client.post("/api/categories", json=dict(name="Hobby", parent_id=cat_id(client, "Expense")))
    client.put(f"/api/own-accounts/{SALARY_IBAN}", json=dict(label="Salary"))
    import_pdf(client, statement_pdf("31.03.2026", HOLDINGS))
    assert client.post("/api/reset").status_code == 200
    for url in ("/api/transactions", "/api/counterparties", "/api/own-accounts", "/api/portfolio/snapshots"):
        assert client.get(url).json() == []
    assert [c["path"] for c in client.get("/api/categories").json()] == [c["path"] for c in defaults]
