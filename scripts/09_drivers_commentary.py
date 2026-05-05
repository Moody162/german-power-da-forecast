"""
Automated drivers commentary: passes computed pipeline metrics to an LLM
and saves the resulting narrative to outputs/tables/drivers_commentary.md.

Every API call is logged (prompt, response, status, latency, token counts)
to outputs/logs/llm_calls.jsonl. The LLM receives only numbers that exist
in the input files — it never invents figures.

Usage:
    uv run python scripts/09_drivers_commentary.py

Inputs:
    outputs/tables/cv_metrics.csv
    outputs/tables/curve_views.json
    outputs/tables/prompt_curve_view.json

Outputs:
    outputs/tables/drivers_commentary.md
    outputs/logs/llm_calls.jsonl
"""

import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from src.ai.commentary import run

PROJECT_ROOT  = Path(__file__).resolve().parents[1]
CV_PATH       = PROJECT_ROOT / "outputs" / "tables" / "cv_metrics.csv"
CURVE_PATH    = PROJECT_ROOT / "outputs" / "tables" / "curve_views.json"
PCV_PATH      = PROJECT_ROOT / "outputs" / "tables" / "prompt_curve_view.json"
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "features.parquet"
FI_PATH       = PROJECT_ROOT / "outputs" / "tables" / "feature_importance.csv"
LOG_PATH      = PROJECT_ROOT / "outputs" / "logs" / "llm_calls.jsonl"
OUTPUT_PATH   = PROJECT_ROOT / "outputs" / "tables" / "drivers_commentary.md"


def main() -> None:
    print(f"Loading CV metrics        : {CV_PATH}")
    cv = pd.read_csv(CV_PATH)

    print(f"Loading curve views       : {CURVE_PATH}")
    with open(CURVE_PATH) as f:
        curve_views = json.load(f)

    print(f"Loading prompt curve view : {PCV_PATH}")
    with open(PCV_PATH) as f:
        prompt_curve_view = json.load(f)

    print(f"Loading features          : {FEATURES_PATH}")
    features = pd.read_parquet(FEATURES_PATH)

    print(f"Loading feature importance: {FI_PATH}")
    feature_importance = pd.read_csv(FI_PATH)

    print("\nCalling LLM ...")
    commentary = run(
        cv, curve_views, prompt_curve_view,
        features, feature_importance,
        LOG_PATH, OUTPUT_PATH,
    )

    print(f"\nCommentary saved → {OUTPUT_PATH}")
    print(f"Log appended     → {LOG_PATH}")
    print("\n" + "-" * 60)
    print(commentary)


if __name__ == "__main__":
    main()
