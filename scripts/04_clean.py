"""
Cleaning layer: reads merged.parquet, imputes small forecast gaps, writes
merged_clean.parquet and an imputation log.

Usage:
    python scripts/04_clean.py

Inputs:
    data/processed/merged.parquet

Outputs:
    data/processed/merged_clean.parquet
    data/qa/impute_log.json
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.qa.impute import FORECAST_COLS, impute_forecast_gaps

PROJECT_ROOT    = Path(__file__).resolve().parents[1]
MERGED_PATH     = PROJECT_ROOT / "data" / "processed" / "merged.parquet"
CLEAN_PATH      = PROJECT_ROOT / "data" / "processed" / "merged_clean.parquet"
IMPUTE_LOG_PATH = PROJECT_ROOT / "data" / "qa" / "impute_log.json"


def main() -> None:
    print(f"Loading {MERGED_PATH} ...")
    df = pd.read_parquet(MERGED_PATH)
    print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")

    null_before = {col: int(df[col].isna().sum()) for col in FORECAST_COLS if col in df.columns}
    print(f"\nNaN in forecast columns before cleaning:")
    for col, n in null_before.items():
        print(f"  {col:<30} {n}")

    print("\nImputing ...")
    cleaned, log = impute_forecast_gaps(df)

    null_after = {col: int(cleaned[col].isna().sum()) for col in FORECAST_COLS if col in cleaned.columns}
    print(f"\nNaN in forecast columns after cleaning:")
    for col, n in null_after.items():
        tag = " ✓ resolved" if null_before.get(col, 0) > 0 and n == 0 else ""
        print(f"  {col:<30} {n}{tag}")

    residual = {col: n for col, n in null_after.items() if n > 0}
    if residual:
        print(f"\nWARNING: {sum(residual.values())} NaN remain after imputation "
              f"(gaps exceed {72}h limit): {residual}")

    print(f"\n{len(log)} cell(s) imputed across {len({e['column'] for e in log})} column(s)")

    IMPUTE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(IMPUTE_LOG_PATH, "w") as fh:
        json.dump({"imputed_count": len(log), "entries": log}, fh, indent=2)
    print(f"Imputation log → {IMPUTE_LOG_PATH}")

    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(CLEAN_PATH)
    print(f"Saved → {CLEAN_PATH}")

    sys.stdout.flush()
    print("\nRunning QA on cleaned data...")
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "03_qa.py"),
         "--input", str(CLEAN_PATH), "--label", "qa_report_clean"],
        check=False,
    )
    if result.returncode != 0:
        print("QA found critical failures in cleaned data — review reports.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
