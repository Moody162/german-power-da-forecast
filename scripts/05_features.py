"""
Feature engineering stage: loads merged_clean.parquet, builds all features,
writes features.parquet.

Usage:
    python scripts/05_features.py

Input:  data/processed/merged_clean.parquet
Output: data/processed/features.parquet
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.engineer import FEATURE_COLS, TARGET_COL, build_features

PROJECT_ROOT   = Path(__file__).resolve().parents[1]
CLEAN_PATH     = PROJECT_ROOT / "data" / "processed" / "merged_clean.parquet"
FEATURES_PATH  = PROJECT_ROOT / "data" / "processed" / "features.parquet"


def main() -> None:
    print(f"Loading {CLEAN_PATH} ...")
    df = pd.read_parquet(CLEAN_PATH)
    print(f"  Input shape: {df.shape[0]:,} rows × {df.shape[1]} columns")

    print("Building features ...")
    features = build_features(df)
    print(f"  Output shape: {features.shape[0]:,} rows × {features.shape[1]} columns")

    rows_dropped = len(df) - len(features)
    print(f"  Rows dropped (lag warm-up): {rows_dropped} ({rows_dropped}h = {rows_dropped/24:.1f} days)")

    train = features[features["dataset"] == "train"]
    test  = features[features["dataset"] == "test"]
    print(f"\n  Train rows : {len(train):,}  ({train.index[0].date()} → {train.index[-1].date()})")
    print(f"  Test rows  : {len(test):,}  ({test.index[0].date()} → {test.index[-1].date()})")

    print(f"\nFeature columns ({len(FEATURE_COLS)}):")
    for col in FEATURE_COLS:
        null_n = int(features[col].isna().sum())
        print(f"  {col:<30}  nulls={null_n}")

    FEATURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(FEATURES_PATH)
    print(f"\nSaved → {FEATURES_PATH}")


if __name__ == "__main__":
    main()
