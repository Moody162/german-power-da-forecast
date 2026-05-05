"""
Last-week-same-day baseline: predict hour h on day D = actual price at
hour h on day D-7. Uses price_lag_168h which is already in features.parquet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def predict_baseline(features: pd.DataFrame) -> pd.Series:
    """Return the last-week-same-hour price as the baseline prediction."""
    return features["price_lag_168h"].rename("y_pred_baseline")


def evaluate(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """Return MAE, RMSE, and tail MAE (top+bottom 5% of actuals)."""
    err = y_true - y_pred
    mae  = float(np.abs(err).mean())
    rmse = float(np.sqrt((err ** 2).mean()))

    threshold_high = y_true.quantile(0.95)
    threshold_low  = y_true.quantile(0.05)
    tail_mask = (y_true >= threshold_high) | (y_true <= threshold_low)
    tail_mae  = float(np.abs(err[tail_mask]).mean())

    return {"mae": round(mae, 3), "rmse": round(rmse, 3), "tail_mae": round(tail_mae, 3)}
