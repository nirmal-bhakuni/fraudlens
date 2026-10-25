"""Fill the dashboard with real rows from the TEST file (never used for training).

The API must be running. Run from the repo root:   python scripts\seed_demo.py
Safe to repeat: every row has an Idempotency-Key, so nothing is duplicated.

The sample has 20 fraud rows and 30 normal rows. That is NOT the real fraud rate (0.39%),
so numbers from this demo are NOT accuracy numbers.
"""
import os
import sys
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "raw" / "fraudTest.csv"
API = os.getenv("FRAUDLENS_API_URL", "http://127.0.0.1:8000")
KEY = os.getenv("FRAUDLENS_API_KEY", "dev-key-change-me")
# Only the columns we need. Names, street and date of birth are never loaded.
COLUMNS = [
    "trans_date_trans_time", "merchant", "category", "amt", "lat", "long",
    "merch_lat", "merch_long", "city_pop", "trans_num", "is_fraud",
]


def main() -> None:
    if not CSV.exists():
        sys.exit(f"Missing {CSV}. See the download steps in README.md")

    df = pd.read_csv(CSV, usecols=COLUMNS, parse_dates=["trans_date_trans_time"])
    fraud = df[df["is_fraud"] == 1].sample(20, random_state=42)
    legit = df[df["is_fraud"] == 0].sample(30, random_state=42)
    sample = pd.concat([fraud, legit]).sort_values("trans_date_trans_time")

    created = replayed = 0
    decisions: dict[str, int] = {}
    fraud_flagged = legit_flagged = 0

    try:
        with httpx.Client(base_url=API, headers={"X-API-Key": KEY}, timeout=30) as client:
            for row in sample.itertuples():
                payload = {
                    "timestamp": row.trans_date_trans_time.isoformat(),
                    "amount": float(row.amt),
                    "category": row.category,
                    "merchant": str(row.merchant).removeprefix("fraud_")[:100],
                    "lat": float(row.lat),
                    "long": float(row.long),
                    "merchant_lat": float(row.merch_lat),
                    "merchant_long": float(row.merch_long),
                    "city_pop": int(row.city_pop),
                }
                response = client.post(
                    "/transactions/score", json=payload,
                    headers={"Idempotency-Key": f"seed-{row.trans_num}"},
                )
                if response.status_code not in (200, 201):
                    sys.exit(f"Stopped: HTTP {response.status_code} {response.text[:200]}")
                if response.status_code == 201:
                    created += 1
                else:
                    replayed += 1
                decision = response.json()["decision"]
                decisions[decision] = decisions.get(decision, 0) + 1
                if decision != "Approve":
                    if row.is_fraud == 1:
                        fraud_flagged += 1
                    else:
                        legit_flagged += 1
    except httpx.ConnectError:
        sys.exit(f"Cannot reach the API at {API}. Start it first: .\\scripts\\start-api.ps1")

    print(f"New: {created}   Already existed: {replayed}")
    print(f"Decisions: {decisions}")
    print(f"Of 20 rows labeled fraud, flagged (Review or Decline): {fraud_flagged}")
    print(f"Of 30 normal rows, flagged (false alarms): {legit_flagged}")
    print("Reminder: this sample over-represents fraud. These are demo numbers, not accuracy.")


if __name__ == "__main__":
    main()