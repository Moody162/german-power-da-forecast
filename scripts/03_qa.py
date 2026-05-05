"""
Runs all data quality checks on a merged parquet and writes JSON and Markdown
reports. Exits non-zero if any critical check fails. Called directly on
merged.parquet and again by 04_clean.py on merged_clean.parquet.

Calls:
    src/qa/checks.py  (run_all_checks)
    src/qa/report.py  (summarise, write_json, write_markdown)

Inputs:
    data/processed/merged.parquet  (default; overridable via --input)

Outputs:
    data/qa/qa_report.json  (default stem; overridable via --label)
    data/qa/qa_report.md
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.qa.checks import run_all_checks
from src.qa.report import summarise, write_json, write_markdown

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QA_DIR       = PROJECT_ROOT / "data" / "qa"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QA checks on a merged parquet.")
    parser.add_argument(
        "--input", "-i",
        default=str(PROJECT_ROOT / "data" / "processed" / "merged.parquet"),
        help="Path to the parquet file to check (default: data/processed/merged.parquet)",
    )
    parser.add_argument(
        "--label", "-l",
        default="qa_report",
        help="Output filename stem, e.g. 'qa_report' or 'qa_report_clean' (default: qa_report)",
    )
    parser.add_argument(
        "--no-fail", action="store_true",
        help="Write reports but do not exit non-zero on critical failures.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    json_path  = QA_DIR / f"{args.label}.json"
    md_path    = QA_DIR / f"{args.label}.md"

    print(f"Loading {input_path} ...")
    df = pd.read_parquet(input_path)
    print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n")

    print("Running checks...")
    results = run_all_checks(df)

    print("\nResults:")
    summarise(results)

    write_json(results, json_path)
    write_markdown(results, md_path, df.shape)
    print(f"\nReports written:\n  {json_path}\n  {md_path}")

    critical_failures = [r for r in results if r.severity == "critical" and not r.passed]
    if critical_failures:
        print(f"\n{len(critical_failures)} critical check(s) failed:")
        for r in critical_failures:
            print(f"  ✗ {r.name}: {r.message}")
        if not args.no_fail:
            sys.exit(1)
    else:
        print("\nAll critical checks passed.")


if __name__ == "__main__":
    main()
