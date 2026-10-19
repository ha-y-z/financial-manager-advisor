from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, Session, engine
from .recurring import materialize
from .routes import portfolio, setup, transactions
from .seed import seed


def init(session_factory, bind):
    Base.metadata.create_all(bind)
    with session_factory() as db:
        seed(db)
        materialize(db)


@asynccontextmanager
async def lifespan(_):
    init(Session, engine)
    yield


app = FastAPI(title="Financial Manager", lifespan=lifespan)
for r in (transactions.router, setup.router, portfolio.router):
    app.include_router(r, prefix="/api")
