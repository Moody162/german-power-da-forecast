"""
Climatological proxy features for multi-step recursive forecasting.

Beyond the 24-hour DA forecast horizon, real wind/solar/load forecasts are not
publicly available. This module substitutes historical means grouped by
(month, hour-of-day) computed from the training set.

Usage:
    clim = build_clim_proxies(train_df)
    proxy_df = get_proxy_features(clim, future_timestamps)
"""

from __future__ import annotations

import pandas as pd


PROXY_COLS = ["wind_forecast_mw", "solar_forecast_mw", "load_forecast_mw"]


def build_clim_proxies(train: pd.DataFrame) -> pd.DataFrame:
    """
    Compute mean wind/solar/load for every (month, hour) combination in the
    training set.

    Parameters
    ----------
    train : DataFrame with a DatetimeIndex in UTC and columns in PROXY_COLS.
            Typically the 'train' split of features.parquet.

    Returns
    -------
    DataFrame indexed by (month, hour) with columns = PROXY_COLS.
    month is 1–12, hour is 0–23.
    """
    local = train.index.tz_convert("Europe/Berlin")
    lookup = train[PROXY_COLS].copy()
    lookup["month"] = local.month
    lookup["hour"]  = local.hour

    clim = (
        lookup
        .groupby(["month", "hour"])[PROXY_COLS]
        .mean()
    )
    return clim


def get_proxy_features(
    clim: pd.DataFrame,
    timestamps: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Look up climatological wind/solar/load for a sequence of future timestamps.

    Parameters
    ----------
    clim        : output of build_clim_proxies()
    timestamps  : DatetimeIndex of future hours (UTC or tz-aware)

    Returns
    -------
    DataFrame with the same index as `timestamps` and columns = PROXY_COLS.
    """
    local = timestamps.tz_convert("Europe/Berlin")
    keys = pd.MultiIndex.from_arrays([local.month, local.hour], names=["month", "hour"])
    proxy = clim.loc[keys].set_index(timestamps)

    proxy["residual_load_mw"]  = proxy["load_forecast_mw"] - proxy["wind_forecast_mw"] - proxy["solar_forecast_mw"]
    proxy["wind_solar_sum_mw"] = proxy["wind_forecast_mw"] + proxy["solar_forecast_mw"]
    proxy["renewable_share"]   = proxy["wind_solar_sum_mw"] / proxy["load_forecast_mw"].replace(0, float("nan"))

    return proxy
