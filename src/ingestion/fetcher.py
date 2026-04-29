"""
Fetches the following 7 ENTSO-E time series for the German bidding zone DE_LU:

  1. Day-ahead prices            (12.1.D)
  2. Day-ahead wind forecast     (14.1.D)
  3. Day-ahead solar forecast    (14.1.D)
  4. Day-ahead load forecast     (6.1.B)
  5. Actual wind generation      (16.1.B&C)
  6. Actual solar generation     (16.1.B&C)
  7. Actual load                 (6.1.A)
"""

import pandas as pd
from datetime import timedelta
from entsoe import EntsoePandasClient

from . import constants


def _fetch_chunked(query_fn, start, end, chunk_days, label):
    """Fetch a time series in chunk_days-sized windows and concatenate results.

    `end` is the last hour to cover (inclusive). The loop advances by
    chunk_end + 1h after each chunk so the boundary hour is never re-requested.

    query_fn receives (start=chunk_start, end=chunk_end) for each window. The
    lambda is responsible for any API-specific end adjustment — e.g. passing
    end + 1h to a method whose API treats end as exclusive, so the full
    chunk_end hour (including its :15/:30/:45 intervals) is returned.
    """
    chunks = []
    failures = 0
    chunk_start = start

    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)
        try:
            result = query_fn(chunk_start, chunk_end)
            print(f"[{label}] {chunk_start} → {chunk_end} (rows={len(result)})")
            chunks.append(result)
        except Exception as e:
            print(f"[{label}] {chunk_start} → {chunk_end} FAILED: {e}")
            failures += 1
        chunk_start = chunk_end + pd.Timedelta(hours=1)

    if not chunks:
        raise RuntimeError(f"[{label}] all {failures} chunk(s) failed")

    combined = pd.concat(chunks)
    return combined[~combined.index.duplicated(keep="first")]


def fetch_da_prices(client: EntsoePandasClient, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Pulls ENTSO-E article 12.1.D (Day-Ahead Prices) for DE_LU.

    `start` and `end` are both inclusive (hourly timestamps). The lambda
    passes end directly because query_day_ahead_prices applies its own ±1-day
    padding internally, making it return the boundary hour without adjustment.

    Chunks at 90 days to stay under the documented 100-TimeSeries response
    limit; empirical observation suggests DA prices publish ~1 TimeSeries per
    day, but ENTSO-E doesn't formally specify the packaging granularity.
    """
    return _fetch_chunked(
        query_fn=lambda s, e: client.query_day_ahead_prices(constants.BIDDING_ZONE, start=s, end=e),
        start=start,
        end=end,
        chunk_days=constants.CHUNK_DAYS,
        label="DA Prices",
    )


def fetch_da_wind_solar_forecast(
    client: EntsoePandasClient, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Pulls ENTSO-E article 14.1.D (DA Wind and Solar Forecast) for DE_LU.

    `start` and `end` are both inclusive (hourly timestamps). The lambda adds
    1h to end because query_wind_and_solar_forecast treats end as exclusive;
    this ensures all four 15-min intervals of the end hour are returned.

    Returns a DataFrame with columns ['Solar', 'Wind Offshore', 'Wind Onshore']
    at 15-min resolution. Column selection is handled in the merge layer.
    """
    return _fetch_chunked(
        query_fn=lambda s, e: client.query_wind_and_solar_forecast(
            constants.BIDDING_ZONE, start=s, end=e + pd.Timedelta(hours=1), psr_type=None
        ),
        start=start,
        end=end,
        chunk_days=constants.CHUNK_DAYS,
        label="DA Wind/Solar Forecast",
    )


def fetch_da_load_forecast(
    client: EntsoePandasClient, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Pulls ENTSO-E article 6.1.B (DA Load Forecast) for DE_LU.

    `start` and `end` are both inclusive (hourly timestamps). The lambda adds
    1h to end because query_load_forecast treats end as exclusive; this ensures
    all four 15-min intervals of the end hour are returned.

    Returns a DataFrame with column 'Forecasted Load' at 15-min resolution.
    """
    return _fetch_chunked(
        query_fn=lambda s, e: client.query_load_forecast(
            constants.BIDDING_ZONE, start=s, end=e + pd.Timedelta(hours=1)
        ),
        start=start,
        end=end,
        chunk_days=constants.CHUNK_DAYS,
        label="DA Load Forecast",
    )


def fetch_actual_generation(
    client: EntsoePandasClient, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Pulls ENTSO-E article 16.1.B&C (Actual Generation per Production Type) for DE_LU.

    `start` and `end` are both inclusive (hourly timestamps). The lambda adds
    1h to end because query_generation treats end as exclusive; this ensures
    all four 15-min intervals of the end hour are returned.

    Returns a DataFrame with a MultiIndex column structure at 15-min resolution.
    Columns used downstream:
      ('Wind Onshore', 'Actual Aggregated') + ('Wind Offshore', 'Actual Aggregated') → wind_actual_mw
      ('Solar', 'Actual Aggregated')                                                  → solar_actual_mw
    Column selection and summing are handled in the merge layer.
    """
    return _fetch_chunked(
        query_fn=lambda s, e: client.query_generation(
            constants.BIDDING_ZONE, start=s, end=e + pd.Timedelta(hours=1), psr_type=None
        ),
        start=start,
        end=end,
        chunk_days=constants.CHUNK_DAYS,
        label="Actual Generation",
    )


def fetch_actual_load(
    client: EntsoePandasClient, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Pulls ENTSO-E article 6.1.A (Actual Total Load) for DE_LU.

    `start` and `end` are both inclusive (hourly timestamps). The lambda adds
    1h to end because query_load treats end as exclusive; this ensures all four
    15-min intervals of the end hour are returned.

    Returns a DataFrame with column 'Actual Load' at 15-min resolution.
    """
    return _fetch_chunked(
        query_fn=lambda s, e: client.query_load(
            constants.BIDDING_ZONE, start=s, end=e + pd.Timedelta(hours=1)
        ),
        start=start,
        end=end,
        chunk_days=constants.CHUNK_DAYS,
        label="Actual Load",
    )
