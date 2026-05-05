"""
Runs the full pipeline from scratch.
Deletes all generated outputs before starting so every run is reproducible.

Usage:
    uv run run_pipeline.py                 # clean + full run
    uv run run_pipeline.py --skip-ingest   # reuse existing raw data (faster)
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
    ("01_ingest.py",               "Ingesting data from ENTSO-E (~15 min)"),
    ("02_merge.py",                "Merging series"),
    ("03_qa.py",                   "Running QA checks"),
    ("04_clean.py",                "Cleaning and imputing"),
    ("05_features.py",             "Engineering features"),
    ("06_train.py",                "Training model"),
    ("07_curve.py",                "Running recursive forecast"),
    ("08_curve_view.py",           "Building curve view"),
    ("09_drivers_commentary.py",   "Generating LLM commentary"),
]


def clean(skip_ingest: bool) -> None:
    print("=== Cleaning generated outputs ===")
    for d in CLEAN_DIRS:
        if d.exists():
            shutil.rmtree(d)
            print(f"  removed {d.relative_to(PROJECT_ROOT)}")
    if not skip_ingest:
        raw = PROJECT_ROOT / "data" / "raw"
        if raw.exists():
            shutil.rmtree(raw)
            print(f"  removed data/raw")


def run_script(name: str, label: str, step: int, total: int) -> None:
    print(f"\n[{step}/{total}] {label}...")
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / name)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"\nPipeline failed at step {step} ({name}). Exiting.")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion and reuse existing raw data.",
    )
    args = parser.parse_args()

    clean(args.skip_ingest)

    scripts = SCRIPTS if not args.skip_ingest else SCRIPTS[1:]
    total = len(SCRIPTS)

    print("\n=== Running pipeline ===")

    if args.skip_ingest:
        print(f"\n[1/{total}] Skipping ingestion (--skip-ingest)")

    for i, (name, label) in enumerate(scripts, start=1 if not args.skip_ingest else 2):
        run_script(name, label, i, total)

    print("\n=== Pipeline complete ===")


if __name__ == "__main__":
    main()
