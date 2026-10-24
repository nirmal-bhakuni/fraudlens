"""Turn model contributions (TreeSHAP) into short reasons a person can read."""
import numpy as np
import pandas as pd

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MIN_IMPACT = 0.001  # ignore effects too small to matter


def describe(feature: str, value: float) -> str:
    if feature == "amt":
        return f"Amount is ${value:,.2f}"
    if feature == "hour":
        return f"Purchase hour is {int(value):02d}:00"
    if feature == "day_of_week":
        return f"Purchase day is {DAY_NAMES[int(value)]}"
    if feature == "is_night":
        return "Purchase is at night (22:00-03:59)" if value else "Purchase is not at night"
    if feature == "distance_km":
        return f"Merchant is {value:,.0f} km from the cardholder"
    if feature == "city_pop":
        return f"Cardholder's city has {int(value):,} people"
    if feature.startswith("cat_"):
        name = feature[len("cat_"):]
        return f"Category is {name}" if value else f"Category is not {name}"
    return f"{feature} = {value}"


def top_reasons(contributions: np.ndarray, features: pd.DataFrame, n: int = 5) -> list[dict]:
    """The n features that moved the score most (up or down).

    `contributions` has one value per column of `features`, in the same order.
    """
    row = features.iloc[0]
    order = np.argsort(-np.abs(contributions))
    reasons = []
    for i in order:
        impact = float(contributions[i])
        if abs(impact) < MIN_IMPACT:
            continue
        feature = features.columns[i]
        reasons.append({
            "feature": feature,
            "text": describe(feature, float(row[feature])),
            "direction": "increases risk" if impact > 0 else "decreases risk",
            "impact": round(impact, 3),
        })
        if len(reasons) == n:
            break
    return reasons