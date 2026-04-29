import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from entsoe import EntsoePandasClient, EntsoeRawClient

START       = pd.Timestamp("2024-01-01", tz="Europe/Berlin")
END         = pd.Timestamp("2024-01-08", tz="Europe/Berlin")
ZONE        = "DE_LU"
DE_LU_CODE  = "10Y1001A1001A82H"

class Tee:
    def __init__(self, *s): self.s = s
    def write(self, d): [x.write(d) for x in self.s]
    def flush(self): [x.flush() for x in self.s]

def probe(label, fn):
    print(f"\n{'='*60}\nSERIES: {label}\n{'='*60}")
    try:
        r = fn()
        print(f"  type   : {type(r)}")
        if hasattr(r, "shape"):   print(f"  shape  : {r.shape}")
        if hasattr(r, "columns"): print(f"  columns: {list(r.columns)}")
        if hasattr(r, "dtypes"):  print(f"  dtypes :\n{r.dtypes}")
        elif hasattr(r, "dtype"): print(f"  dtype  : {r.dtype}")
        if hasattr(r, "index"):
            print(f"  tz     : {r.index.tz}\n  head() :\n{r.head()}\n  tail() :\n{r.tail()}")
    except Exception as e:
        print(f"  ERROR  : {e}")

def main():
    load_dotenv()
    token = os.environ["ENTSOE_API_KEY"]

    log_dir = Path("outputs/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"probe_entsoe_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
    log_file = open(log_path, "w")
    sys.stdout = Tee(sys.__stdout__, log_file)

    client = EntsoePandasClient(api_key=token)

    # 1. DA Prices — HTTP 400 workaround via _base_request + BusinessType=A62
    print(f"\n{'='*60}\nSERIES: DA Prices\n{'='*60}")
    try:
        p = client.query_day_ahead_prices(ZONE, start=START, end=END)
        print(f"  type   : {type(p)}\n  shape  : {p.shape}\n  dtype  : {p.dtype}")
        print(f"  tz     : {p.index.tz}\n  head() :\n{p.head()}\n  tail() :\n{p.tail()}")
    except Exception as e:
        print(f"  ERROR (attempt 1): {e}")
        if "400" in str(e):
            print("  Retrying via EntsoeRawClient._base_request with BusinessType=A62 ...")
            try:
                raw  = EntsoeRawClient(api_key=token)
                resp = raw._base_request(
                    params={'documentType': 'A44', 'in_Domain': DE_LU_CODE,
                            'out_Domain': DE_LU_CODE, 'contract_MarketAgreement.type': 'A01',
                            'BusinessType': 'A62'},
                    start=START, end=END)
                print(f"  raw status : {resp.status_code}")
                print(f"  raw len    : {len(resp.text)} chars\n  raw head   : {resp.text[:500]}")
            except Exception as e2:
                print(f"  ERROR (attempt 2): {e2}")

    # 2. DA wind/solar forecasts — psr_type=None returns all production-type columns
    probe("DA Wind & Solar Forecast",
          lambda: client.query_wind_and_solar_forecast(ZONE, start=START, end=END, psr_type=None))

    # 4. DA load forecast
    probe("DA Load Forecast", lambda: client.query_load_forecast(ZONE, start=START, end=END))

    # 5. Actual generation — psr_type=None returns all columns (incl. B18 offshore, B19 onshore, B16 solar)
    probe("Actual Generation (all production types)",
          lambda: client.query_generation(ZONE, start=START, end=END, psr_type=None))

    # 7. Actual load
    probe("Actual Load", lambda: client.query_load(ZONE, start=START, end=END))

    print(f"\nLog written to: {log_path}")
    log_file.close()
    sys.stdout = sys.__stdout__
    print(f"Log written to: {log_path}")

if __name__ == "__main__":
    main()
