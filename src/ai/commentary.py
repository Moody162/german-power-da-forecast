"""
Automated drivers commentary: calls the Anthropic API with a structured
prompt built from computed pipeline metrics and returns a narrative summary.

The LLM receives only numbers that exist in the input files — it never
invents prices, MAEs, or signals. Every call is logged to a JSONL file.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import anthropic
import pandas as pd

from src.models.clim_proxies import build_clim_proxies, get_proxy_features

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


# ── Prompt building ───────────────────────────────────────────────────────────

def _summarize_cv(cv: pd.DataFrame) -> dict:
    return {
        "lgbm_mae":       round(cv["lgbm_mae"].mean(), 2),
        "lgbm_rmse":      round(cv["lgbm_rmse"].mean(), 2),
        "lgbm_tail_mae":  round(cv["lgbm_tail_mae"].mean(), 2),
        "base_mae":       round(cv["baseline_mae"].mean(), 2),
        "base_rmse":      round(cv["baseline_rmse"].mean(), 2),
        "base_tail_mae":  round(cv["baseline_tail_mae"].mean(), 2),
        "n_folds":        len(cv),
        "improvement_pct": round(
            (1 - cv["lgbm_mae"].mean() / cv["baseline_mae"].mean()) * 100, 1
        ),
    }


def _summarize_drivers(
    features: pd.DataFrame,
    curve_views: dict,
) -> dict:
    """
    Compute mean wind/solar/load for each forecast period using the same
    climatological proxies the recursive forecast used, plus recent actuals
    from the test set for comparison.
    """
    train = features[features["dataset"] == "train"]
    clim  = build_clim_proxies(train)

    period_drivers = []
    for pf in curve_views["period_forecasts"]:
        start = pd.Timestamp(pf["period_start"]).tz_convert("UTC")
        end   = pd.Timestamp(pf["period_end"]).tz_convert("UTC")
        ts    = pd.date_range(start=start, end=end, freq="h", tz="UTC")
        proxy = get_proxy_features(clim, ts)

        period_drivers.append({
            "label":                    pf["label"],
            "mean_wind_mw":             round(proxy["wind_forecast_mw"].mean()),
            "mean_solar_mw":            round(proxy["solar_forecast_mw"].mean()),
            "mean_load_mw":             round(proxy["load_forecast_mw"].mean()),
            "mean_residual_load_mw":    round(proxy["residual_load_mw"].mean()),
            "mean_renewable_share_pct": round(proxy["renewable_share"].mean() * 100, 1),
        })

    # Recent 30-day actuals from test set for context
    test   = features[features["dataset"] == "test"]
    recent = test.tail(30 * 24)
    recent_drivers = {
        "n_days":                   30,
        "mean_wind_mw":             round(recent["wind_forecast_mw"].mean()),
        "mean_solar_mw":            round(recent["solar_forecast_mw"].mean()),
        "mean_load_mw":             round(recent["load_forecast_mw"].mean()),
        "mean_residual_load_mw":    round(recent["residual_load_mw"].mean()),
        "mean_renewable_share_pct": round(recent["renewable_share"].mean() * 100, 1),
    }

    # Period-over-period changes (Prompt Week → Prompt Month)
    pw = period_drivers[0]
    pm = period_drivers[1]

    def _chg(a: float, b: float) -> dict:
        delta = b - a
        pct   = round(delta / a * 100, 1) if a != 0 else None
        return {"delta": round(delta), "pct": pct}

    changes = {
        "wind_mw":          _chg(pw["mean_wind_mw"],             pm["mean_wind_mw"]),
        "solar_mw":         _chg(pw["mean_solar_mw"],            pm["mean_solar_mw"]),
        "load_mw":          _chg(pw["mean_load_mw"],             pm["mean_load_mw"]),
        "residual_load_mw": _chg(pw["mean_residual_load_mw"],    pm["mean_residual_load_mw"]),
        "renewable_share":  _chg(pw["mean_renewable_share_pct"], pm["mean_renewable_share_pct"]),
    }

    return {
        "periods":        period_drivers,
        "recent_actuals": recent_drivers,
        "pw_to_pm_changes": changes,
    }


def _summarize_feature_importance(fi: pd.DataFrame) -> list[dict]:
    total = fi["importance"].sum()
    fi = fi.copy()
    fi["importance_pct"] = (fi["importance"] / total * 100).round(1)
    return fi[["feature", "importance_pct"]].to_dict(orient="records")


def build_prompt(
    cv: pd.DataFrame,
    curve_views: dict,
    prompt_curve_view: dict,
    features: pd.DataFrame,
    feature_importance: pd.DataFrame,
) -> str:
    m = _summarize_cv(cv)
    d = _summarize_drivers(features, curve_views)
    fi = _summarize_feature_importance(feature_importance)

    period_lines = []
    for p in curve_views["period_forecasts"]:
        period_lines.append(
            f"  {p['label']} ({p['period_start'][:10]} to {p['period_end'][:10]}, {p['n_hours']} hours)\n"
            f"    Fair value : {p['mean_pred']} €/MWh\n"
            f"    Sigma      : {p['sigma']} €/MWh\n"
            f"    80% CI     : [{p['low_80']}, {p['high_80']}] €/MWh\n"
            f"    95% CI     : [{p['low_95']}, {p['high_95']}] €/MWh"
        )

    scenario_lines = []
    for sc in prompt_curve_view["scenarios"]:
        scenario_lines.append(f"\n  Scenario: {sc['scenario']} — {sc['description']}")
        for pv in sc["period_views"]:
            da = pv["desk_action"]
            scenario_lines.append(
                f"    {pv['label']}:\n"
                f"      Forward (illustrative): {pv['forward_px_eur_mwh']} €/MWh\n"
                f"      Edge  : {pv['edge_eur_mwh']:+.2f} €/MWh ({pv['edge_in_sigma']:+.2f}σ)\n"
                f"      Signal: {pv['signal_direction'].upper()} | Confidence: {pv['signal_confidence']}\n"
                f"      Action: {da['position'].upper()} {da['instrument']}\n"
                f"      Sizing: {da['sizing_note']}"
            )

    invalidation = prompt_curve_view["scenarios"][0]["period_views"][0][
        "invalidation_conditions"
    ]
    inv_lines = "\n".join(
        f"  - {i['condition']}: {i['description']}" for i in invalidation
    )

    test_end = prompt_curve_view["test_end"][:10]

    prompt = f"""You are a quantitative analyst writing a daily market commentary for a European power trading desk.

Below are the exact outputs from a day-ahead price forecasting model for the German power market (DE_LU), as of {test_end}.
Use ONLY the numbers provided. Do not invent, estimate, or interpolate any figures not listed here.

=== MODEL PERFORMANCE (walk-forward CV, {m['n_folds']} folds) ===
LightGBM mean MAE      : {m['lgbm_mae']} €/MWh
LightGBM mean RMSE     : {m['lgbm_rmse']} €/MWh
LightGBM mean tail MAE : {m['lgbm_tail_mae']} €/MWh
Baseline mean MAE      : {m['base_mae']} €/MWh
Baseline mean RMSE     : {m['base_rmse']} €/MWh
Baseline mean tail MAE : {m['base_tail_mae']} €/MWh
Improvement over baseline: {m['improvement_pct']}%

=== FAIR VALUE VIEWS (recursive forecast from {test_end}) ===
{chr(10).join(period_lines)}

=== FUNDAMENTAL DRIVERS (climatological proxies, same assumptions used in the forecast) ===
Note: "Prompt Week → Prompt Month change" shows how the expected market conditions shift
between the two delivery periods. These are the driver values the model relied on.

                           Recent (last {d['recent_actuals']['n_days']}d actuals)   {d['periods'][0]['label']}   {d['periods'][1]['label']}
Wind generation (MW)       {d['recent_actuals']['mean_wind_mw']:>10,}              {d['periods'][0]['mean_wind_mw']:>10,}   {d['periods'][1]['mean_wind_mw']:>10,}
Solar generation (MW)      {d['recent_actuals']['mean_solar_mw']:>10,}              {d['periods'][0]['mean_solar_mw']:>10,}   {d['periods'][1]['mean_solar_mw']:>10,}
Total load (MW)            {d['recent_actuals']['mean_load_mw']:>10,}              {d['periods'][0]['mean_load_mw']:>10,}   {d['periods'][1]['mean_load_mw']:>10,}
Residual load (MW)         {d['recent_actuals']['mean_residual_load_mw']:>10,}              {d['periods'][0]['mean_residual_load_mw']:>10,}   {d['periods'][1]['mean_residual_load_mw']:>10,}
Renewable share (%)        {d['recent_actuals']['mean_renewable_share_pct']:>10}              {d['periods'][0]['mean_renewable_share_pct']:>10}   {d['periods'][1]['mean_renewable_share_pct']:>10}

Prompt Week → Prompt Month changes:
  Wind        : {d['pw_to_pm_changes']['wind_mw']['delta']:+,} MW  ({d['pw_to_pm_changes']['wind_mw']['pct']:+.1f}%)
  Solar       : {d['pw_to_pm_changes']['solar_mw']['delta']:+,} MW  ({d['pw_to_pm_changes']['solar_mw']['pct']:+.1f}%)
  Load        : {d['pw_to_pm_changes']['load_mw']['delta']:+,} MW  ({d['pw_to_pm_changes']['load_mw']['pct']:+.1f}%)
  Residual load: {d['pw_to_pm_changes']['residual_load_mw']['delta']:+,} MW  ({d['pw_to_pm_changes']['residual_load_mw']['pct']:+.1f}%)
  Renewable share: {d['pw_to_pm_changes']['renewable_share']['delta']:+.1f} pp

Residual load = total load minus wind and solar. A lower residual load means less gas-fired
generation is needed, which pushes prices down.

=== FEATURE IMPORTANCE (% share of total model importance, LightGBM gain) ===
Note: higher % = the model relies on this input more when making predictions.
Price lag features are based on actual past prices; for the recursive forecast beyond
24 hours they are themselves predicted values, which increases uncertainty at longer horizons.

{chr(10).join(f"  {row['feature']:<26} {row['importance_pct']:>5.1f}%" for row in fi)}

=== SCENARIO ANALYSIS (illustrative forward prices) ===
{"".join(scenario_lines)}

Confidence thresholds used:
  high     = edge ≥ 1.96σ  → full-size position
  moderate = 1.28σ ≤ edge < 1.96σ → half-size
  low      = 0.50σ ≤ edge < 1.28σ → quarter-size
  noise    = edge < 0.50σ  → flat

=== INVALIDATION CONDITIONS ===
{inv_lines}

---

Write a daily market commentary with exactly these four sections.
Use only the numbers above — copy them exactly, do not round differently or add new figures.

Each section must contain two parts in this order:
  > **In plain terms:** One or two sentences in simple, jargon-free language that any non-specialist could understand. No technical terms, no Greek letters, no acronyms.
  Then the full technical detail as described below.

**1. Model Quality**
Plain terms first, then two to three technical sentences on forecast performance relative to the baseline.

**2. Fair Value View**
Plain terms first (explain in one or two simple sentences WHY prices differ between the two periods,
citing the specific driver changes — e.g. solar, wind, load — and what that means for power prices
in everyday language). Then one technical paragraph covering both fair values, uncertainty bands,
the driver changes (MW values and % deltas from the table above) that explain the price gap,
and a note on which features the model weighted most heavily and what that implies for forecast
reliability at each horizon (e.g. price lags are known at 24h but recursively predicted beyond that).

**3. Trading Signals**
Plain terms first (one sentence summarising the overall picture across scenarios), then one short technical paragraph per scenario (market_bearish, market_neutral, market_bullish), stating the signal, confidence, and recommended desk action for each delivery period.

**4. Key Risks**
Plain terms first (one sentence on what could go wrong), then a technical bullet list of the conditions that would invalidate the signals, drawn from the invalidation list above.
"""
    return prompt


# ── LLM call + logging ────────────────────────────────────────────────────────

def _log(log_path: Path, record: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def call_llm(prompt: str, log_path: Path) -> str:
    client = anthropic.Anthropic()
    t0 = time.monotonic()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = round((time.monotonic() - t0) * 1000)
        text = response.content[0].text

        _log(log_path, {
            "timestamp":     pd.Timestamp.now(tz="UTC").isoformat(),
            "model":         response.model,
            "status":        "success",
            "latency_ms":    latency_ms,
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "prompt":        prompt,
            "response":      text,
        })
        return text

    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000)
        _log(log_path, {
            "timestamp":     pd.Timestamp.now(tz="UTC").isoformat(),
            "model":         MODEL,
            "status":        f"error: {type(exc).__name__}: {exc}",
            "latency_ms":    latency_ms,
            "input_tokens":  None,
            "output_tokens": None,
            "prompt":        prompt,
            "response":      None,
        })
        raise


# ── Top-level entry point ─────────────────────────────────────────────────────

def run(
    cv: pd.DataFrame,
    curve_views: dict,
    prompt_curve_view: dict,
    features: pd.DataFrame,
    feature_importance: pd.DataFrame,
    log_path: Path,
    output_path: Path,
) -> str:
    prompt = build_prompt(cv, curve_views, prompt_curve_view, features, feature_importance)
    print(f"  Prompt length: {len(prompt):,} chars")

    commentary = call_llm(prompt, log_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(commentary, encoding="utf-8")

    return commentary
