from app.ml.scorer import get_scorer
from app.rules import apply_rules, check_rules


def test_no_rules_for_small_amount():
    assert check_rules(50.0, is_night=True) == []


def test_high_amount_rule():
    assert check_rules(5000.0, is_night=False) == ["high_amount"]


def test_high_amount_at_night_rule():
    assert check_rules(1200.0, is_night=True) == ["high_amount_at_night"]
    assert check_rules(1200.0, is_night=False) == []


def test_rules_can_raise_approve_to_review():
    assert apply_rules("Approve", ["high_amount"]) == "Review"


def test_rules_never_lower_or_create_decline():
    assert apply_rules("Decline", ["high_amount"]) == "Decline"
    assert apply_rules("Review", ["high_amount"]) == "Review"
    assert apply_rules("Approve", []) == "Approve"


def test_model_decision_bounds():
    scorer = get_scorer()
    assert scorer.decide(0.0) == "Approve"
    assert scorer.decide(1.0) == "Decline"
    assert scorer.decide(scorer.decline_threshold) == "Decline"