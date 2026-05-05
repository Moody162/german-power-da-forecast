"""
Recursive multi-step forecast from TEST_END+1h through FORECAST_END.

For each future hour:
  1. Pull climatological wind/solar/load proxies from clim_proxies.
  2. Compute price lag and rolling features from a growing price buffer
     seeded with actual prices from features.parquet.
  3. Build calendar features from the Berlin local timestamp.
  4. Assemble FEATURE_COLS in order and predict with the final LightGBM model.
  5. Append the prediction to the price buffer for subsequent steps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb

from src.features.engineer import FEATURE_COLS
from src.ingestion.constants import FORECAST_END, TEST_END
from src.models.clim_proxies import build_clim_proxies, get_proxy_features

# Hours of actual price history needed to seed price lag and rolling features.
# Derived from engineer.py: rolling_std_7d uses shift(24) + rolling(168),
# requiring prices as far back as t-191. 200 adds a small safety margin.
_BUFFER_SEED_HOURS = 200


def recursive_forecast(
    model: lgb.LGBMRegressor,
    features: pd.DataFrame,
) -> pd.Series:
    """
    Generate hourly DA price predictions from TEST_END+1h through FORECAST_END.

    Parameters
    ----------
    model    : trained LightGBM model (output of train_final_model)
    features : full features.parquet DataFrame (both train and test splits)

    Returns
    -------
    pd.Series of predicted DA prices (€/MWh), UTC DatetimeIndex,
    name='y_pred_recursive'.
    """
    # ── Seed price buffer with known actuals ──────────────────────────────────
    # Prices up to and including TEST_END are real observed values.
    # The buffer grows as predictions are appended; future lags draw from it.
    history = features.loc[features.index <= TEST_END, "da_price_eur_mwh"]
    if len(history) < _BUFFER_SEED_HOURS:
        raise ValueError(
            f"Need {_BUFFER_SEED_HOURS} seed hours, got {len(history)}."
        )
    price_buffer: list[float] = list(history.iloc[-_BUFFER_SEED_HOURS:].values)

    # ── Climatological proxies from training data ─────────────────────────────
    train = features[features["dataset"] == "train"]
    clim  = build_clim_proxies(train)

    # ── Forecast index: TEST_END+1h → FORECAST_END in UTC ────────────────────
    forecast_start = TEST_END.tz_convert("UTC") + pd.Timedelta(hours=1)
    forecast_end   = FORECAST_END.tz_convert("UTC")
    forecast_index = pd.date_range(
        start=forecast_start,
        end=forecast_end,
        freq="h",
        tz="UTC",
    )
    local_index = forecast_index.tz_convert("Europe/Berlin")

    # Pre-compute proxy features for the full horizon in one vectorised call
    proxy_df = get_proxy_features(clim, forecast_index)

    # ── Recursive prediction loop ─────────────────────────────────────────────
    predictions: list[float] = []

    for ts_utc, ts_local in zip(forecast_index, local_index):
        # Price lags from buffer.
        # buffer[-1] always points to the price one hour before ts_utc.
        # buffer[-k] = price at ts_utc - k hours.
        lag_24h  = price_buffer[-24]
        lag_48h  = price_buffer[-48]
        lag_168h = price_buffer[-168]

        # Rolling 7-day stats, mirroring engineer.py:
        #   price_lagged = price.shift(24)
        #   rolling(168).mean() at ts_utc = mean(price[ts-191h : ts-24h])
        # In buffer terms: elements [-191 : -23] (end-exclusive) = 168 values.
        window = price_buffer[-191:-23]
        roll_mean = float(np.mean(window))
        roll_std  = float(np.std(window, ddof=1))

        row = proxy_df.loc[ts_utc]

        feature_row = {
            "wind_forecast_mw":      row["wind_forecast_mw"],
            "solar_forecast_mw":     row["solar_forecast_mw"],
            "load_forecast_mw":      row["load_forecast_mw"],
            "residual_load_mw":      row["residual_load_mw"],
            "renewable_share":       row["renewable_share"],
            "wind_solar_sum_mw":     row["wind_solar_sum_mw"],
            "price_lag_24h":         lag_24h,
            "price_lag_48h":         lag_48h,
            "price_lag_168h":        lag_168h,
            "price_rolling_mean_7d": roll_mean,
            "price_rolling_std_7d":  roll_std,
            "hour":                  ts_local.hour,
            "day_of_week":           ts_local.dayofweek,
            "month":                 ts_local.month,
            "is_weekend":            int(ts_local.dayofweek >= 5),
            "quarter":               ts_local.quarter,
        }

        X = pd.DataFrame([feature_row], columns=FEATURE_COLS)
        y_hat = float(model.predict(X)[0])

        predictions.append(y_hat)
        price_buffer.append(y_hat)

    return pd.Series(predictions, index=forecast_index, name="y_pred_recursive")
