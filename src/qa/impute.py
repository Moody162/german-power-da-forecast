"""
Imputation of small gaps in forecast columns.

Only forecast columns are touched — actuals are QA-only and left as-is.
Returns the cleaned DataFrame and a structured log of every imputed value.
"""

from __future__ import annotations

import pandas as pd

FORECAST_COLS = [
    "da_price_eur_mwh",
    "wind_forecast_mw",
    "solar_forecast_mw",
    "load_forecast_mw",
]

MAX_GAP_HOURS = 72


def impute_forecast_gaps(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Interpolate gaps ≤ MAX_GAP_HOURS in FORECAST_COLS using time-based linear
    interpolation.

    Returns:
        cleaned  — copy of df with NaN filled in forecast columns
        log      — list of dicts, one entry per imputed cell:
                   {column, timestamp_utc, timestamp_local, before, after}
    """
    cleaned = df.copy()
    log: list[dict] = []

    for col in FORECAST_COLS:
        if col not in cleaned.columns:
            continue

        null_mask = cleaned[col].isna()
        if not null_mask.any():
            continue

        interpolated = cleaned[col].interpolate(method="time", limit=MAX_GAP_HOURS)

        filled_mask = null_mask & interpolated.notna()
        for ts in cleaned.index[filled_mask]:
            log.append({
                "column":          col,
                "timestamp_utc":   str(ts),
                "timestamp_local": str(cleaned.at[ts, "timestamp_local"]),
                "before":          None,
                "after":           round(float(interpolated.at[ts]), 4),
            })

        cleaned[col] = interpolated

    return cleaned, log
