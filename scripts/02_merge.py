"""
Merge layer: loads raw parquets, resamples 15-min → hourly via mean, extracts
and renames columns to the final schema, joins on a UTC index, and adds dataset
labels. Output: data/processed/merged.parquet

Column schema:
  Index : timestamp_utc (UTC, canonical join key)
  timestamp_local      : Europe/Berlin tz-aware (for hour-of-day features)
  da_price_eur_mwh     : target variable
  wind_forecast_mw     : DA wind forecast (onshore + offshore)
  solar_forecast_mw    : DA solar forecast
  load_forecast_mw     : DA load forecast
  wind_actual_mw       : actual wind generation (QA only — not a feature)
  solar_actual_mw      : actual solar generation (QA only — not a feature)
  load_actual_mw       : actual load (QA only — not a feature)
  dataset              : 'train' | 'test'
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import constants

PROJECT_ROOT  = Path(__file__).resolve().parents[1]
RAW_DIR       = PROJECT_ROOT / constants.RAW_DATA_DIR
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _to_hourly(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path).resample("h").mean()


def _to_utc(df: pd.DataFrame) -> pd.DataFrame:
    df.index = df.index.tz_convert("UTC")
    return df


def build_merged() -> pd.DataFrame:
    # --- DA prices (mixed hourly/15-min — resample handles both) ---
    prices = _to_hourly(RAW_DIR / "da_prices.parquet")
    prices = prices.rename(columns={0: "da_price_eur_mwh"})

    # --- DA wind/solar forecast ---
    wsf = _to_hourly(RAW_DIR / "da_wind_solar_forecast.parquet")
    wsf = pd.DataFrame({
        "wind_forecast_mw":  wsf["Wind Onshore"].add(wsf["Wind Offshore"], fill_value=0),
        "solar_forecast_mw": wsf["Solar"],
    }, index=wsf.index)

    # --- DA load forecast ---
    lf = _to_hourly(RAW_DIR / "da_load_forecast.parquet")
    lf = lf.rename(columns={"Forecasted Load": "load_forecast_mw"})

    # --- Actual generation ---
    # min_count=1: if one wind component is NaN, use the other rather than
    # propagating NaN (handles early years where offshore may be unreported)
    gen = _to_hourly(RAW_DIR / "actual_generation.parquet")
    actuals_gen = pd.DataFrame({
        "wind_actual_mw": gen[
            [("Wind Onshore", "Actual Aggregated"), ("Wind Offshore", "Actual Aggregated")]
        ].sum(axis=1, min_count=1),
        "solar_actual_mw": gen[("Solar", "Actual Aggregated")],
    }, index=gen.index)

    # --- Actual load ---
    al = _to_hourly(RAW_DIR / "actual_load.parquet")
    al = al.rename(columns={"Actual Load": "load_actual_mw"})

    # --- Convert all indexes to UTC ---
    prices, wsf, lf, actuals_gen, al = (
        _to_utc(df) for df in [prices, wsf, lf, actuals_gen, al]
    )

    # --- Left-join everything onto prices (prices drives the index) ---
    merged = (
        prices
        .join(wsf,        how="left")
        .join(lf,         how="left")
        .join(actuals_gen, how="left")
        .join(al,         how="left")
    )
    merged.index.name = "timestamp_utc"

    # --- Add timestamp_local ---
    merged.insert(0, "timestamp_local", merged.index.tz_convert("Europe/Berlin"))

    # --- Add dataset labels ---
    train_start = constants.TRAIN_START.tz_convert("UTC")
    train_end   = constants.TRAIN_END.tz_convert("UTC")
    test_start  = constants.TEST_START.tz_convert("UTC")
    test_end    = constants.TEST_END.tz_convert("UTC")

    merged["dataset"] = pd.NA
    merged.loc[(merged.index >= train_start) & (merged.index <= train_end), "dataset"] = "train"
    merged.loc[(merged.index >= test_start)  & (merged.index <= test_end),  "dataset"] = "test"

    return merged


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print("Building merged dataset...")
    merged = build_merged()

    path = PROCESSED_DIR / "merged.parquet"
    merged.to_parquet(path)

    print(f"\nShape    : {merged.shape}")
    print(f"Index    : {merged.index[0]}  →  {merged.index[-1]}")
    print(f"Columns  : {list(merged.columns)}")
    print(f"\nDataset counts:\n{merged['dataset'].value_counts()}")
    print(f"\nNaN counts:\n{merged.isna().sum()}")
    print(f"\nSaved → {path}")


if __name__ == "__main__":
    main()
