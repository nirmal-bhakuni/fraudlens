import pandas as pd
import pytest

from app.ml.features import CATEGORIES, FEATURE_COLUMNS, build_features


def make_row(**overrides):
    row = {
        "trans_date_trans_time": "2020-01-05 23:30:00",
        "amt": 100.0,
        "category": "shopping_net",
        "lat": 40.0, "long": -75.0,
        "merch_lat": 40.0, "merch_long": -75.0,
        "city_pop": 5000,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_columns_and_order():
    X = build_features(make_row())
    assert list(X.columns) == FEATURE_COLUMNS
    assert X.shape == (1, len(FEATURE_COLUMNS))


def test_category_is_one_hot():
    X = build_features(make_row(category="travel"))
    assert X["cat_travel"].iloc[0] == 1
    assert X[[f"cat_{c}" for c in CATEGORIES]].sum(axis=1).iloc[0] == 1


def test_night_flag_boundaries():
    assert build_features(make_row(trans_date_trans_time="2020-01-05 22:00:00"))["is_night"].iloc[0] == 1
    assert build_features(make_row(trans_date_trans_time="2020-01-05 03:59:00"))["is_night"].iloc[0] == 1
    assert build_features(make_row(trans_date_trans_time="2020-01-05 04:00:00"))["is_night"].iloc[0] == 0
    assert build_features(make_row(trans_date_trans_time="2020-01-05 12:00:00"))["is_night"].iloc[0] == 0


def test_distance_zero_for_same_place():
    assert build_features(make_row())["distance_km"].iloc[0] == pytest.approx(0.0)


def test_distance_one_degree_latitude():
    X = build_features(make_row(merch_lat=41.0))
    assert X["distance_km"].iloc[0] == pytest.approx(111.19, abs=0.5)


def test_unknown_category_raises():
    with pytest.raises(ValueError):
        build_features(make_row(category="casino"))