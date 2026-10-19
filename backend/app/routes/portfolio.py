from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import delete, select

from ..db import get_db
from ..models import Holding, Snapshot, Tag
from ..portfolio import parse_statement

router = APIRouter()


@router.post("/import/portfolio")
async def upload_pdf(file: UploadFile, db=Depends(get_db)):
    try:
        when, holdings = parse_statement(await file.read())  # bytes stay in memory (ADR 0003)
    except ValueError as e:
        raise HTTPException(422, str(e))
    replaced = db.scalar(select(Snapshot).where(Snapshot.date == when))
    if replaced:
        db.delete(replaced)
        db.flush()
    db.add(Snapshot(date=when, holdings=[Holding(**h) for h in holdings]))
    db.commit()
    return dict(date=when, holdings=len(holdings), total=round(sum(h["value"] for h in holdings), 2),
                replaced=bool(replaced))


@router.get("/portfolio/snapshots")
def snapshots(db=Depends(get_db)):
    return [dict(id=s.id, date=s.date, total=round(sum(h.value for h in s.holdings), 2))
            for s in db.scalars(select(Snapshot).order_by(Snapshot.date))]


@router.get("/portfolio/snapshots/{sid}")
def snapshot(sid: int, db=Depends(get_db)):
    s = db.get(Snapshot, sid)
    if not s:
        raise HTTPException(404)
    tags = defaultdict(list)
    for t in db.scalars(select(Tag)):
        tags[t.isin].append(t.name)
    holdings = sorted((dict(isin=h.isin, name=h.name, quantity=h.quantity, price=h.price, value=h.value,
                            tags=sorted(tags[h.isin])) for h in s.holdings), key=lambda h: -h["value"])
    by_tag = defaultdict(lambda: dict(value=0.0, isins=[]))
    for h in holdings:
        for name in h["tags"] or ["Untagged"]:
            by_tag[name]["value"] += h["value"]
            by_tag[name]["isins"].append(h["isin"])
    return dict(id=s.id, date=s.date, total=round(sum(h["value"] for h in holdings), 2), holdings=holdings,
                by_tag=sorted((dict(name=k, value=round(v["value"], 2), isins=v["isins"]) for k, v in by_tag.items()),
                              key=lambda x: -x["value"]))


@router.get("/tags")
def all_tags(db=Depends(get_db)):
    return sorted(set(db.scalars(select(Tag.name))))


@router.put("/holdings/{isin}/tags")
def set_tags(isin: str, names: list[str], db=Depends(get_db)):
    db.execute(delete(Tag).where(Tag.isin == isin))
    db.add_all(Tag(isin=isin, name=n.strip()) for n in {n.strip() for n in names} if n)
    db.commit()
    return {"ok": True}
