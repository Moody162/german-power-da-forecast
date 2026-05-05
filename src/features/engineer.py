"""
Feature engineering for the DA price forecasting model.

All features are constructed to be available at prediction time (after 12:55 CET
on day D-1, when DA forecasts for day D are published). No actuals columns are
used — they are not available at prediction time.

Leakage policy:
  - Price lag features use shift(24) minimum — yesterday's prices are the
    earliest available at prediction time.
  - Rolling stats on price use shift(24) before the rolling window.
  - DA wind/solar/load forecasts for the delivery hour are available after
    the auction closes and are safe to use directly.
"""

from __future__ import annotations

import pandas as pd

FEATURE_COLS = [
    # Fundamental drivers
    "wind_forecast_mw",
    "solar_forecast_mw",
    "load_forecast_mw",
    "residual_load_mw",
    "renewable_share",
    "wind_solar_sum_mw",
    # Lagged price
    "price_lag_24h",
    "price_lag_48h",
    "price_lag_168h",
    # Rolling price stats (lagged to avoid leakage)
    "price_rolling_mean_7d",
    "price_rolling_std_7d",
    # Calendar
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "quarter",
]

TARGET_COL = "da_price_eur_mwh"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes merged_clean.parquet DataFrame, returns a new DataFrame with
    FEATURE_COLS + TARGET_COL + metadata columns (timestamp_local, dataset).

    Rows where any feature is NaN (due to lagged windows) are dropped.
    The largest lag is 168h, so the first 168 rows are dropped.
    """
    out = pd.DataFrame(index=df.index)

    # --- Metadata ---
    out["timestamp_local"] = df["timestamp_local"]
    out["dataset"]         = df["dataset"]

    # --- Target ---
    out[TARGET_COL] = df["da_price_eur_mwh"]

    # --- Raw forecast features ---
    out["wind_forecast_mw"]  = df["wind_forecast_mw"]
    out["solar_forecast_mw"] = df["solar_forecast_mw"]
    out["load_forecast_mw"]  = df["load_forecast_mw"]

    # --- Derived supply/demand features ---
    out["residual_load_mw"]  = df["load_forecast_mw"] - df["wind_forecast_mw"] - df["solar_forecast_mw"]
    out["wind_solar_sum_mw"] = df["wind_forecast_mw"] + df["solar_forecast_mw"]
    out["renewable_share"]   = out["wind_solar_sum_mw"] / df["load_forecast_mw"].replace(0, float("nan"))

    # --- Lagged price features (shift in hours — index is hourly UTC) ---
    price = df["da_price_eur_mwh"]
    out["price_lag_24h"]  = price.shift(24)
    out["price_lag_48h"]  = price.shift(48)
    out["price_lag_168h"] = price.shift(168)

    # --- Rolling price stats: 7-day window, shifted 24h to avoid leakage ---
    price_lagged = price.shift(24)
    out["price_rolling_mean_7d"] = price_lagged.rolling(168).mean()
    out["price_rolling_std_7d"]  = price_lagged.rolling(168).std()

    # --- Calendar features (from local Berlin time) ---
    local = df["timestamp_local"]
    out["hour"]        = local.dt.hour
    out["day_of_week"] = local.dt.dayofweek      # Monday=0, Sunday=6
    out["month"]       = local.dt.month
    out["quarter"]     = local.dt.quarter
    out["is_weekend"]  = (local.dt.dayofweek >= 5).astype(int)

    # --- Drop rows with NaN in any feature or target ---
    cols_to_check = FEATURE_COLS + [TARGET_COL]
    out = out.dropna(subset=cols_to_check)

    return out
