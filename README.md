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

### 1. Install Python 3.13+

Check if you already have it:
```bash
python --version
```
If the output shows `Python 3.13.x` or higher, skip to the next step.

**macOS**
```bash
brew install python@3.13
```
If `brew` is not found, install Homebrew first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Then re-run the `brew install python@3.13` command.

**Linux (Ubuntu / Debian)**
```bash
sudo apt update && sudo apt install -y python3.13 python3.13-venv
```
If Python 3.13 is not available in your package manager, install it via the deadsnakes PPA:
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update && sudo apt install -y python3.13 python3.13-venv
```

**Windows**

Download and run the installer from [python.org/downloads](https://www.python.org/downloads/). During installation, check **"Add Python to PATH"** before clicking Install.

After installation, open a new terminal and run:
```
py -3.13 --version
```
This should print `Python 3.13.x`. Use `py -3.13` rather than `python` on Windows — if you have multiple Python versions installed, `python` may still point to an older one. This does not matter for the pipeline: `uv` reads the `requires-python` setting from `pyproject.toml` and automatically selects Python 3.13 when you run `uv sync` or `uv run`. You can confirm it found the right version by running (after installing `uv` in the next step):
```
uv python list
```

---

### 2. Install uv

`uv` is the package manager used by this project. It manages dependencies and runs scripts.

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then restart your terminal (or run `source ~/.bashrc` / `source ~/.zshrc`) so the `uv` command is available.

**Windows** (run in PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Restart PowerShell after installation. Verify with:
```
uv --version
```

---

### 3. API Keys

Two API keys are required before the pipeline can run:

**ENTSO-E API token**
1. Register at [transparency.entsoe.eu](https://transparency.entsoe.eu) (free account)
2. Email `transparency@entsoe.eu` with subject `RESTful API access` and request API access. Approval typically takes 1–3 working days.
3. Once approved, your API key is visible in your account settings on the portal.

**Anthropic API key**
1. Sign up or log in at [console.anthropic.com](https://console.anthropic.com)
2. Navigate to **API Keys** and create a new key.

---

### 4. Clone and install

```bash
git clone https://github.com/Moody162/german-power-da-forecast.git
cd german-power-da-forecast
uv sync
cp .env.example .env
```

Open `.env` in any text editor and fill in your two API keys:
```
ENTSOE_API_KEY=your_entsoe_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### Run the pipeline

Use the provided Python script, which works on all platforms (macOS, Linux, Windows). It cleans all generated outputs and runs all 9 steps in order:

```bash
uv run run_pipeline.py
```

Ingestion is **incremental** — if raw data already exists, only the missing window is fetched from ENTSO-E. A full first-time ingestion takes approximately 15 minutes; subsequent runs are much faster.

To force a full re-ingest from scratch (deletes raw data too):

```bash
uv run run_pipeline.py --full-clean
```

To run steps individually instead:

```bash
uv run scripts/01_ingest.py        # fetch raw data from ENTSO-E (incremental, ~15 min first run)
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
