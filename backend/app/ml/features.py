"""Turn raw transaction columns into model features.

The same function is used for training and (later) by the API,
so the model always sees the same features in the same order.
"""
import numpy as np
import pandas as pd

CATEGORIES = [
    "entertainment", "food_dining", "gas_transport", "grocery_net",
    "grocery_pos", "health_fitness", "home", "kids_pets", "misc_net",
    "misc_pos", "personal_care", "shopping_net", "shopping_pos", "travel",
]

# Raw columns a caller must provide for one transaction.
RAW_COLUMNS = [
    "trans_date_trans_time", "amt", "category",
    "lat", "long", "merch_lat", "merch_long", "city_pop",
]

NUMERIC_FEATURES = ["amt", "hour", "day_of_week", "is_night", "distance_km", "city_pop"]
FEATURE_COLUMNS = NUMERIC_FEATURES + [f"cat_{c}" for c in CATEGORIES]


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two points on Earth."""
    lat1, lon1, lat2, lon2 = (np.radians(v) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    unknown = set(df["category"].unique()) - set(CATEGORIES)
    if unknown:
        raise ValueError(f"Unknown category: {sorted(unknown)}")

    ts = pd.to_datetime(df["trans_date_trans_time"])
    out = pd.DataFrame(index=df.index)
    out["amt"] = df["amt"].astype(float)
    out["hour"] = ts.dt.hour
    out["day_of_week"] = ts.dt.dayofweek
    # Night = 22:00 to 03:59. We chose this after looking at TRAIN data only.
    out["is_night"] = ((out["hour"] >= 22) | (out["hour"] <= 3)).astype(int)
    out["distance_km"] = haversine_km(df["lat"], df["long"], df["merch_lat"], df["merch_long"])
    out["city_pop"] = df["city_pop"]
    for c in CATEGORIES:
        out[f"cat_{c}"] = (df["category"] == c).astype(int)
    return out[FEATURE_COLUMNS]