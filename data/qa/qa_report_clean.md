# QA Report

**Dataset shape**: 46,343 rows × 9 columns

**Checks run**: 35  |  **Critical failures**: 0  |  **Warnings**: 0


## Structural

| Check | Severity | Passed | Message |
|-------|----------|--------|---------|
| `index_monotonic` | 🔴 critical | ✓ | Index is monotonically increasing |
| `hourly_frequency` | 🔴 critical | ✓ | Hourly frequency intact |
| `columns_present` | 🔴 critical | ✓ | All expected columns present |
| `dataset_labels` | 🔴 critical | ✓ | dataset column contains only valid labels |

## Missingness

| Check | Severity | Passed | Message |
|-------|----------|--------|---------|
| `no_nulls_da_price_eur_mwh` | 🔴 critical | ✓ | da_price_eur_mwh: 0 NaN in train+test |
| `no_nulls_wind_forecast_mw` | 🔴 critical | ✓ | wind_forecast_mw: 0 NaN in train+test |
| `no_nulls_solar_forecast_mw` | 🔴 critical | ✓ | solar_forecast_mw: 0 NaN in train+test |
| `no_nulls_load_forecast_mw` | 🔴 critical | ✓ | load_forecast_mw: 0 NaN in train+test |
| `nulls_wind_actual_mw` | 🟢 info | ✓ | wind_actual_mw: 0 NaN (0.0%) in train+test |
| `nulls_solar_actual_mw` | 🟢 info | ✓ | solar_actual_mw: 0 NaN (0.0%) in train+test |
| `nulls_load_actual_mw` | 🟢 info | ✓ | load_actual_mw: 0 NaN (0.0%) in train+test |
| `max_gap_da_price_eur_mwh` | 🟢 info | ✓ | da_price_eur_mwh: largest gap = 0h |
| `max_gap_wind_forecast_mw` | 🟢 info | ✓ | wind_forecast_mw: largest gap = 0h |
| `max_gap_solar_forecast_mw` | 🟢 info | ✓ | solar_forecast_mw: largest gap = 0h |
| `max_gap_load_forecast_mw` | 🟢 info | ✓ | load_forecast_mw: largest gap = 0h |
| `max_gap_wind_actual_mw` | 🟢 info | ✓ | wind_actual_mw: largest gap = 0h |
| `max_gap_solar_actual_mw` | 🟢 info | ✓ | solar_actual_mw: largest gap = 0h |
| `max_gap_load_actual_mw` | 🟢 info | ✓ | load_actual_mw: largest gap = 0h |
| `monthly_missingness` | 🟢 info | ✓ | Per-month NaN counts per column |

## Duplicates

| Check | Severity | Passed | Message |
|-------|----------|--------|---------|
| `no_duplicate_utc` | 🔴 critical | ✓ | No duplicate UTC timestamps |
| `dst_spring_days` | 🟢 info | ✓ | 6 23-hour days found, all in March |
| `dst_autumn_days` | 🟢 info | ✓ | 5 25-hour days found, all in October |
| `no_unexpected_day_lengths` | 🔴 critical | ✓ | No days with unexpected hour counts |

## Value Sanity

| Check | Severity | Passed | Message |
|-------|----------|--------|---------|
| `range_da_price_eur_mwh` | 🔴 critical | ✓ | da_price_eur_mwh ∈ [-500, 4000] |
| `range_wind_forecast_mw` | 🔴 critical | ✓ | wind_forecast_mw ∈ [0, 80000] |
| `range_solar_forecast_mw` | 🔴 critical | ✓ | solar_forecast_mw ∈ [0, 80000] |
| `range_load_forecast_mw` | 🔴 critical | ✓ | load_forecast_mw ∈ [20000, 90000] |
| `range_wind_actual_mw` | 🔴 critical | ✓ | wind_actual_mw ∈ [0, 80000] |
| `range_solar_actual_mw` | 🔴 critical | ✓ | solar_actual_mw ∈ [0, 80000] |
| `range_load_actual_mw` | 🔴 critical | ✓ | load_actual_mw ∈ [20000, 90000] |
| `solar_night_solar_forecast_mw` | 🟡 warning | ✓ | solar_forecast_mw: 0 night-time reading(s) ≥ 100 MW (21:00–03:00 UTC) |
| `solar_night_solar_actual_mw` | 🟡 warning | ✓ | solar_actual_mw: 0 night-time reading(s) ≥ 100 MW (21:00–03:00 UTC) |

## Cross Series

| Check | Severity | Passed | Message |
|-------|----------|--------|---------|
| `forecast_bias_by_year` | 🟢 info | ✓ | Mean forecast bias (actual − forecast, MW) per series per year |
| `negative_price_hours` | 🟢 info | ✓ | 1,642 negative DA price hours across full dataset |
| `renewable_surplus_hours` | 🟢 info | ✓ | 514 hours where wind+solar forecast exceeds load forecast |
