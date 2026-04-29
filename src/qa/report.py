"""
Report generation from a list of QAResult objects.

Produces:
  - data/qa/qa_report.json  — machine-readable full results
  - data/qa/qa_report.md    — human-readable summary with a per-category table
"""

from __future__ import annotations

import json
from pathlib import Path

from src.qa.checks import QAResult

_SEV_ICON = {"critical": "🔴", "warning": "🟡", "info": "🟢"}
_PASS_ICON = {True: "✓", False: "✗"}


def _results_to_dict(results: list[QAResult]) -> list[dict]:
    return [
        {
            "name":     r.name,
            "category": r.category,
            "severity": r.severity,
            "passed":   r.passed,
            "message":  r.message,
            "details":  r.details,
        }
        for r in results
    ]


def write_json(results: list[QAResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(_results_to_dict(results), fh, indent=2, default=str)


def write_markdown(results: list[QAResult], path: Path, dataset_shape: tuple) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    n_critical_fail = sum(1 for r in results if r.severity == "critical" and not r.passed)
    n_warn_fail     = sum(1 for r in results if r.severity == "warning"  and not r.passed)
    n_total         = len(results)

    lines: list[str] = []
    lines.append("# QA Report\n")
    lines.append(f"**Dataset shape**: {dataset_shape[0]:,} rows × {dataset_shape[1]} columns\n")
    lines.append(f"**Checks run**: {n_total}  |  "
                 f"**Critical failures**: {n_critical_fail}  |  "
                 f"**Warnings**: {n_warn_fail}\n")

    categories = list(dict.fromkeys(r.category for r in results))
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        lines.append(f"\n## {cat.replace('_', ' ').title()}\n")
        lines.append("| Check | Severity | Passed | Message |")
        lines.append("|-------|----------|--------|---------|")
        for r in cat_results:
            icon = _SEV_ICON.get(r.severity, "")
            tick = _PASS_ICON[r.passed]
            lines.append(f"| `{r.name}` | {icon} {r.severity} | {tick} | {r.message} |")

    # Append details for non-info checks that failed
    failed = [r for r in results if not r.passed and r.severity != "info"]
    if failed:
        lines.append("\n## Failure Details\n")
        for r in failed:
            lines.append(f"### `{r.name}`\n")
            lines.append(f"```json\n{json.dumps(r.details, indent=2, default=str)}\n```\n")

    path.write_text("\n".join(lines) + "\n")


def summarise(results: list[QAResult]) -> None:
    """Print a compact summary to stdout."""
    categories = list(dict.fromkeys(r.category for r in results))
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        fails = [r for r in cat_results if not r.passed]
        tag = f"[{cat}]"
        if not fails:
            print(f"  {tag:<30} all {len(cat_results)} checks passed")
        else:
            for r in fails:
                icon = _SEV_ICON.get(r.severity, "")
                print(f"  {tag:<30} {icon} FAIL  {r.name}: {r.message}")
