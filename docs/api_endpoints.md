# ENTSO-E Transparency Platform — API Endpoints

All data is sourced from the [ENTSO-E Transparency Platform REST API](https://documenter.getpostman.com/view/7009892/2s93JtP3F6) via the [`entsoe-py`](https://github.com/EnergieID/entsoe-py) Python client. Full knowledge base: [ENTSO-E Transparency Knowledge Base](https://transparencyplatform.zendesk.com/hc/en-us/categories/12818231533716-Knowledge-base).

**Base URL:** `https://web-api.tp.entsoe.eu/api`  
**Authentication:** Security token passed as query parameter `securityToken`  
**Bidding zone:** DE_LU (Germany / Luxembourg)  
**EIC code:** `10Y1001A1001A82H`

---

## Endpoints Used

| # | ENTSO-E Article | Description | `entsoe-py` Method | Raw Resolution | Columns Used | Documentation |
|---|---|---|---|---|---|---|
| 1 | 12.1.D | Day-Ahead Prices | `query_day_ahead_prices` | Hourly (pre-Oct 2025) / 15-min (post-Oct 2025) | Price (€/MWh) | [link](https://transparencyplatform.zendesk.com/hc/en-us/articles/16647234190100-Energy-Prices-12-1-D) |
| 2 | 14.1.D | Day-Ahead Wind and Solar Forecast | `query_wind_and_solar_forecast` | 15-min | Wind Onshore (MW), Wind Offshore (MW), Solar (MW) | [link](https://transparencyplatform.zendesk.com/hc/en-us/articles/16648445340180-Generation-Forecasts-for-Wind-and-Solar-14-1-D-) |
| 3 | 6.1.B | Day-Ahead Total Load Forecast | `query_load_forecast` | 15-min | Forecasted Load (MW) | [link](https://transparencyplatform.zendesk.com/hc/en-us/articles/16647979768084-Total-Load-Day-Ahead-Actual-6-1-A-6-1-B) |
| 4 | 16.1.B&C | Actual Generation per Production Type | `query_generation` | 15-min | Wind Onshore Actual Aggregated (MW), Wind Offshore Actual Aggregated (MW), Solar Actual Aggregated (MW) | [link](https://transparencyplatform.zendesk.com/hc/en-us/articles/16648290299284-Actual-Generation-per-Production-Type-16-1-B-C) |
| 5 | 6.1.A | Actual Total Load | `query_load` | 15-min | Actual Load (MW) | [link](https://transparencyplatform.zendesk.com/hc/en-us/articles/16647979768084-Total-Load-Day-Ahead-Actual-6-1-A-6-1-B) |

---

## Query Parameters

All requests share the following parameters:

| Parameter | Value |
|---|---|
| `documentType` | Article-specific (set by `entsoe-py`) |
| `in_Domain` / `out_Domain` | `10Y1001A1001A82H` (DE_LU) — sent as `in_Domain` or `out_Domain` depending on the article; handled automatically by `entsoe-py` |
| `periodStart` | UTC timestamp, format `YYYYMMDDHHMM` |
| `periodEnd` | UTC timestamp, format `YYYYMMDDHHMM` |

Requests are chunked into 90-day windows. The ~100 TimeSeries per call limit varies by article — some endpoints are more generous — but 90 days is the most conservative safe limit across all five, so it is applied uniformly.

---

## Data Coverage

| Series | Train window | Test window |
|---|---|---|
| DA Prices (target) | 2021-01-01 → 2025-06-30 | 2025-07-01 → day before ingestion run |
| DA Wind/Solar Forecast | 2021-01-01 → 2025-06-30 | 2025-07-01 → day before ingestion run |
| DA Load Forecast | 2021-01-01 → 2025-06-30 | 2025-07-01 → day before ingestion run |
| Actual Generation | 2021-01-01 → 2025-06-30 | 2025-07-01 → day before ingestion run |
| Actual Load | 2021-01-01 → 2025-06-30 | 2025-07-01 → day before ingestion run |

All series are resampled to hourly resolution (mean) in the merge layer before modelling.

---

## Notes

- **15-minute transition:** ENTSO-E began publishing DE_LU day-ahead prices at 15-minute resolution from October 2025. The merge layer uses `.resample("h").mean()` uniformly, which handles both resolutions without branching logic.
- **Actuals vs. forecasts at inference time:** Wind and solar actuals (articles 16.1.B&C and 6.1.A) are used for training only. At inference time for horizons beyond 24 hours, climatological averages (historical mean by month and hour-of-day) are substituted, as multi-week-ahead generation forecasts are not publicly available.
- **End-boundary handling:** `query_day_ahead_prices` applies its own boundary padding internally. All other methods treat `periodEnd` as exclusive, so the client adds 1 hour to `periodEnd` to ensure the final hour's 15-minute intervals are returned.
