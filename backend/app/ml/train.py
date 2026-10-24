"""Train the FraudLens model.

Run from the backend folder:   python -m app.ml.train
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, precision_recall_curve

from app.ml.features import CATEGORIES, FEATURE_COLUMNS, RAW_COLUMNS, build_features

ROOT = Path(__file__).resolve().parents[3]  # repo root
DATA_DIR = ROOT / "data" / "raw"
MODELS_DIR = ROOT / "backend" / "models"

# Last ~2 months of the training file are used as validation (time-based).
VALIDATION_START = pd.Timestamp("2020-04-21")
# Business choices (our assumptions, not facts):
TARGET_DECLINE_PRECISION = 0.90  # auto-decline only when we are right 9 times out of 10
TARGET_REVIEW_RECALL = 0.80      # decline + review together should catch 80% of fraud


def load(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"Missing {path}. See download steps in README.md")
    # usecols: personal columns (names, street, dob) are never loaded.
    return pd.read_csv(
        path,
        usecols=RAW_COLUMNS + ["is_fraud"],
        parse_dates=["trans_date_trans_time"],
    )


def make_model(scale_pos_weight: float) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        tree_method="hist",
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )


def pick_thresholds(y_true, scores):
    """Choose review and decline thresholds using VALIDATION data only."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    precision, recall = precision[:-1], recall[:-1]  # line up with thresholds

    ok = np.where(precision >= TARGET_DECLINE_PRECISION)[0]
    decline_t = float(thresholds[ok[0]]) if len(ok) else float(thresholds[-1])

    ok = np.where(recall >= TARGET_REVIEW_RECALL)[0]
    review_t = float(thresholds[ok[-1]]) if len(ok) else float(thresholds[0])

    return min(review_t, decline_t), decline_t


def evaluate(y, scores, review_t, decline_t) -> dict:
    decision = np.where(scores >= decline_t, "Decline",
                        np.where(scores >= review_t, "Review", "Approve"))
    total_fraud = int(y.sum())
    result = {
        "pr_auc": float(average_precision_score(y, scores)),
        "baseline_pr_auc": float(y.mean()),  # what random guessing would score
        "counts": {d: int((decision == d).sum()) for d in ("Approve", "Review", "Decline")},
    }
    for name, mask in (("decline", decision == "Decline"), ("flagged", decision != "Approve")):
        n = int(mask.sum())
        caught = int(y[mask].sum())
        result[name] = {
            "count": n,
            "fraud_caught": caught,
            "precision": caught / n if n else 0.0,
            "recall": caught / total_fraud,
        }
    return result


def print_report(title: str, m: dict) -> None:
    print(f"\n{title}")
    print(f"  PR-AUC: {m['pr_auc']:.3f}   (random guessing would give {m['baseline_pr_auc']:.4f})")
    print(f"  Decisions: {m['counts']}")
    for name in ("decline", "flagged"):
        s = m[name]
        print(f"  {name:8s} n={s['count']:>7,}  fraud caught={s['fraud_caught']:>5,}  "
              f"precision={s['precision']:.3f}  recall={s['recall']:.3f}")


def main(model_version: str) -> None:
    print("Loading data...")
    train = load("fraudTrain.csv")
    test = load("fraudTest.csv")

    is_val = train["trans_date_trans_time"] >= VALIDATION_START
    fit_df, val_df = train[~is_val], train[is_val]
    print(f"Fit rows: {len(fit_df):,}  Validation rows: {len(val_df):,}  Test rows: {len(test):,}")

    X_fit, y_fit = build_features(fit_df), fit_df["is_fraud"].to_numpy()
    X_val, y_val = build_features(val_df), val_df["is_fraud"].to_numpy()
    X_test, y_test = build_features(test), test["is_fraud"].to_numpy()

    # Class imbalance: try 3 weights for the rare fraud class, keep the best on validation.
    ratio = float((y_fit == 0).sum() / (y_fit == 1).sum())
    candidates = {"none": 1.0, "sqrt": float(np.sqrt(ratio)), "full": ratio}

    print("\nComparing imbalance settings (validation PR-AUC, higher is better):")
    results = []
    for label, weight in candidates.items():
        model = make_model(weight)
        model.fit(X_fit, y_fit)
        val_scores = model.predict_proba(X_val)[:, 1]
        pr_auc = float(average_precision_score(y_val, val_scores))
        print(f"  {label:5s} scale_pos_weight={weight:7.1f}   PR-AUC={pr_auc:.3f}")
        results.append((pr_auc, label, weight, model, val_scores))

    best_pr_auc, best_label, best_weight, model, val_scores = max(results, key=lambda r: r[0])
    print(f"\nChosen: {best_label} (weight {best_weight:.1f})")

    review_t, decline_t = pick_thresholds(y_val, val_scores)
    print(f"Thresholds from validation: review >= {review_t:.4f}, decline >= {decline_t:.4f}")

    val_metrics = evaluate(y_val, val_scores, review_t, decline_t)
    # The test set is used ONCE, with thresholds already fixed.
    test_scores = model.predict_proba(X_test)[:, 1]
    test_metrics = evaluate(y_test, test_scores, review_t, decline_t)

    print_report("VALIDATION (used to choose thresholds, so slightly optimistic)", val_metrics)
    print_report("TEST (untouched until now)", test_metrics)

    out_dir = MODELS_DIR / model_version
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(out_dir / "model.json"))
    metadata = {
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "XGBClassifier",
        "features": FEATURE_COLUMNS,
        "categories": CATEGORIES,
        "imbalance": {
            "chosen": best_label,
            "scale_pos_weight": best_weight,
            "validation_pr_auc_by_option": {r[1]: r[0] for r in results},
        },
        "thresholds": {"review": review_t, "decline": decline_t},
        "targets": {
            "decline_precision": TARGET_DECLINE_PRECISION,
            "review_recall": TARGET_REVIEW_RECALL,
        },
        "split": {
            "validation_start": str(VALIDATION_START.date()),
            "fit_rows": len(fit_df),
            "validation_rows": len(val_df),
            "test_rows": len(test),
        },
        "metrics": {"validation": val_metrics, "test": test_metrics},
        "note": "Trained on public SIMULATED data (Sparkov). Not proof of real-world accuracy.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\nSaved model and metadata to {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", default="1.0.0")
    main(parser.parse_args().model_version)