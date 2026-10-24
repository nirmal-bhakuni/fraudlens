"""Database table for scored transactions."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # What the caller sent
    trans_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Float, index=True)
    category: Mapped[str] = mapped_column(String(32))
    merchant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    long: Mapped[float] = mapped_column(Float)
    merchant_lat: Mapped[float] = mapped_column(Float)
    merchant_long: Mapped[float] = mapped_column(Float)
    city_pop: Mapped[int] = mapped_column(Integer)

    # What we decided (kept for audit: what model, what score, which rules)
    risk_score: Mapped[float] = mapped_column(Float)
    model_decision: Mapped[str] = mapped_column(String(10))  # before rules
    decision: Mapped[str] = mapped_column(String(10))        # final, after rules
    flagged: Mapped[bool] = mapped_column(Boolean, index=True)
    rules_triggered: Mapped[list] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(20))