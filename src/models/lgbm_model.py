"""
LightGBM model with expanding-window walk-forward cross-validation.

Validation design:
  - Minimum initial training window: 2 years (17,520 hours)
  - Roll forward in monthly steps (720-hour folds)
  - Each fold trains on all data up to fold boundary, predicts the next month
  - Final model trains on the full train set for test-set inference
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.features.engineer import FEATURE_COLS, TARGET_COL
from src.models.baseline import evaluate

LGBM_PARAMS = {
    "objective":        "regression",
    "metric":           "mae",
    "n_estimators":     1000,
    "learning_rate":    0.05,
    "num_leaves":       63,
    "min_child_samples": 50,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "reg_alpha":        0.1,
    "reg_lambda":       0.1,
    "n_jobs":           -1,
    "verbose":          -1,
    "random_state":     42,
}

MIN_TRAIN_HOURS = 17_520   # 2 years
FOLD_HOURS      = 720      # ~1 month


@dataclass
class CVResult:
    fold:       int
    train_end:  pd.Timestamp
    val_start:  pd.Timestamp
    val_end:    pd.Timestamp
    n_train:    int
    n_val:      int
    metrics:    dict = field(default_factory=dict)
    y_true:     pd.Series = field(default_factory=pd.Series)
    y_pred:     pd.Series = field(default_factory=pd.Series)


def walk_forward_cv(train: pd.DataFrame) -> tuple[list[CVResult], pd.DataFrame]:
    """
    Expanding-window walk-forward CV on the training set.

    Returns:
        results  — list of CVResult per fold
        oof_preds — out-of-fold predictions as a DataFrame with columns
                    [y_true, y_pred, fold]
    """
    X = train[FEATURE_COLS]
    y = train[TARGET_COL]

    results:   list[CVResult] = []
    oof_parts: list[pd.DataFrame] = []

    fold_start = MIN_TRAIN_HOURS
    fold_idx   = 0

    while fold_start + FOLD_HOURS <= len(train):
        fold_end = fold_start + FOLD_HOURS

        X_tr, y_tr = X.iloc[:fold_start],          y.iloc[:fold_start]
        X_val, y_val = X.iloc[fold_start:fold_end], y.iloc[fold_start:fold_end]

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(50, verbose=False),
                           lgb.log_evaluation(period=-1)],
            )

        y_pred = pd.Series(model.predict(X_val), index=X_val.index)
        metrics = evaluate(y_val, y_pred)

        result = CVResult(
            fold      = fold_idx,
            train_end = X_tr.index[-1],
            val_start = X_val.index[0],
            val_end   = X_val.index[-1],
            n_train   = len(X_tr),
            n_val     = len(X_val),
            metrics   = metrics,
            y_true    = y_val,
            y_pred    = y_pred,
        )
        results.append(result)

        oof_parts.append(pd.DataFrame({
            "y_true": y_val.values,
            "y_pred": y_pred.values,
            "fold":   fold_idx,
        }, index=X_val.index))

        fold_start += FOLD_HOURS
        fold_idx   += 1

    oof_preds = pd.concat(oof_parts) if oof_parts else pd.DataFrame()
    return results, oof_preds


def train_final_model(train: pd.DataFrame) -> lgb.LGBMRegressor:
    """Train on full training set, no early stopping."""
    X = train[FEATURE_COLS]
    y = train[TARGET_COL]

    # Use median n_estimators from CV as a proxy for best n_estimators
    params = {**LGBM_PARAMS, "n_estimators": LGBM_PARAMS["n_estimators"]}
    params.pop("metric")   # not needed without eval_set

    model = lgb.LGBMRegressor(**{**LGBM_PARAMS})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(X, y)

    return model


def predict(model: lgb.LGBMRegressor, features: pd.DataFrame) -> pd.Series:
    X = features[FEATURE_COLS]
    return pd.Series(model.predict(X), index=X.index, name="y_pred")
