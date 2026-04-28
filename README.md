# German Power Day-Ahead Forecast

End-to-end forecasting pipeline for the German Day-Ahead electricity market. Ingests price and fundamental driver data (wind generation, solar generation, total load) from the ENTSO-E Transparency Platform, trains a time-series model to predict next-day hourly DA prices, translates forecasts into prompt curve trading views, and integrates an LLM as a programmatic pipeline component.

**Author:** Mohamad Fares — `fares.mohamad1602@gmail.com`

---

## What it does

1. **Ingestion** — pulls hourly DA prices, wind/solar generation, and load for Germany from ENTSO-E, with correct DST handling.
2. **Data quality** — automated QA checks (missingness, duplicates, outliers, coverage) with a generated report.
3. **Forecasting** — baseline + improved models with walk-forward validation. Predicts next-day hourly prices and aggregates into weekly/monthly views.
4. **Curve translation** — converts forecast distributions into a tradable view (expected delivery-period mean with confidence bands), with explicit invalidation logic.
5. **AI component** — an LLM is called programmatically from Python to perform an automated pipeline task. Every prompt and response is logged.

---

## Setup

### Prerequisites
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- ENTSO-E API token — request via email to `transparency@entsoe.eu` with subject `RESTful API access` and your registered email in the body. Approval typically takes 1–3 working days.
- Anthropic API key — https://console.anthropic.com

### Install
```bash
git clone git@github.com:Moody162/german-power-da-forecast.git
cd german-power-da-forecast
uv sync
cp .env.example .env
# Edit .env to fill in ENTSOE_API_KEY and ANTHROPIC_API_KEY
```

### Run the pipeline
```bash
uv run python scripts/01_ingest.py
uv run python scripts/02_qa.py
uv run python scripts/03_train.py
uv run python scripts/04_translate.py
uv run python scripts/05_ai_component.py
```

---

## Project structure
```
src/
├── ingestion/      ENTSO-E API pulls
├── qa/             data quality checks
├── features/       feature engineering
├── models/         baseline + improved models
├── translation/    DA → curve view conversion
└── ai/             LLM-driven pipeline component (with logged prompts/outputs)
data/               raw + processed data (gitignored)
outputs/            figures, tables, predictions, LLM logs
report/             written report
scripts/            pipeline entry points
tests/              DST + leakage tests
```

---

## Outputs

- `outputs/figures/` — figures used in the report
- `outputs/tables/` — performance metrics
- `outputs/predictions/submission.csv` — out-of-sample predictions on the test window
- `outputs/logs/llm_calls.jsonl` — every LLM call (prompt, response, status, latency)
- `data/qa/qa_report.md` — data quality summary
- `report/report.pdf` — final write-up

---

## Methodology notes

- All time-series validation uses **walk-forward / blocked CV** — no random splits.
- DST transitions are handled explicitly: late-March 23-hour day and late-October 25-hour day.
- API keys live only in `.env` (gitignored). Never committed.
- LLM is called from code (Anthropic Python SDK). Every prompt and response is logged with timestamp, status, and latency. The LLM does not invent numbers — it reads only from metrics explicitly passed in the prompt.
