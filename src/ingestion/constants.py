import pandas as pd
from pathlib import Path

BIDDING_ZONE = "DE_LU"
DE_LU_EIC = "10Y1001A1001A82H"

TRAIN_START = pd.Timestamp("2021-01-01", tz="Europe/Berlin")
TRAIN_END = pd.Timestamp("2025-06-30 23:00", tz="Europe/Berlin")
TEST_START = pd.Timestamp("2025-07-01", tz="Europe/Berlin")
TEST_END = pd.Timestamp("2026-04-15 23:00", tz="Europe/Berlin")
STRESS_START = pd.Timestamp("2019-01-01", tz="Europe/Berlin")
STRESS_END = pd.Timestamp("2020-12-31 23:00", tz="Europe/Berlin")

RAW_DATA_DIR = Path("data/raw")
CHUNK_DAYS = 90
