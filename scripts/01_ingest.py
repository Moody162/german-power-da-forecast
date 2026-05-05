"""
Fetches all raw time series from the ENTSO-E Transparency Platform for the
German bidding zone DE_LU and saves each as a parquet file.

Calls:
    src/ingestion/fetcher.py  (fetch_da_prices, fetch_da_wind_solar_forecast,
                               fetch_da_load_forecast, fetch_actual_generation,
                               fetch_actual_load)

Inputs:
    ENTSO-E Transparency Platform API (live, requires ENTSOE_API_KEY in .env)

Outputs:
    data/raw/da_prices.parquet
    data/raw/da_wind_solar_forecast.parquet
    data/raw/da_load_forecast.parquet
    data/raw/actual_generation.parquet
    data/raw/actual_load.parquet
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from entsoe import EntsoePandasClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import constants
from src.ingestion.fetcher import (
    fetch_actual_generation,
    fetch_actual_load,
    fetch_da_load_forecast,
    fetch_da_prices,
    fetch_da_wind_solar_forecast,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SERIES = [
    ("da_prices",              fetch_da_prices),
    ("da_wind_solar_forecast", fetch_da_wind_solar_forecast),
    ("da_load_forecast",       fetch_da_load_forecast),
    ("actual_generation",      fetch_actual_generation),
    ("actual_load",            fetch_actual_load),
]


def run(client: EntsoePandasClient, start, end, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fetch_fn in SERIES:
        path = out_dir / f"{name}.parquet"
        print(f"\n{'='*60}\nFetching {name}\n{'='*60}")

        if path.exists():
            existing = pd.read_parquet(path)
            last_ts = existing.index.max()
            if last_ts >= end:
                print(f"Already up to date (last={last_ts}), skipping.")
                continue
            fetch_start = last_ts.floor("h") + pd.Timedelta(hours=1)
            print(f"Incremental fetch: {fetch_start.date()} → {end.date()}")
            new_data = fetch_fn(client, fetch_start, end)
            if isinstance(new_data, pd.Series):
                new_data = new_data.to_frame()
            combined = pd.concat([existing, new_data])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            combined.to_parquet(path)
            print(f"Appended {len(new_data):,} rows → {path} (total {len(combined):,})")
        else:
            print(f"Full fetch: {start.date()} → {end.date()}")
            df = fetch_fn(client, start, end)
            if isinstance(df, pd.Series):
                df = df.to_frame()
            df.to_parquet(path)
            print(f"Saved {len(df):,} rows → {path}")


def main() -> None:
    load_dotenv()
    client = EntsoePandasClient(api_key=os.environ["ENTSOE_API_KEY"])

    print("Fetching train+test window "
          f"({constants.TRAIN_START.date()} → {constants.TEST_END.date()})...")
    run(client, constants.TRAIN_START, constants.TEST_END, PROJECT_ROOT / constants.RAW_DATA_DIR)


if __name__ == "__main__":
    main()
