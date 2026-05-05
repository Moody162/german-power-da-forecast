"""
Converts the model's period fair-value forecasts into tradable desk views
under three market scenarios (bearish, neutral, bullish) by computing edge,
confidence, and recommended position for each scenario × delivery period.

Calls:
    (no src/ modules — all logic is self-contained)

Inputs:
    outputs/tables/curve_views.json

Outputs:
    outputs/tables/prompt_curve_view.json
    outputs/reports/prompt_curve_view.md
"""

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT      = Path(__file__).resolve().parents[1]
CURVE_VIEWS_PATH  = PROJECT_ROOT / "outputs" / "tables" / "curve_views.json"
OUTPUT_JSON_PATH  = PROJECT_ROOT / "outputs" / "tables" / "prompt_curve_view.json"
OUTPUT_MD_PATH    = PROJECT_ROOT / "outputs" / "reports" / "prompt_curve_view.md"

# ── Illustrative forward prices (€/MWh) ──────────────────────────────────────
# Hypothetical reference levels — not real market quotes.
# Chosen to demonstrate the translation logic across long, neutral, and short
# signal regimes. In a live setting, replace with exchange/broker feed values.
SCENARIOS: dict[str, dict] = {
    "market_bearish": {
        "description": "Market underprices fundamentals — forward well below model fair value",
        "forwards": {
            "Prompt Week":  76.00,   # ~2.07σ below fair value → high confidence long
            "Prompt Month": 45.00,   # ~2.09σ below fair value → high confidence long
        },
    },
    "market_neutral": {
        "description": "Market roughly agrees with the model — forward near fair value",
        "forwards": {
            "Prompt Week":  95.00,
            "Prompt Month": 58.00,
        },
    },
    "market_bullish": {
        "description": "Market overprices fundamentals — forward well above model fair value",
        "forwards": {
            "Prompt Week":  107.00,
            "Prompt Month": 68.00,
        },
    },
}

# ── Confidence thresholds (multiples of sigma) ────────────────────────────────
_THRESHOLDS = {"high": 1.96, "moderate": 1.28, "low": 0.50}

# ── Invalidation conditions (shared across all scenarios) ─────────────────────
_INVALIDATION = [
    {
        "condition": "weather_surprise",
        "description": (
            "A sustained heat wave or cold snap drives load or renewable output "
            "outside the climatological range used for the recursive forecast. "
            "Climatological proxies cannot anticipate weather regimes."
        ),
    },
    {
        "condition": "nuclear_outage",
        "description": (
            "A surprise nuclear outage in Germany or France reduces cross-border "
            "import capacity, shifting the supply stack and repricing scarcity."
        ),
    },
    {
        "condition": "gas_repricing",
        "description": (
            "A gas supply disruption (TTF spike) raises the marginal cost of "
            "gas-fired generation, lifting the price floor above model assumptions."
        ),
    },
    {
        "condition": "model_assumption_breakdown",
        "description": (
            "Sigma bands are derived from OOF residuals over the Jul 2025–May 2026 "
            "period. If the future regime differs materially (e.g. structural demand "
            "shift, new interconnector capacity), uncertainty is underestimated."
        ),
    },
    {
        "condition": "demand_response",
        "description": (
            "Large-scale industrial curtailment or demand response not captured by "
            "the ENTSO-E load proxy suppresses realized demand below the forecast."
        ),
    },
]

_INSTRUMENT = {
    "Prompt Week":  "EEX prompt-week baseload forward",
    "Prompt Month": "EEX prompt-month baseload forward",
}

_SIZING = {
    "high":     "Full-size position — edge exceeds 1.96σ; model error unlikely to eliminate the edge.",
    "moderate": "Half-size position — edge exceeds 1.28σ; meaningful conviction but room for model error.",
    "low":      "Quarter-size position — edge exceeds 0.50σ; treat as indicative, not a conviction trade.",
}


def _confidence(edge_in_sigma: float) -> str:
    z = abs(edge_in_sigma)
    if z >= _THRESHOLDS["high"]:
        return "high"
    if z >= _THRESHOLDS["moderate"]:
        return "moderate"
    if z >= _THRESHOLDS["low"]:
        return "low"
    return "noise"


def _direction(edge: float, confidence: str) -> str:
    if confidence == "noise":
        return "neutral"
    return "long" if edge > 0 else "short"


def _desk_action(
    label: str,
    direction: str,
    confidence: str,
    fair_value: float,
    forward_px: float,
    edge: float,
    edge_in_sigma: float,
) -> dict:
    instrument = _INSTRUMENT[label]

    if direction == "neutral":
        return {
            "instrument": instrument,
            "position":   "flat",
            "rationale": (
                f"Edge of {edge:+.2f} €/MWh ({edge_in_sigma:.2f}σ) is within noise "
                "threshold. Model does not provide sufficient conviction to deviate from flat."
            ),
            "sizing_note": "No position. Revisit if the forward moves more than 1.28σ from fair value.",
        }

    verb  = "Buy" if direction == "long" else "Sell"
    rel   = "above" if direction == "long" else "below"

    return {
        "instrument": instrument,
        "position":   direction,
        "rationale": (
            f"Model fair value ({fair_value:.2f} €/MWh) is {abs(edge):.2f} €/MWh {rel} "
            f"the illustrative forward ({forward_px:.2f} €/MWh). {verb} the {instrument} "
            f"to capture the {abs(edge):.2f} €/MWh edge on delivery-period settlement."
        ),
        "sizing_note": _SIZING[confidence],
    }


def _compute_period_view(period: dict, forward_px: float) -> dict:
    fair_value    = period["mean_pred"]
    sigma         = period["sigma"]
    edge          = round(fair_value - forward_px, 4)
    edge_in_sigma = round(edge / sigma, 4)
    confidence    = _confidence(edge_in_sigma)
    direction     = _direction(edge, confidence)

    return {
        "label":                    period["label"],
        "period_start":             period["period_start"],
        "period_end":               period["period_end"],
        "n_hours":                  period["n_hours"],
        "model_fair_value_eur_mwh": fair_value,
        "model_sigma_eur_mwh":      sigma,
        "ci_80_low":                period["low_80"],
        "ci_80_high":               period["high_80"],
        "ci_95_low":                period["low_95"],
        "ci_95_high":               period["high_95"],
        "forward_px_eur_mwh":       forward_px,
        "forward_px_source":        "illustrative",
        "edge_eur_mwh":             edge,
        "edge_in_sigma":            edge_in_sigma,
        "signal_direction":         direction,
        "signal_confidence":        confidence,
        "desk_action":              _desk_action(
            period["label"], direction, confidence,
            fair_value, forward_px, edge, edge_in_sigma,
        ),
        "invalidation_conditions":  _INVALIDATION,
    }


_DIRECTION_LABEL = {"long": "**LONG**", "short": "**SHORT**", "neutral": "FLAT"}
_CONFIDENCE_LABEL = {"high": "High", "moderate": "Moderate", "low": "Low", "noise": "Noise"}
_SCENARIO_NUM = {"market_bearish": 1, "market_neutral": 2, "market_bullish": 3}
_SCENARIO_TITLE = {
    "market_bearish": "Market Bearish",
    "market_neutral": "Market Neutral",
    "market_bullish": "Market Bullish",
}


def _save_markdown(output: dict, path: Path) -> None:
    test_end_ts  = pd.Timestamp(output["test_end"]).strftime("%Y-%m-%d %H:%M %Z")
    generated_ts = pd.Timestamp(output["generated_at"]).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Prompt Curve Translation View — German DA Power (DE_LU)",
        "",
        f"**Model data through:** {test_end_ts}  ",
        f"**Generated:** {generated_ts}",
        "",
        "> **Disclaimer:** Forward prices are illustrative hypothetical reference levels,",
        "> not real market quotes. Included solely to demonstrate the DA-to-curve",
        "> translation methodology across long, neutral, and short signal regimes.",
        "",
        "---",
        "",
        "## Confidence Framework",
        "",
        "| Level    | Threshold            | Desk Implication                         |",
        "|----------|----------------------|------------------------------------------|",
        "| High     | edge ≥ 1.96σ        | Full-size position                       |",
        "| Moderate | 1.28σ ≤ edge < 1.96σ | Half-size position                       |",
        "| Low      | 0.50σ ≤ edge < 1.28σ | Quarter-size — indicative only           |",
        "| Noise    | edge < 0.50σ        | Flat — insufficient conviction to trade  |",
        "",
        "---",
        "",
    ]

    for scenario in output["scenarios"]:
        key   = scenario["scenario"]
        num   = _SCENARIO_NUM[key]
        title = _SCENARIO_TITLE[key]
        desc  = scenario["description"]
        views = scenario["period_views"]

        lines += [
            f"## Scenario {num}: {title}",
            f"*{desc}*",
            "",
            "| Period | Fair Value (€/MWh) | Forward (€/MWh) | Edge (€/MWh) | σ-multiple | Direction | Confidence |",
            "|--------|-------------------|----------------|-------------|-----------|-----------|------------|",
        ]

        for pv in views:
            edge_sign = "+" if pv["edge_eur_mwh"] >= 0 else ""
            z_sign    = "+" if pv["edge_in_sigma"] >= 0 else ""
            lines.append(
                f"| {pv['label']} "
                f"| {pv['model_fair_value_eur_mwh']:.2f} "
                f"| {pv['forward_px_eur_mwh']:.2f} "
                f"| {edge_sign}{pv['edge_eur_mwh']:.2f} "
                f"| {z_sign}{pv['edge_in_sigma']:.2f}σ "
                f"| {_DIRECTION_LABEL[pv['signal_direction']]} "
                f"| {_CONFIDENCE_LABEL[pv['signal_confidence']]} |"
            )

        lines.append("")

        for pv in views:
            da  = pv["desk_action"]
            pos = da["position"].upper()
            lines += [
                f"**{pv['label']} — Desk Action**  ",
                f"Instrument: {da['instrument']} | Position: **{pos}**  ",
                f"Rationale: {da['rationale']}  ",
                f"Sizing: {da['sizing_note']}",
                "",
            ]

        lines += ["---", ""]

    lines += [
        "## Invalidation Conditions",
        "",
        "The following conditions apply to all scenarios. Any of these would "
        "materially impair the reliability of the model's fair-value estimate:",
        "",
    ]

    invalidation = output["scenarios"][0]["period_views"][0]["invalidation_conditions"]
    for inv in invalidation:
        lines.append(f"- **{inv['condition']}:** {inv['description']}")

    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    with open(CURVE_VIEWS_PATH) as f:
        curve_views = json.load(f)

    period_map = {p["label"]: p for p in curve_views["period_forecasts"]}

    scenarios_out = []
    for key, cfg in SCENARIOS.items():
        period_views = [
            _compute_period_view(period_map[label], forward_px)
            for label, forward_px in cfg["forwards"].items()
        ]
        scenarios_out.append({
            "scenario":    key,
            "description": cfg["description"],
            "period_views": period_views,
        })

    output = {
        "generated_at":             pd.Timestamp.now(tz="UTC").isoformat(),
        "curve_views_generated_at": curve_views["generated_at"],
        "test_end":                 curve_views["test_end"],
        "disclaimer": (
            "Forward prices marked 'illustrative' are not real market quotes. "
            "They are hypothetical reference levels included solely to demonstrate "
            "the DA-to-curve translation methodology across long, neutral, and short "
            "signal regimes."
        ),
        "confidence_thresholds": {
            "high":     "edge ≥ 1.96σ",
            "moderate": "1.28σ ≤ edge < 1.96σ",
            "low":      "0.50σ ≤ edge < 1.28σ",
            "noise":    "edge < 0.50σ — no position",
        },
        "scenarios": scenarios_out,
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved → {OUTPUT_JSON_PATH}")

    _save_markdown(output, OUTPUT_MD_PATH)
    print(f"Saved → {OUTPUT_MD_PATH}")


if __name__ == "__main__":
    main()
