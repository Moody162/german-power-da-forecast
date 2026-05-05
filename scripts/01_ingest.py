"""
Pipeline entry point for ENTSO-E ingestion.
Calls fetcher.py for each of the 7 series and saves raw parquets to data/raw/.
Run from the project root: python scripts/01_ingest.py
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
