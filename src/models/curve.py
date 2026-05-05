"""
Aggregates the recursive hourly forecast into prompt-period delivery averages
and attaches uncertainty bands derived from out-of-fold (OOF) residuals.

The uncertainty model:
  - OOF hourly residuals (y_true - y_pred) are grouped by ISO week / calendar
    month and their period-mean is computed for each group.
  - The std of those period-means = sigma, the typical error of a period-average
    forecast.  80% and 95% confidence intervals follow from ±1.28σ and ±1.96σ.

This is the only auditable uncertainty estimate available without a held-out
test period with actuals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.ingestion.constants import (
    PROMPT_MONTH_END,
    PROMPT_MONTH_START,
    PROMPT_WEEK_END,
    PROMPT_WEEK_START,
)

_Z80 = 1.28
_Z95 = 1.96


@dataclass
class PeriodForecast:
    label:        str
    period_start: pd.Timestamp
    period_end:   pd.Timestamp
    n_hours:      int
    mean_pred:    float
    sigma:        float
    low_80:       float
    high_80:      float
    low_95:       float
    high_95:      float

    def as_dict(self) -> dict:
        return {
            "label":        self.label,
            "period_start": self.period_start.isoformat(),
            "period_end":   self.period_end.isoformat(),
            "n_hours":      self.n_hours,
            "mean_pred":    round(self.mean_pred, 2),
            "sigma":        round(self.sigma, 2),
            "low_80":       round(self.low_80, 2),
            "high_80":      round(self.high_80, 2),
            "low_95":       round(self.low_95, 2),
            "high_95":      round(self.high_95, 2),
        }


def _sigma_from_oof(oof: pd.DataFrame, freq: str) -> float:
    """
    Compute the std of period-mean OOF residuals.

    Parameters
    ----------
    oof  : DataFrame with UTC DatetimeIndex and columns y_true, y_pred.
    freq : 'W-MON' for ISO weeks, 'MS' for calendar months.

    Returns
    -------
    Std of per-period mean residuals (€/MWh).
    """
    residuals = oof["y_true"] - oof["y_pred"]
    period_means = residuals.resample(freq).mean().dropna()
    return float(period_means.std(ddof=1))


def _slice_forecast(
    forecast: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    """
    Return the subset of `forecast` whose Berlin local time falls within
    [start, end] inclusive.  start/end are Europe/Berlin timestamps.
    """
    local_index = forecast.index.tz_convert("Europe/Berlin")
    mask = (local_index >= start) & (local_index <= end)
    return forecast.loc[mask]


def build_period_forecasts(
    forecast: pd.Series,
    oof: pd.DataFrame,
) -> list[PeriodForecast]:
    """
    Aggregate hourly recursive forecast into prompt-week and prompt-month
    delivery averages with uncertainty bands.

    Parameters
    ----------
    forecast : pd.Series, UTC DatetimeIndex, output of recursive_forecast()
    oof      : pd.DataFrame with UTC DatetimeIndex and columns [y_true, y_pred],
               output of walk_forward_cv() reassembled in the orchestration script

    Returns
    -------
    List of two PeriodForecast objects: [prompt_week, prompt_month]
    """
    sigma_week  = _sigma_from_oof(oof, freq="W-MON")
    sigma_month = _sigma_from_oof(oof, freq="MS")

    results = []

    specs = [
        ("Prompt Week",  PROMPT_WEEK_START,  PROMPT_WEEK_END,  sigma_week),
        ("Prompt Month", PROMPT_MONTH_START, PROMPT_MONTH_END, sigma_month),
    ]

    for label, start, end, sigma in specs:
        subset = _slice_forecast(forecast, start, end)
        if subset.empty:
            raise ValueError(
                f"{label}: no forecast hours found between {start} and {end}. "
                "Check that FORECAST_END covers the full prompt month."
            )
        mean_pred = float(subset.mean())
        results.append(PeriodForecast(
            label        = label,
            period_start = start,
            period_end   = end,
            n_hours      = len(subset),
            mean_pred    = mean_pred,
            sigma        = sigma,
            low_80       = mean_pred - _Z80 * sigma,
            high_80      = mean_pred + _Z80 * sigma,
            low_95       = mean_pred - _Z95 * sigma,
            high_95      = mean_pred + _Z95 * sigma,
        ))

    return results
