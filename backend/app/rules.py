"""Simple safety rules.

Rules can only make a decision STRICTER (Approve -> Review).
They never lower a decision and never create a Decline.
The thresholds are our own assumptions, not facts from the data.
"""

HIGH_AMOUNT = 5000.0
NIGHT_AMOUNT = 1000.0


def check_rules(amount: float, is_night: bool) -> list[str]:
    hits = []
    if amount >= HIGH_AMOUNT:
        hits.append("high_amount")
    if amount >= NIGHT_AMOUNT and is_night:
        hits.append("high_amount_at_night")
    return hits


def apply_rules(model_decision: str, hits: list[str]) -> str:
    if hits and model_decision == "Approve":
        return "Review"
    return model_decision