"""
QA check functions for the merged ENTSO-E dataset.

Each public function returns list[QAResult]. Severity policy:
  critical — data is unusable; pipeline should not proceed
  warning  — quality issue; proceed with caution
  info     — statistics and coverage summaries; always passes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


# ── Result type ────────────────────────────────────────────────────────────

@dataclass
class QAResult:
    name: str
    category: str
    severity: Literal["critical", "warning", "info"]
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


# ── Helpers ────────────────────────────────────────────────────────────────

def _jsonify(obj: object) -> object:
    """Recursively convert numpy/pandas types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if obj is pd.NA:
        return None
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _largest_null_run(
    series: pd.Series,
) -> tuple[int, pd.Timestamp | None, pd.Timestamp | None]:
    """Return (length_hours, start_ts, end_ts) of the largest contiguous NaN run."""
    null_mask = series.isna()
    if not null_mask.any():
        return 0, None, None

    run_id = (null_mask != null_mask.shift()).cumsum()
    null_run_ids = run_id[null_mask]
    if null_run_ids.empty:
        return 0, None, None

    run_sizes = null_run_ids.groupby(null_run_ids).count()
    max_run_id = run_sizes.idxmax()
    max_size = int(run_sizes.max())
    gap_idx = null_run_ids[null_run_ids == max_run_id].index
    return max_size, gap_idx[0], gap_idx[-1]


# ── 1. Structural ──────────────────────────────────────────────────────────

EXPECTED_COLUMNS = [
    "timestamp_local",
    "da_price_eur_mwh",
    "wind_forecast_mw",
    "solar_forecast_mw",
    "load_forecast_mw",
    "wind_actual_mw",
    "solar_actual_mw",
    "load_actual_mw",
    "dataset",
]


def check_structural(df: pd.DataFrame) -> list[QAResult]:
    results: list[QAResult] = []

    # Monotonic index
    mono = bool(df.index.is_monotonic_increasing)
    results.append(QAResult(
        name="index_monotonic",
        category="structural",
        severity="critical",
        passed=mono,
        message="Index is monotonically increasing" if mono
                else "Index is NOT monotonically increasing",
    ))

    # No gaps in hourly frequency
    diffs = df.index.to_series().diff().dropna()
    bad = diffs[diffs != pd.Timedelta(hours=1)]
    results.append(QAResult(
        name="hourly_frequency",
        category="structural",
        severity="critical",
        passed=bad.empty,
        message="Hourly frequency intact" if bad.empty
                else f"{len(bad)} irregular interval(s) found",
        details=_jsonify({"irregular_at": [str(t) for t in bad.index[:5]]}) if not bad.empty else {},
    ))

    # All expected columns present
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    results.append(QAResult(
        name="columns_present",
        category="structural",
        severity="critical",
        passed=not missing,
        message="All expected columns present" if not missing
                else f"Missing columns: {missing}",
        details={"missing_columns": missing},
    ))

    # dataset column contains only valid labels
    found = set(df["dataset"].dropna().unique())
    valid = found <= {"train", "test"}
    results.append(QAResult(
        name="dataset_labels",
        category="structural",
        severity="critical",
        passed=valid,
        message="dataset column contains only valid labels" if valid
                else f"Unexpected labels: {found - {'train', 'test'}}",
        details=_jsonify({"labels_found": sorted(found)}),
    ))

    return results


# ── 2. Missingness ─────────────────────────────────────────────────────────

FORECAST_COLS = ["da_price_eur_mwh", "wind_forecast_mw", "solar_forecast_mw", "load_forecast_mw"]
ACTUAL_COLS   = ["wind_actual_mw", "solar_actual_mw", "load_actual_mw"]
GAP_CRITICAL_H = 24


def check_missingness(df: pd.DataFrame) -> list[QAResult]:
    results: list[QAResult] = []
    tt = df[df["dataset"].isin(["train", "test"])]

    # Zero NaN in price + forecast columns (critical)
    for col in FORECAST_COLS:
        n = int(tt[col].isna().sum())
        results.append(QAResult(
            name=f"no_nulls_{col}",
            category="missingness",
            severity="critical",
            passed=n == 0,
            message=f"{col}: {n} NaN in train+test",
            details={"null_count": n},
        ))

    # Actuals NaN — tolerated, reported as info
    for col in ACTUAL_COLS:
        n = int(tt[col].isna().sum())
        pct = round(100 * n / len(tt), 3)
        results.append(QAResult(
            name=f"nulls_{col}",
            category="missingness",
            severity="info",
            passed=True,
            message=f"{col}: {n} NaN ({pct}%) in train+test",
            details={"null_count": n, "null_pct": pct},
        ))

    # Largest contiguous gap per column
    for col in FORECAST_COLS:
        gap_len, gap_start, gap_end = _largest_null_run(tt[col])
        exceeds = gap_len > GAP_CRITICAL_H
        results.append(QAResult(
            name=f"max_gap_{col}",
            category="missingness",
            severity="critical" if exceeds else "info",
            passed=not exceeds,
            message=f"{col}: largest gap = {gap_len}h"
                    + (f" (exceeds {GAP_CRITICAL_H}h threshold)" if exceeds else ""),
            details=_jsonify({"gap_hours": gap_len, "gap_start": gap_start, "gap_end": gap_end}),
        ))

    for col in ACTUAL_COLS:
        gap_len, gap_start, gap_end = _largest_null_run(tt[col])
        exceeds = gap_len > GAP_CRITICAL_H
        results.append(QAResult(
            name=f"max_gap_{col}",
            category="missingness",
            severity="warning" if exceeds else "info",
            passed=not exceeds,
            message=f"{col}: largest gap = {gap_len}h"
                    + (f" (exceeds {GAP_CRITICAL_H}h threshold)" if exceeds else ""),
            details=_jsonify({"gap_hours": gap_len, "gap_start": gap_start, "gap_end": gap_end}),
        ))

    # Per-month missingness summary (info)
    month_key = df["timestamp_local"].dt.tz_localize(None).dt.to_period("M").astype(str)
    monthly: dict[str, dict] = {}
    for col in FORECAST_COLS + ACTUAL_COLS:
        monthly[col] = _jsonify(
            df.groupby(month_key)[col].apply(lambda s: int(s.isna().sum())).to_dict()
        )
    results.append(QAResult(
        name="monthly_missingness",
        category="missingness",
        severity="info",
        passed=True,
        message="Per-month NaN counts per column",
        details=monthly,
    ))

    return results


# ── 3. Duplicates ──────────────────────────────────────────────────────────

def check_duplicates(df: pd.DataFrame) -> list[QAResult]:
    results: list[QAResult] = []

    # No duplicate UTC timestamps
    n_dup = int(df.index.duplicated().sum())
    results.append(QAResult(
        name="no_duplicate_utc",
        category="duplicates",
        severity="critical",
        passed=n_dup == 0,
        message=f"{n_dup} duplicate timestamp_utc" if n_dup
                else "No duplicate UTC timestamps",
        details={"duplicate_count": n_dup},
    ))

    # DST hour counts per local calendar day
    local_dates = df["timestamp_local"].dt.date
    hours_per_day = df.groupby(local_dates).size()

    abnormal   = hours_per_day[hours_per_day != 24]
    spring     = abnormal[abnormal == 23]   # clock springs forward → 23-hour day
    autumn     = abnormal[abnormal == 25]   # clock falls back      → 25-hour day
    unexpected = abnormal[(abnormal != 23) & (abnormal != 25)]

    spring_wrong = [d for d in spring.index if d.month != 3]
    results.append(QAResult(
        name="dst_spring_days",
        category="duplicates",
        severity="critical" if spring_wrong else "info",
        passed=not spring_wrong,
        message=f"{len(spring)} 23-hour days found, all in March" if not spring_wrong
                else f"23-hour days outside March: {spring_wrong}",
        details=_jsonify({"spring_forward_dates": [str(d) for d in spring.index]}),
    ))

    autumn_wrong = [d for d in autumn.index if d.month != 10]
    results.append(QAResult(
        name="dst_autumn_days",
        category="duplicates",
        severity="critical" if autumn_wrong else "info",
        passed=not autumn_wrong,
        message=f"{len(autumn)} 25-hour days found, all in October" if not autumn_wrong
                else f"25-hour days outside October: {autumn_wrong}",
        details=_jsonify({"fall_back_dates": [str(d) for d in autumn.index]}),
    ))

    results.append(QAResult(
        name="no_unexpected_day_lengths",
        category="duplicates",
        severity="critical",
        passed=unexpected.empty,
        message="No days with unexpected hour counts" if unexpected.empty
                else f"{len(unexpected)} days with unexpected hour counts",
        details=_jsonify({"unexpected": {str(d): int(h) for d, h in unexpected.items()}}),
    ))

    return results


# ── 4. Value sanity ────────────────────────────────────────────────────────

_RANGE_CHECKS: list[tuple[str, float, float, Literal["critical", "warning", "info"]]] = [
    ("da_price_eur_mwh",   -500,  4000, "critical"),
    ("wind_forecast_mw",      0, 80000, "critical"),
    ("solar_forecast_mw",     0, 80000, "critical"),
    ("load_forecast_mw",  20000, 90000, "critical"),
    ("wind_actual_mw",        0, 80000, "critical"),
    ("solar_actual_mw",       0, 80000, "critical"),
    ("load_actual_mw",    20000, 90000, "critical"),
]


def check_value_sanity(df: pd.DataFrame) -> list[QAResult]:
    results: list[QAResult] = []

    for col, lo, hi, sev in _RANGE_CHECKS:
        s = df[col].dropna()
        n_below = int((s < lo).sum())
        n_above = int((s > hi).sum())
        passed  = n_below == 0 and n_above == 0
        results.append(QAResult(
            name=f"range_{col}",
            category="value_sanity",
            severity=sev,
            passed=passed,
            message=f"{col} ∈ [{lo}, {hi}]" if passed
                    else f"{col}: {n_below} below {lo}, {n_above} above {hi}",
            details=_jsonify({
                "min": float(s.min()), "max": float(s.max()),
                "n_below_range": n_below, "n_above_range": n_above,
            }),
        ))

    # Solar at night (21:00–03:00 UTC) should be < 100 MW.
    # UTC is used to avoid DST distortion — 22:00 CEST = 20:00 UTC is genuine
    # dusk at 52°N in summer and should not be flagged. Threshold is 100 MW:
    # nighttime actuals top out at ~83 MW (noise/twilight fringe); anything
    # above 100 MW is unambiguously anomalous (<0.3% of typical midday output).
    utc_hour = df.index.hour
    night = (utc_hour >= 21) | (utc_hour < 3)
    for col in ("solar_forecast_mw", "solar_actual_mw"):
        s = df.loc[night, col].dropna()
        n_bright = int((s >= 100).sum())
        results.append(QAResult(
            name=f"solar_night_{col}",
            category="value_sanity",
            severity="warning",
            passed=n_bright == 0,
            message=f"{col}: {n_bright} night-time reading(s) ≥ 100 MW (21:00–03:00 UTC)",
            details={"n_readings_above_100mw": n_bright},
        ))

    return results


# ── 5. Cross-series consistency ────────────────────────────────────────────

def check_cross_series(df: pd.DataFrame) -> list[QAResult]:
    results: list[QAResult] = []
    tt = df[df["dataset"].isin(["train", "test"])].copy()

    # Forecast bias (actual − forecast) per series per year
    bias_pairs = [
        ("wind_actual_mw",  "wind_forecast_mw",  "wind"),
        ("solar_actual_mw", "solar_forecast_mw", "solar"),
        ("load_actual_mw",  "load_forecast_mw",  "load"),
    ]
    bias_summary: dict[str, dict] = {}
    for actual_col, forecast_col, label in bias_pairs:
        valid = tt[[actual_col, forecast_col, "timestamp_local"]].dropna(
            subset=[actual_col, forecast_col]
        )
        if valid.empty:
            continue
        bias = valid[actual_col] - valid[forecast_col]
        by_year = bias.groupby(valid["timestamp_local"].dt.year).mean().round(1)
        bias_summary[label] = _jsonify(by_year.to_dict())

    results.append(QAResult(
        name="forecast_bias_by_year",
        category="cross_series",
        severity="info",
        passed=True,
        message="Mean forecast bias (actual − forecast, MW) per series per year",
        details=bias_summary,
    ))

    # Negative DA price hours
    neg = df[df["da_price_eur_mwh"] < 0]
    neg_by_year = _jsonify(neg.groupby(neg["timestamp_local"].dt.year).size().to_dict())
    results.append(QAResult(
        name="negative_price_hours",
        category="cross_series",
        severity="info",
        passed=True,
        message=f"{len(neg):,} negative DA price hours across full dataset",
        details=_jsonify({
            "total": len(neg),
            "by_year": neg_by_year,
            "min_price_eur_mwh": float(df["da_price_eur_mwh"].min()),
        }),
    ))

    # Renewable surplus hours (wind + solar forecast > load forecast)
    surplus_mask = (
        df["wind_forecast_mw"] + df["solar_forecast_mw"] > df["load_forecast_mw"]
    )
    surplus = df[surplus_mask]
    results.append(QAResult(
        name="renewable_surplus_hours",
        category="cross_series",
        severity="info",
        passed=True,
        message=f"{len(surplus):,} hours where wind+solar forecast exceeds load forecast",
        details=_jsonify({
            "total": len(surplus),
            "by_year": surplus.groupby(surplus["timestamp_local"].dt.year).size().to_dict(),
        }),
    ))

    return results


# ── Entry point ────────────────────────────────────────────────────────────

def run_all_checks(df: pd.DataFrame) -> list[QAResult]:
    return (
        check_structural(df)
        + check_missingness(df)
        + check_duplicates(df)
        + check_value_sanity(df)
        + check_cross_series(df)
    )
