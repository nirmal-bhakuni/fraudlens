"""Database table for scored transactions."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"
    # The database itself stops duplicates. This also makes the lookup fast.
    __table_args__ = (
        UniqueConstraint("client_id", "idempotency_key", name="uq_client_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Who sent it, and the idempotency data
    client_id: Mapped[str] = mapped_column(String(16), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))  # detects same key + different body

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
    reasons: Mapped[list] = mapped_column(JSON, default=list)  # top SHAP reasons
    model_version: Mapped[str] = mapped_column(String(20))