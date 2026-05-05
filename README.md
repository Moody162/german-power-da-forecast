# German Power Day-Ahead Forecast

End-to-end forecasting pipeline for the German Day-Ahead electricity market. Ingests price and fundamental driver data (wind generation, solar generation, total load) from the ENTSO-E Transparency Platform, trains a time-series model to predict next-day hourly DA prices, translates forecasts into prompt curve trading views, and integrates an LLM as a programmatic pipeline component.

**Author:** Mohamad Fares — `fares.mohamad1602@gmail.com`

---

## What it does

1. **Ingestion** — pulls hourly DA prices, wind/solar generation, and load for Germany from ENTSO-E, with correct DST handling.
2. **Data quality** — 35 automated QA checks (missingness, duplicates, outliers, coverage) with a generated report.
3. **Forecasting** — baseline + LightGBM model with 30-fold expanding walk-forward CV. Predicts next-day hourly prices.
4. **Curve translation** — recursive forecast to prompt-week and prompt-month horizons with sigma-based uncertainty bands and three-scenario desk views.
5. **AI component** — LLM called programmatically from Python to generate a daily market commentary. Every prompt and response is logged.

---

## Setup

### Prerequisites
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- ENTSO-E API token — register at `transparency.entsoe.eu`, then email `transparency@entsoe.eu` with subject `RESTful API access`. Approval takes 1–3 working days.
- Anthropic API key — `console.anthropic.com`

### Install
```bash
git clone git@github.com:Moody162/german-power-da-forecast.git
cd german-power-da-forecast
uv sync
cp .env.example .env
# Edit .env and fill in ENTSOE_API_KEY and ANTHROPIC_API_KEY
```

### Run the pipeline

Use the provided Python script, which works on all platforms (macOS, Linux, Windows). It cleans all generated outputs and runs all 9 steps in order:

```bash
uv run run_pipeline.py
```

Ingestion hits the ENTSO-E API and takes approximately 15 minutes. If raw data already exists and you only want to re-run the downstream steps:

```bash
uv run run_pipeline.py --skip-ingest
```

To run steps individually instead:

```bash
uv run scripts/01_ingest.py        # fetch raw data from ENTSO-E (~15 min)
uv run scripts/02_merge.py         # align and merge all series
uv run scripts/03_qa.py            # run QA checks on raw data
uv run scripts/04_clean.py         # impute and clean
uv run scripts/05_features.py      # feature engineering
uv run scripts/06_train.py         # walk-forward CV + final model + figures
uv run scripts/07_curve.py         # recursive forecast to prompt horizon
uv run scripts/08_curve_view.py    # three-scenario desk translation
uv run scripts/09_drivers_commentary.py  # LLM-generated market commentary
```

---

## Project structure

```
src/
├── ingestion/      ENTSO-E API client, constants, chunked fetching
├── qa/             35-check QA module, imputation
├── features/       feature engineering (FEATURE_COLS, leakage policy)
├── models/         baseline, LightGBM, recursive forecast, curve aggregation
└── ai/             LLM commentary (prompt builder, API call, logging)
scripts/            pipeline entry points (01–09, run in order)
run_pipeline.py     runs the full pipeline (cross-platform)
docs/               ENTSO-E API endpoint documentation
data/               raw + processed data (gitignored)
outputs/
├── figures/        diagnostic plots
├── tables/         CV metrics, feature importance, curve views (CSV/JSON)
├── predictions/    submission.csv, OOF predictions, recursive forecast
├── reports/        model performance, curve view, LLM commentary (Markdown)
├── logs/           LLM call log (JSONL)
└── models/         trained LightGBM model (.pkl)
REPORT.md           written case study report
```

---

## Key outputs

| Path | Description |
|---|---|
| `outputs/predictions/submission.csv` | Out-of-sample predictions (2025-07-01 → test end) |
| `outputs/figures/` | OOF actual vs predicted, feature importance, test set, recursive forecast |
| `outputs/tables/cv_metrics.csv` | Per-fold CV results |
| `outputs/tables/curve_views.json` | Prompt week/month fair values and CIs |
| `outputs/reports/model_performance.md` | Full CV and test set metrics |
| `outputs/reports/prompt_curve_view.md` | Three-scenario desk translation |
| `outputs/reports/drivers_commentary.md` | LLM-generated daily market commentary |
| `outputs/logs/llm_calls.jsonl` | Every LLM call: prompt, response, status, latency, tokens |
| `data/qa/qa_report.md` | Raw data QA summary |
| `data/qa/qa_report_clean.md` | Post-cleaning QA summary |

---

## Methodology notes

- All time-series validation uses **expanding walk-forward CV** — no random splits, ever.
- DST transitions handled explicitly: 23-hour spring-forward days and 25-hour fall-back days verified across the full dataset.
- API keys live only in `.env` (gitignored). Never committed.
- LLM reads only numbers explicitly injected into the prompt — it does not invent figures. Every call is logged with timestamp, model, status, latency, and token counts.
