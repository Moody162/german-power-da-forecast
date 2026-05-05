"""
Runs the full pipeline from scratch.
Deletes all generated outputs (except raw data) before starting so every
run is reproducible. Ingestion is incremental — only missing data is fetched.

Usage:
    uv run run_pipeline.py              # clean outputs, keep raw data (incremental ingest)
    uv run run_pipeline.py --full-clean # delete everything including raw data (full re-ingest)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

CLEAN_DIRS = [
    PROJECT_ROOT / "data" / "processed",
    PROJECT_ROOT / "data" / "qa",
    PROJECT_ROOT / "outputs" / "figures",
    PROJECT_ROOT / "outputs" / "tables",
    PROJECT_ROOT / "outputs" / "predictions",
    PROJECT_ROOT / "outputs" / "reports",
    PROJECT_ROOT / "outputs" / "logs",
    PROJECT_ROOT / "outputs" / "models",
]

SCRIPTS = [
    ("01_ingest.py",             "Ingesting data from ENTSO-E (incremental)"),
    ("02_merge.py",              "Merging series"),
    ("03_qa.py",                 "Running QA checks"),
    ("04_clean.py",              "Cleaning and imputing"),
    ("05_features.py",           "Engineering features"),
    ("06_train.py",              "Training model"),
    ("07_curve.py",              "Running recursive forecast"),
    ("08_curve_view.py",         "Building curve view"),
    ("09_drivers_commentary.py", "Generating LLM commentary"),
]


def clean(full: bool) -> None:
    print("=== Cleaning generated outputs ===")
    for d in CLEAN_DIRS:
        if d.exists():
            shutil.rmtree(d)
            print(f"  removed {d.relative_to(PROJECT_ROOT)}")
    if full:
        raw = PROJECT_ROOT / "data" / "raw"
        if raw.exists():
            shutil.rmtree(raw)
            print(f"  removed data/raw")


def run_script(name: str, label: str, step: int, total: int, extra_args: list[str] | None = None) -> None:
    print(f"\n[{step}/{total}] {label}...")
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / name)] + (extra_args or [])
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\nPipeline failed at step {step} ({name}). Exiting.")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-clean",
        action="store_true",
        help="Also delete raw data, forcing a full re-ingest from ENTSO-E (~15 min).",
    )
    args = parser.parse_args()

    clean(full=args.full_clean)
    print("\n=== Running pipeline ===")
    for i, (name, label) in enumerate(SCRIPTS, start=1):
        extra = ["--no-fail"] if name == "03_qa.py" else None
        run_script(name, label, i, len(SCRIPTS), extra_args=extra)
    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()
