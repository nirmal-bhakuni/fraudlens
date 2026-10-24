import math

import pandas as pd
import pytest

from app.ml.features import build_features
from app.ml.reasons import describe, top_reasons
from app.ml.scorer import get_scorer
from score_helpers import GOOD, post_score


def one_row(**changes):
    row = {
        "trans_date_trans_time": "2020-12-30 23:15:00", "amt": 1250.5,
        "category": "shopping_net", "lat": 36.08, "long": -81.18,
        "merch_lat": 36.01, "merch_long": -82.05, "city_pop": 3495,
    }
    row.update(changes)
    return build_features(pd.DataFrame([row]))


def test_contributions_add_up_to_the_score():
    scorer = get_scorer()
    features = one_row()
    values, bias = scorer.contributions(features)
    assert len(values) == len(features.columns)
    rebuilt = 1 / (1 + math.exp(-(bias + values.sum())))
    assert rebuilt == pytest.approx(scorer.score(features), abs=1e-4)


def test_top_reasons_are_sorted_and_limited():
    scorer = get_scorer()
    features = one_row()
    values, _ = scorer.contributions(features)
    reasons = top_reasons(values, features, n=5)
    assert 1 <= len(reasons) <= 5
    impacts = [abs(r["impact"]) for r in reasons]
    assert impacts == sorted(impacts, reverse=True)
    for r in reasons:
        assert (r["impact"] > 0) == (r["direction"] == "increases risk")
        assert r["text"]


def test_describe_texts():
    assert describe("amt", 1250.5) == "Amount is $1,250.50"
    assert describe("is_night", 1) == "Purchase is at night (22:00-03:59)"
    assert describe("is_night", 0) == "Purchase is not at night"
    assert describe("cat_travel", 0) == "Category is not travel"
    assert describe("hour", 23) == "Purchase hour is 23:00"


def test_score_response_has_reasons_and_replay_keeps_them(client):
    first = post_score(client, GOOD, key="r-1").json()
    assert 1 <= len(first["reasons"]) <= 5
    assert {"feature", "text", "direction", "impact"} <= set(first["reasons"][0])
    second = post_score(client, GOOD, key="r-1").json()
    assert second["reasons"] == first["reasons"]


def test_detail_includes_reasons(client):
    created = post_score(client, GOOD, key="r-2").json()
    detail = client.get(f"/transactions/{created['id']}").json()
    assert detail["reasons"] == created["reasons"]