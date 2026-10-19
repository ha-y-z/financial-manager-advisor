import datetime as dt

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

Id = Mapped[int]
OptId = Mapped[int | None]


class Category(Base):
    __tablename__ = "category"
    id: Id = mapped_column(primary_key=True)
    name: Mapped[str]
    parent_id: OptId = mapped_column(ForeignKey("category.id"))


class Counterparty(Base):
    __tablename__ = "counterparty"
    id: Id = mapped_column(primary_key=True)
    name: Mapped[str]
    default_category_id: OptId = mapped_column(ForeignKey("category.id"))
    aliases: Mapped[list["Alias"]] = relationship(back_populates="counterparty")


class Alias(Base):
    __tablename__ = "alias"
    raw_name: Mapped[str] = mapped_column(primary_key=True)
    counterparty_id: Id = mapped_column(ForeignKey("counterparty.id"))
    counterparty: Mapped[Counterparty] = relationship(back_populates="aliases")


class OwnAccount(Base):
    __tablename__ = "own_account"
    iban: Mapped[str] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="")
    income_source: Mapped[bool] = mapped_column(default=False)


class TypeMapping(Base):
    __tablename__ = "type_mapping"
    tr_type: Mapped[str] = mapped_column(primary_key=True)
    category_id: Id = mapped_column(ForeignKey("category.id"))


class RecurringEntry(Base):
    __tablename__ = "recurring_entry"
    id: Id = mapped_column(primary_key=True)
    amount: Mapped[float]
    counterparty_id: Id = mapped_column(ForeignKey("counterparty.id"))
    category_id: Id = mapped_column(ForeignKey("category.id"))
    interval: Mapped[str]  # monthly | quarterly | yearly
    start: Mapped[dt.date]
    end: Mapped[dt.date | None]


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = (UniqueConstraint("recurring_id", "date"),)
    id: Id = mapped_column(primary_key=True)
    tx_id: Mapped[str | None] = mapped_column(unique=True)  # bank id; None for manual
    recurring_id: OptId = mapped_column(ForeignKey("recurring_entry.id"))
    # bank (or manual) values
    date: Mapped[dt.date]
    amount: Mapped[float]
    raw_name: Mapped[str] = mapped_column(default="")
    tr_type: Mapped[str | None]
    mcc: Mapped[str | None]
    iban: Mapped[str | None]
    description: Mapped[str] = mapped_column(default="")
    counterparty_id: OptId = mapped_column(ForeignKey("counterparty.id"))
    category_id: OptId = mapped_column(ForeignKey("category.id"))
    # Overrides of imported values
    o_amount: Mapped[float | None]
    o_date: Mapped[dt.date | None]
    o_counterparty_id: OptId = mapped_column(ForeignKey("counterparty.id"))
    o_category_id: OptId = mapped_column(ForeignKey("category.id"))
    excluded: Mapped[bool] = mapped_column(default=False)

    @property
    def manual(self):
        return self.tx_id is None

    @property
    def eff_amount(self):
        return self.amount if self.o_amount is None else self.o_amount

    @property
    def eff_date(self):
        return self.o_date or self.date

    @property
    def eff_counterparty_id(self):
        return self.o_counterparty_id or self.counterparty_id

    @property
    def eff_category_id(self):
        return self.o_category_id or self.category_id

    @property
    def overridden(self):
        return any(v is not None for v in (self.o_amount, self.o_date, self.o_counterparty_id, self.o_category_id))


class Snapshot(Base):
    __tablename__ = "snapshot"
    id: Id = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(unique=True)
    holdings: Mapped[list["Holding"]] = relationship(cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holding"
    id: Id = mapped_column(primary_key=True)
    snapshot_id: Id = mapped_column(ForeignKey("snapshot.id"))
    isin: Mapped[str]
    name: Mapped[str]
    quantity: Mapped[float]
    price: Mapped[float]
    value: Mapped[float]


class Tag(Base):
    __tablename__ = "tag"
    isin: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(primary_key=True)
