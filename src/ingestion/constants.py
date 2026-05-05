import pandas as pd
from pandas.tseries.offsets import MonthEnd, Week
from pathlib import Path

BIDDING_ZONE = "DE_LU"
DE_LU_EIC = "10Y1001A1001A82H"

TRAIN_START = pd.Timestamp("2021-01-01", tz="Europe/Berlin")
TRAIN_END = pd.Timestamp("2025-06-30 23:00", tz="Europe/Berlin")
TEST_START = pd.Timestamp("2025-07-01", tz="Europe/Berlin")
TEST_END = (
    (pd.Timestamp.now(tz="Europe/Berlin") - pd.Timedelta(days=1))
    .normalize()
    + pd.Timedelta(hours=23)
)
RAW_DATA_DIR = Path("data/raw")
CHUNK_DAYS = 90

# ── Forecast horizon ──────────────────────────────────────────────────────────
# Prompt week: next full ISO Mon–Sun week after TEST_END's date.
# Week(weekday=0) snaps forward to the next Monday (inclusive if already Monday).
PROMPT_WEEK_START = (TEST_END + Week(weekday=0)).normalize()
PROMPT_WEEK_END   = PROMPT_WEEK_START + pd.Timedelta(days=6, hours=23)

# Prompt month: the full calendar month after TEST_END's month.
# MonthEnd(1) → last day of TEST_END's own month (May 31 23:00).
# + 1 hour → midnight on the 1st of next month (June 1 00:00).
# MonthEnd(2) → last day of next month at same time-of-day (June 30 23:00).
PROMPT_MONTH_START = TEST_END + MonthEnd(1) + pd.Timedelta(hours=1)
PROMPT_MONTH_END   = TEST_END + MonthEnd(2)

# FORECAST_END is the last hour we need to predict to cover the prompt month.
FORECAST_END = PROMPT_MONTH_END
