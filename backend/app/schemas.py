"""Request and response shapes. FastAPI uses these to check input."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ml.features import CATEGORIES

# Literal[("a", "b")] means the same as Literal["a", "b"].
# A wrong category gives a clear error that lists the allowed values.
Category = Literal[tuple(CATEGORIES)]
Decision = Literal["Approve", "Review", "Decline"]


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


class Reason(BaseModel):
    feature: str
    text: str
    direction: Literal["increases risk", "decreases risk"]
    impact: float = Field(description="Effect on the score in log-odds units, not probability")


class ScoreOut(BaseModel):
    id: int
    risk_score: float
    decision: Decision
    rules_triggered: list[str]
    reasons: list[Reason]
    model_version: str


class TransactionOut(BaseModel):
    """A saved transaction, as shown in the list and detail endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    timestamp: datetime = Field(validation_alias="trans_time")
    amount: float
    category: str
    merchant: str | None
    lat: float
    long: float
    merchant_lat: float
    merchant_long: float
    city_pop: int
    risk_score: float
    model_decision: Decision
    decision: Decision
    flagged: bool
    rules_triggered: list[str]
    reasons: list[Reason]
    model_version: str


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class ExplainIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str | None = Field(
        default=None, min_length=3, max_length=300,
        description="Optional. Leave empty to ask why this transaction got its decision.",
    )


class Source(BaseModel):
    source: str
    title: str
    score: float
    text: str


class ExplainOut(BaseModel):
    transaction_id: int
    decision: Decision          # unchanged: the explanation never changes it
    answered: bool              # False = "I don't have enough information"
    answer: str
    sources: list[Source]       # the passages that were given to the model
    llm_model: str | None       # None when the LLM was not called