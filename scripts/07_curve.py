"""
Curve translation: loads the trained final model and OOF predictions,
runs the recursive multi-step forecast through FORECAST_END, aggregates
to prompt-week and prompt-month delivery averages with uncertainty bands,
and saves outputs.

Usage:
    python scripts/07_curve.py

Inputs:
    data/processed/features.parquet
    outputs/models/final_model.pkl
    outputs/predictions/oof_predictions.parquet

Outputs:
    outputs/predictions/recursive_forecast.parquet
    outputs/tables/curve_views.json
    outputs/figures/recursive_forecast.png
"""

import json
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.constants import (
    FORECAST_END,
    PROMPT_MONTH_END,
    PROMPT_MONTH_START,
    PROMPT_WEEK_END,
    PROMPT_WEEK_START,
    TEST_END,
)
from src.models.curve import build_period_forecasts
from src.models.recursive_forecast import recursive_forecast

PROJECT_ROOT   = Path(__file__).resolve().parents[1]
FEATURES_PATH  = PROJECT_ROOT / "data" / "processed" / "features.parquet"
MODEL_PATH     = PROJECT_ROOT / "outputs" / "models" / "final_model.pkl"
OOF_PATH       = PROJECT_ROOT / "outputs" / "predictions" / "oof_predictions.parquet"
TABLES_DIR     = PROJECT_ROOT / "outputs" / "tables"
FIGURES_DIR    = PROJECT_ROOT / "outputs" / "figures"
PREDS_DIR      = PROJECT_ROOT / "outputs" / "predictions"


def save_forecast_figure(
    features: pd.DataFrame,
    forecast: pd.Series,
    period_forecasts: list,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 5))

    # Recent actuals: last 30 days of the test set
    recent = features[features["dataset"] == "test"]["da_price_eur_mwh"].tail(30 * 24)
    ax.plot(
        recent.index.tz_convert("Europe/Berlin"),
        recent.values,
        color="#2c7bb6", lw=0.8, label="Actuals (last 30 days)", alpha=0.9,
    )

    # Recursive forecast
    forecast_local = forecast.copy()
    forecast_local.index = forecast.index.tz_convert("Europe/Berlin")
    ax.plot(
        forecast_local.index, forecast_local.values,
        color="#d7191c", lw=0.9, label="Recursive forecast", alpha=0.85,
    )

    # CI bands (95%)
    pf_week  = period_forecasts[0]
    pf_month = period_forecasts[1]

    for pf, color in [(pf_week, "#f4a582"), (pf_month, "#92c5de")]:
        local_start = pf.period_start
        local_end   = pf.period_end
        ax.axvspan(local_start, local_end, alpha=0.12, color=color)
        ax.axhline(pf.mean_pred, color=color, lw=1.2, linestyle="--", alpha=0.9)
        ax.fill_between(
            [local_start, local_end],
            pf.low_95, pf.high_95,
            alpha=0.08, color=color,
        )

    # Vertical line at TEST_END
    ax.axvline(
        TEST_END.tz_convert("Europe/Berlin"),
        color="black", lw=1, linestyle=":", alpha=0.6, label="TEST_END",
    )

    # Legend patches for period shading
    week_patch  = mpatches.Patch(color="#f4a582", alpha=0.4,
                                  label=f"Prompt Week  μ={pf_week.mean_pred:.1f} ±{pf_week.sigma:.1f} €/MWh")
    month_patch = mpatches.Patch(color="#92c5de", alpha=0.4,
                                  label=f"Prompt Month μ={pf_month.mean_pred:.1f} ±{pf_month.sigma:.1f} €/MWh")

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [week_patch, month_patch], fontsize=7.5, loc="upper left")

    ax.set_title("Recursive DA Price Forecast — Prompt Week & Prompt Month Views")
    ax.set_ylabel("DA Price (€/MWh)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for d in [TABLES_DIR, FIGURES_DIR, PREDS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Load inputs ───────────────────────────────────────────────────────────
    print(f"Loading features  {FEATURES_PATH} ...")
    features = pd.read_parquet(FEATURES_PATH)

    print(f"Loading model     {MODEL_PATH} ...")
    model = joblib.load(MODEL_PATH)

    print(f"Loading OOF       {OOF_PATH} ...")
    oof = pd.read_parquet(OOF_PATH)

    # ── Recursive forecast ────────────────────────────────────────────────────
    forecast_start_berlin = (TEST_END + pd.Timedelta(hours=1))
    print(
        f"\nRunning recursive forecast ...\n"
        f"  From : {forecast_start_berlin.strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"  To   : {FORECAST_END.strftime('%Y-%m-%d %H:%M %Z')}"
    )
    forecast = recursive_forecast(model, features)
    print(f"  {len(forecast):,} hourly predictions generated")

    forecast.to_frame().to_parquet(PREDS_DIR / "recursive_forecast.parquet")
    print(f"  Saved → {PREDS_DIR / 'recursive_forecast.parquet'}")

    # ── Aggregate to prompt periods ───────────────────────────────────────────
    print("\nAggregating to prompt periods ...")
    period_forecasts = build_period_forecasts(forecast, oof)

    print(f"\n{'Period':<14}  {'Hours':>5}  {'Mean':>7}  {'Sigma':>6}  "
          f"{'80% CI':>18}  {'95% CI':>18}")
    print("-" * 75)
    for pf in period_forecasts:
        print(
            f"{pf.label:<14}  {pf.n_hours:>5}  {pf.mean_pred:>7.2f}  {pf.sigma:>6.2f}  "
            f"  [{pf.low_80:.2f}, {pf.high_80:.2f}]  [{pf.low_95:.2f}, {pf.high_95:.2f}]"
        )

    # ── Save curve views JSON ─────────────────────────────────────────────────
    curve_views = {
        "generated_at":  pd.Timestamp.now(tz="UTC").isoformat(),
        "test_end":       TEST_END.isoformat(),
        "forecast_end":   FORECAST_END.isoformat(),
        "period_forecasts": [pf.as_dict() for pf in period_forecasts],
    }
    views_path = TABLES_DIR / "curve_views.json"
    with open(views_path, "w") as f:
        json.dump(curve_views, f, indent=2)
    print(f"\nCurve views → {views_path}")

    # ── Figure ────────────────────────────────────────────────────────────────
    fig_path = FIGURES_DIR / "recursive_forecast.png"
    save_forecast_figure(features, forecast, period_forecasts, fig_path)
    print(f"Figure      → {fig_path}")


if __name__ == "__main__":
    main()
