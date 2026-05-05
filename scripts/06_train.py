"""
Runs baseline and LightGBM walk-forward CV, trains the final model on the full
training set, and produces out-of-fold predictions, test-set forecasts,
performance metrics, feature importance, and diagnostic figures.

Calls:
    src/features/engineer.py   (FEATURE_COLS, TARGET_COL)
    src/models/baseline.py     (predict_baseline, evaluate)
    src/models/lgbm_model.py   (walk_forward_cv, train_final_model, predict)

Inputs:
    data/processed/features.parquet

Outputs:
    outputs/models/final_model.pkl
    outputs/predictions/oof_predictions.parquet
    outputs/predictions/submission.csv
    outputs/tables/cv_metrics.csv
    outputs/tables/feature_importance.csv
    outputs/reports/model_performance.md
    outputs/figures/oof_actual_vs_predicted.png
    outputs/figures/feature_importance.png
"""

import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.engineer import FEATURE_COLS, TARGET_COL
from src.models.baseline import evaluate, predict_baseline
from src.models.lgbm_model import (
    predict,
    train_final_model,
    walk_forward_cv,
)

PROJECT_ROOT  = Path(__file__).resolve().parents[1]
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "features.parquet"
TABLES_DIR    = PROJECT_ROOT / "outputs" / "tables"
REPORTS_DIR   = PROJECT_ROOT / "outputs" / "reports"
FIGURES_DIR   = PROJECT_ROOT / "outputs" / "figures"
PREDS_DIR     = PROJECT_ROOT / "outputs" / "predictions"
MODELS_DIR    = PROJECT_ROOT / "outputs" / "models"


def print_metrics(label: str, metrics: dict) -> None:
    print(f"  {label:<30}  MAE={metrics['mae']:.2f}  RMSE={metrics['rmse']:.2f}  TailMAE={metrics['tail_mae']:.2f}")


def save_oof_figure(oof: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))

    # Top: time series comparison (last 90 days of OOF)
    sample = oof.tail(90 * 24)
    ax = axes[0]
    ax.plot(sample.index, sample["y_true"], color="#2c7bb6", lw=0.7, label="Actual", alpha=0.9)
    ax.plot(sample.index, sample["y_pred_lgbm"], color="#d7191c", lw=0.7, label="LightGBM", alpha=0.8)
    ax.plot(sample.index, sample["y_pred_baseline"], color="#888888", lw=0.7,
            label="Baseline (lag-168h)", alpha=0.6, linestyle="--")
    ax.set_title("Out-of-Fold Predictions vs Actuals (last 90 days of CV)")
    ax.set_ylabel("DA Price (€/MWh)")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    # Bottom: scatter actual vs predicted
    ax2 = axes[1]
    ax2.scatter(oof["y_true"], oof["y_pred_lgbm"], alpha=0.15, s=2, color="#d7191c", label="LightGBM")
    lim = [oof["y_true"].min(), oof["y_true"].max()]
    ax2.plot(lim, lim, "k--", lw=1, label="Perfect prediction")
    ax2.set_xlabel("Actual DA Price (€/MWh)")
    ax2.set_ylabel("Predicted DA Price (€/MWh)")
    ax2.set_title("Actual vs Predicted — Out-of-Fold")
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_feature_importance_figure(importance_df: pd.DataFrame, path: Path) -> None:
    top = importance_df.head(16).sort_values("importance")
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(top["feature"], top["importance"], color="#2c7bb6")
    ax.set_xlabel("Feature Importance (gain)")
    ax.set_title("LightGBM Feature Importance")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for d in [TABLES_DIR, REPORTS_DIR, FIGURES_DIR, PREDS_DIR, MODELS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"Loading {FEATURES_PATH} ...")
    df = pd.read_parquet(FEATURES_PATH)
    train = df[df["dataset"] == "train"].copy()
    test  = df[df["dataset"] == "test"].copy()
    print(f"  Train: {len(train):,} rows  |  Test: {len(test):,} rows\n")

    # ── Baseline ──────────────────────────────────────────────────────────────
    print("Baseline (last-week-same-hour):")
    baseline_pred_train = predict_baseline(train)
    baseline_metrics    = evaluate(train[TARGET_COL], baseline_pred_train)
    print_metrics("train (full)", baseline_metrics)

    # ── LightGBM walk-forward CV ───────────────────────────────────────────────
    print("\nLightGBM walk-forward CV ...")
    cv_results, oof = walk_forward_cv(train)

    print(f"  {len(cv_results)} folds completed\n")
    print("  Per-fold metrics:")
    for r in cv_results:
        print(f"    Fold {r.fold:>2}  {r.val_start.date()} → {r.val_end.date()}"
              f"  MAE={r.metrics['mae']:.2f}  RMSE={r.metrics['rmse']:.2f}"
              f"  TailMAE={r.metrics['tail_mae']:.2f}")

    # Aggregate CV metrics
    cv_maes  = [r.metrics["mae"]      for r in cv_results]
    cv_rmses = [r.metrics["rmse"]     for r in cv_results]
    cv_tails = [r.metrics["tail_mae"] for r in cv_results]
    cv_agg = {
        "mae":      round(float(np.mean(cv_maes)),  3),
        "rmse":     round(float(np.mean(cv_rmses)), 3),
        "tail_mae": round(float(np.mean(cv_tails)), 3),
    }
    print(f"\nLightGBM CV mean metrics:")
    print_metrics("mean across folds", cv_agg)
    print("\nBaseline CV-period metrics:")
    baseline_oof = predict_baseline(train.loc[oof.index])
    baseline_cv  = evaluate(oof["y_true"], baseline_oof)
    print_metrics("mean across folds", baseline_cv)

    # OOF aggregate: all folds stacked, evaluated as one
    oof_agg_lgbm = evaluate(oof["y_true"], oof["y_pred"])
    print("\nLightGBM OOF aggregate (all folds combined):")
    print_metrics("all folds combined", oof_agg_lgbm)

    # ── Save CV metrics table ─────────────────────────────────────────────────
    cv_rows = []
    for r in cv_results:
        cv_rows.append({
            "fold":      r.fold,
            "val_start": r.val_start.date(),
            "val_end":   r.val_end.date(),
            "n_train":   r.n_train,
            "n_val":     r.n_val,
            **{f"lgbm_{k}": v for k, v in r.metrics.items()},
        })
    cv_df = pd.DataFrame(cv_rows)

    # Add baseline metrics per fold
    for i, r in enumerate(cv_results):
        bl_fold = evaluate(r.y_true, predict_baseline(train.loc[r.y_true.index]))
        for k, v in bl_fold.items():
            cv_df.loc[i, f"baseline_{k}"] = v

    cv_df.to_csv(TABLES_DIR / "cv_metrics.csv", index=False)
    print(f"\nCV metrics → {TABLES_DIR / 'cv_metrics.csv'}")

    oof.to_parquet(PREDS_DIR / "oof_predictions.parquet")
    print(f"OOF predictions → {PREDS_DIR / 'oof_predictions.parquet'}")

    # ── Final model ───────────────────────────────────────────────────────────
    print("\nTraining final model on full train set ...")
    final_model = train_final_model(train)
    joblib.dump(final_model, MODELS_DIR / "final_model.pkl")
    print(f"Final model → {MODELS_DIR / 'final_model.pkl'}")

    # Feature importance
    importance_df = pd.DataFrame({
        "feature":    FEATURE_COLS,
        "importance": final_model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False).reset_index(drop=True)
    importance_df.to_csv(TABLES_DIR / "feature_importance.csv", index=False)
    print(f"Feature importance → {TABLES_DIR / 'feature_importance.csv'}")

    # ── Test set predictions → submission.csv ─────────────────────────────────
    test_pred = predict(final_model, test)
    test_metrics_lgbm = evaluate(test[TARGET_COL], test_pred)
    test_metrics_base = evaluate(test[TARGET_COL], predict_baseline(test))
    print("\nTest set metrics:")
    print_metrics("LightGBM", test_metrics_lgbm)
    print_metrics("Baseline", test_metrics_base)
    local_times = test_pred.index.tz_convert("Europe/Berlin")
    submission = pd.DataFrame({
        "id":               test_pred.index.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_berlin": local_times.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "y_pred":           test_pred.values.round(4),
    })
    submission.to_csv(PREDS_DIR / "submission.csv", index=False)
    print(f"submission.csv → {PREDS_DIR / 'submission.csv'}  ({len(submission):,} rows)")

    # ── Figures ───────────────────────────────────────────────────────────────
    oof["y_pred_lgbm"]     = oof["y_pred"]
    oof["y_pred_baseline"] = predict_baseline(train.loc[oof.index]).values

    save_oof_figure(oof, FIGURES_DIR / "oof_actual_vs_predicted.png")
    save_feature_importance_figure(importance_df, FIGURES_DIR / "feature_importance.png")
    print(f"Figures → {FIGURES_DIR}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Model':<30}  {'MAE':>8}  {'RMSE':>8}  {'TailMAE':>10}")
    print(f"{'Baseline (lag-168h)':<30}  {baseline_cv['mae']:>8.2f}  {baseline_cv['rmse']:>8.2f}  {baseline_cv['tail_mae']:>10.2f}")
    print(f"{'LightGBM (CV mean)':<30}  {cv_agg['mae']:>8.2f}  {cv_agg['rmse']:>8.2f}  {cv_agg['tail_mae']:>10.2f}")

    # ── Model performance markdown ────────────────────────────────────────────
    def _pct_improvement(lgbm_val, base_val):
        return round((1 - lgbm_val / base_val) * 100, 1)

    train_start_str = train.index[0].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")
    train_end_str   = train.index[-1].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")
    test_start_str  = test.index[0].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")
    test_end_str    = test.index[-1].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")
    oof_start_str   = oof.index[0].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")
    oof_end_str     = oof.index[-1].tz_convert("Europe/Berlin").strftime("%Y-%m-%d")

    lines = [
        "# Model Performance",
        "",
        "**Baseline:** Last-week-same-hour (price_lag_168h).  ",
        "**Model:** LightGBM, expanding-window walk-forward CV with early stopping.  ",
        "**Tail MAE:** MAE restricted to the top and bottom 5% of actual prices (price spikes and negative hours).",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Evaluation window | Model | MAE (€/MWh) | RMSE (€/MWh) | Tail MAE (€/MWh) |",
        "|---|---|---|---|---|",
        f"| CV OOF aggregate ({oof_start_str} → {oof_end_str}, {len(cv_results)} folds) "
        f"| Baseline | {baseline_cv['mae']:.2f} | {baseline_cv['rmse']:.2f} | {baseline_cv['tail_mae']:.2f} |",
        f"| CV OOF aggregate ({oof_start_str} → {oof_end_str}, {len(cv_results)} folds) "
        f"| LightGBM | {oof_agg_lgbm['mae']:.2f} | {oof_agg_lgbm['rmse']:.2f} | {oof_agg_lgbm['tail_mae']:.2f} |",
        f"| Test set ({test_start_str} → {test_end_str}) "
        f"| Baseline | {test_metrics_base['mae']:.2f} | {test_metrics_base['rmse']:.2f} | {test_metrics_base['tail_mae']:.2f} |",
        f"| Test set ({test_start_str} → {test_end_str}) "
        f"| LightGBM | {test_metrics_lgbm['mae']:.2f} | {test_metrics_lgbm['rmse']:.2f} | {test_metrics_lgbm['tail_mae']:.2f} |",
        "",
        "> **CV OOF aggregate** stacks all out-of-fold predictions across all folds and evaluates them as one. "
        "**CV fold mean** (per-fold table below) is the mean of each fold's individual MAE — a slightly different number. "
        "The aggregate is the more conservative and representative figure.",
        "",
        "---",
        "",
        "## Per-Fold CV Results",
        "",
        f"Training window: {train_start_str} → {train_end_str}  ",
        f"Minimum initial training window: 2 years (17,520 hours). Each fold expands by 720 hours.",
        "",
        "| Fold | Val Start | Val End | LightGBM MAE | LightGBM RMSE | LightGBM Tail MAE | Baseline MAE | Baseline RMSE | Baseline Tail MAE |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for r in cv_results:
        bl = cv_df.loc[cv_df["fold"] == r.fold].iloc[0]
        lines.append(
            f"| {r.fold} | {r.val_start.date()} | {r.val_end.date()} "
            f"| {r.metrics['mae']:.2f} | {r.metrics['rmse']:.2f} | {r.metrics['tail_mae']:.2f} "
            f"| {bl['baseline_mae']:.2f} | {bl['baseline_rmse']:.2f} | {bl['baseline_tail_mae']:.2f} |"
        )

    lines += [
        "",
        f"| **Mean** | | "
        f"| **{cv_agg['mae']:.2f}** | **{cv_agg['rmse']:.2f}** | **{cv_agg['tail_mae']:.2f}** "
        f"| **{baseline_cv['mae']:.2f}** | **{baseline_cv['rmse']:.2f}** | **{baseline_cv['tail_mae']:.2f}** |",
    ]

    md_path = REPORTS_DIR / "model_performance.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Model performance report → {md_path}")


if __name__ == "__main__":
    main()
