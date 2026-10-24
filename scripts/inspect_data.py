"""Inspect the Sparkov dataset: shape, columns, missing values, fraud rate."""
import sys
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")

EXPECTED_COLUMNS = [
    "trans_date_trans_time", "cc_num", "merchant", "category", "amt",
    "first", "last", "gender", "street", "city", "state", "zip",
    "lat", "long", "city_pop", "job", "dob", "trans_num", "unix_time",
    "merch_lat", "merch_long", "is_fraud",
]


def load(name: str) -> pd.DataFrame:
    path = RAW_DIR / name
    if not path.exists():
        sys.exit(f"Missing file: {path}. See the download steps in README.md")
    # The first column in the file is an unnamed row index, so we drop it.
    return pd.read_csv(path, index_col=0, parse_dates=["trans_date_trans_time"])


def inspect(name: str) -> None:
    df = load(name)
    print("=" * 60)
    print(name)
    print("=" * 60)
    print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
    print(f"Missing expected columns: {missing or 'none'}")
    print(f"Unexpected extra columns: {extra or 'none'}")

    print("\nColumn types:")
    print(df.dtypes.to_string())

    print("\nColumns with missing values:")
    nulls = df.isna().sum()
    print(nulls[nulls > 0].to_string() if nulls.any() else "none")

    fraud = int(df["is_fraud"].sum())
    print(f"\nFraud rows: {fraud:,} of {len(df):,} ({fraud / len(df):.3%})")
    print(f"Accuracy of a model that always says 'not fraud': {1 - fraud / len(df):.3%}")

    ts = df["trans_date_trans_time"]
    print(f"\nDate range: {ts.min()}  to  {ts.max()}")
    print(f"Unique cards: {df['cc_num'].nunique():,}")
    print(f"Unique merchants: {df['merchant'].nunique():,}")
    print(f"Duplicate trans_num: {df['trans_num'].duplicated().sum():,}")

    print("\nAmount summary (all):")
    print(df["amt"].describe().round(2).to_string())
    print("\nMean amount, legit vs fraud:")
    print(df.groupby("is_fraud")["amt"].mean().round(2).to_string())

    print("\nFraud rate by category (highest first):")
    by_cat = df.groupby("category")["is_fraud"].agg(["mean", "sum", "count"])
    print(by_cat.sort_values("mean", ascending=False).round(4).to_string())

    print("\nFraud rate by hour of day:")
    by_hour = df.groupby(ts.dt.hour)["is_fraud"].mean()
    print(by_hour.round(4).to_string())

    print("\nSample rows (no personal columns):")
    safe_cols = ["trans_date_trans_time", "merchant", "category", "amt", "state", "is_fraud"]
    print(df[safe_cols].head(5).to_string())
    print()


if __name__ == "__main__":
    inspect("fraudTrain.csv")
    inspect("fraudTest.csv")
    