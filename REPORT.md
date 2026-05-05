# German Power Day-Ahead Price Forecasting — Case Study Report

**Mohamad Fares**  
fares.mohamad1602@gmail.com

---

## Part 1 — Data Ingestion and Quality

### Market and Data Source

Germany (DE_LU bidding zone) was chosen as the target market. It is the largest European power market by volume, has the most complete and consistent ENTSO-E coverage, and its price dynamics are dominated by wind and solar — the two cleanest publicly available fundamental drivers. All data was sourced from the [ENTSO-E Transparency Platform REST API](https://documenter.getpostman.com/view/7009892/2s93JtP3F6) via the `entsoe-py` Python client. Full endpoint documentation, including article numbers, `entsoe-py` methods, and direct knowledge base links, is in `docs/api_endpoints.md`.

Five series were collected at hourly resolution:

| Series | ENTSO-E Article | Role |
|---|---|---|
| Day-Ahead prices | 12.1.D | Target variable |
| DA wind and solar forecast | 14.1.D | Primary supply driver |
| DA load forecast | 6.1.B | Primary demand driver |
| Actual wind and solar generation | 16.1.B&C | Training features (not used at inference) |
| Actual total load | 6.1.A | Training features (not used at inference) |

The training window spans **2021-01-01 to 2025-06-30**, and the test window runs from **2025-07-01 to the day before the ingestion script is run** (dynamic). All series except DA prices are published at 15-minute resolution by ENTSO-E and are resampled to hourly means in the merge layer. DA prices were hourly until October 2025, when ENTSO-E transitioned DE_LU to 15-minute settlement; the same resampling step handles both resolutions without branching logic. Requests are issued in 90-day chunks — the most conservative safe limit across all five endpoints — to stay within the API's response size ceiling.

### Timezone and DST Handling

All pipeline boundary timestamps are defined as `tz="Europe/Berlin"` so that transitions are unambiguous at the API query level. Three DST-specific concerns are handled explicitly:

- **Spring forward (23-hour day, late March):** ENTSO-E does not publish a row for the missing 02:00–03:00 hour. No special handling is needed — the merge index simply has no entry for that UTC slot.
- **Fall back (25-hour day, late October):** `entsoe-py` returns a UTC DatetimeIndex, so the two Berlin "02:00" occurrences on a fall-back day are stored as two distinct UTC timestamps (`00:00 UTC` and `01:00 UTC`) — both are correctly preserved.
- **Join alignment:** All series are converted to UTC before the left-join on the price index. This eliminates DST ambiguity at the join level. A `timestamp_local` (Europe/Berlin) column is preserved separately as the source for calendar features, ensuring that hour-of-day, day-of-week, and month features reflect Berlin local time rather than UTC offsets.

The QA pipeline verified 6 correct 23-hour days (all in March) and 5 correct 25-hour days (all in October), with no unexpected day lengths across the full dataset.

### Data Quality

35 automated checks were run on both the raw merged dataset and the cleaned dataset using a dedicated QA module (`src/qa/`). Full reports are at `data/qa/qa_report.md` and `data/qa/qa_report_clean.md`. After cleaning, **all 35 checks passed with zero critical failures and zero warnings**.

**Checks covered:**
- *Structural:* index monotonicity, hourly frequency, required columns present, valid dataset labels
- *Missingness:* per-column NaN counts and maximum gap lengths for all 7 series
- *Duplicates:* no duplicate UTC timestamps; DST day-length verification
- *Value sanity:* physical bounds on all series; nighttime solar sanity check
- *Cross-series:* forecast bias by year, negative price hour count, renewable surplus hours

**Findings on the raw dataset:**
- 1,730 hours of negative DA prices across the full dataset — physically valid (excess renewable supply), not treated as outliers
- 547 hours where wind + solar forecast exceeded total load — valid renewable surplus events
- `solar_forecast_mw`: 3 NaN (critical failure in raw QA), max gap 1 hour
- `load_forecast_mw`: 50 NaN (critical failure in raw QA), max gap 24 hours
- `wind_forecast_mw`, `da_price_eur_mwh`: complete, 0 NaN
- `solar_actual_mw`: 9 NaN (0.019%), max gap 9 hours — actuals only, not a model input
- `load_actual_mw`: 8 NaN (0.017%), max gap 8 hours — actuals only, not a model input

**Cleaning:**
53 cells were imputed across 2 forecast columns using **time-based linear interpolation** (`pandas` `interpolate(method="time")`), with a 72-hour maximum gap limit. This method fits a straight line between the last known value before a gap and the first known value after it, weighted by actual time differences — more physically defensible than forward-fill for multi-hour gaps in load or solar. Gaps exceeding 72 hours are left as NaN. The full cell-level log is at `data/qa/impute_log.json`.

- `solar_forecast_mw`: 3 cells — a single missing midnight reading on each of three DST fall-back dates (Oct 2023, Oct 2024, Oct 2025). The adjacent values on either side of each gap were both 0 MW (solar at midnight), so interpolation correctly produced 0.
- `load_forecast_mw`: 50 cells across four gaps:
  - Two full-day ENTSO-E reporting outages (2022-02-22: 24 hours; 2022-03-24: 24 hours). Interpolation linearly transitioned between the load level at the start of each gap and the load level at the end, producing a smooth ramp consistent with the slow drift typical of hourly load forecasts.
  - Two single missing midnight readings on DST fall-back dates (Oct 2023 and Oct 2024) — same pattern as solar, interpolated to the surrounding load level.

No imputation was applied to the target variable (`da_price_eur_mwh`) or to actual-generation columns, which are used for QA cross-checks only and not as model inputs.
