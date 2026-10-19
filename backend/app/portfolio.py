import io
import re
from datetime import datetime

import pdfplumber

NUM = r"\d{1,3}(?:[ .]\d{3})*,\d+"  # German format: 1 234,56 or 1.234,56
ROW = re.compile(rf"^({NUM}) Stk\. (.+)$")
ISIN = re.compile(r"^ISIN: ([A-Z]{2}[A-Z0-9]{9}\d)")


def de_num(s):
    return float(s.replace(" ", "").replace(".", "").replace(",", "."))


def split_tail(rest, qty):
    """'<name> <price> <value>' where numbers may contain spaces; pick the split where qty × price ≈ value."""
    toks = rest.split()
    best = None
    for k in range(1, 4):  # tokens in value
        for j in range(1, 4):  # tokens in price
            if j + k >= len(toks):
                continue
            price, value = " ".join(toks[-k - j:-k]), " ".join(toks[-k:])
            if re.fullmatch(NUM, price) and re.fullmatch(NUM, value):
                err = abs(qty * de_num(price) - de_num(value))
                if best is None or err < best[0]:
                    best = (err, " ".join(toks[:-k - j]), de_num(price), de_num(value))
    if not best:
        raise ValueError(f"Cannot read a Holding row of the Portfolio Statement.")
    return best[1:]


def parse_statement(data: bytes):
    """Statement date and Holdings from a Trade Republic Portfolio Statement, in memory only (ADR 0003)."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        raise ValueError("This is not a readable PDF file.")
    when = re.search(r"zum (\d{2}\.\d{2}\.\d{4})", text)
    totals = re.search(rf"ANZAHL POSITIONEN:\s*(\d+)\s+({NUM})\s*EUR", text)
    if not when or not totals:
        raise ValueError("Not a Trade Republic Portfolio Statement (statement date or ANZAHL POSITIONEN not found).")

    holdings, cur, continued = [], None, False
    for line in text.splitlines():
        if row := ROW.match(line):
            qty = de_num(row[1])
            name, price, value = split_tail(row[2], qty)
            cur, continued = dict(isin=None, name=name, quantity=qty, price=price, value=value), False
            holdings.append(cur)
        elif cur and (isin := ISIN.match(line)):
            cur["isin"], cur = isin[1], None
        elif cur and not continued:  # second name line, ends with the price date
            cur["name"] += " " + re.sub(r"\s*\d{2}\.\d{2}\.\d{4}$", "", line).strip()
            continued = True

    count, total = int(totals[1]), de_num(totals[2])
    parsed = round(sum(h["value"] for h in holdings), 2)
    if len(holdings) != count or abs(parsed - total) > 0.01 or any(h["isin"] is None for h in holdings):
        raise ValueError(
            f"Parsed {len(holdings)} Holdings worth {parsed:,.2f} EUR, but the statement lists "
            f"{count} worth {total:,.2f} EUR. The layout may have changed; nothing was imported."
        )
    return datetime.strptime(when[1], "%d.%m.%Y").date(), holdings
