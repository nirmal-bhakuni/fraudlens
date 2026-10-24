"""Request and response shapes. FastAPI uses these to check input."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ml.features import CATEGORIES

# Literal[("a", "b")] means the same as Literal["a", "b"].
# A wrong category gives a clear error that lists the allowed values.
Category = Literal[tuple(CATEGORIES)]


class TransactionIn(BaseModel):
    timestamp: datetime = Field(description="Local time of the purchase, e.g. 2020-12-30T23:15:00")
    amount: float = Field(gt=0, le=1_000_000)
    category: Category
    merchant: str | None = Field(default=None, max_length=100)
    lat: float = Field(ge=-90, le=90, description="Cardholder latitude")
    long: float = Field(ge=-180, le=180, description="Cardholder longitude")
    merchant_lat: float = Field(ge=-90, le=90)
    merchant_long: float = Field(ge=-180, le=180)
    city_pop: int = Field(ge=0, description="Population of the cardholder's city")


class ScoreOut(BaseModel):
    id: int
    risk_score: float
    decision: Literal["Approve", "Review", "Decline"]
    rules_triggered: list[str]
    model_version: str