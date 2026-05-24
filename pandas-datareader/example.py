"""
FXMacroData — pandas-datareader Integration Examples
======================================================
Demonstrates all four reader classes plus the DataReader-compatible interface.

USD data (inflation, policy_rate, forex) is **free** — no API key required.
All other currencies and COT data require a Professional API key.

Get your key at https://fxmacrodata.com/api-management
"""
import logging
import sys

__copilot_logger = logging.getLogger(__name__)

def __copilot_log_print(*args, sep=" ", end="\n", file=None, flush=False):
    message = sep.join(str(arg) for arg in args)
    if end and end != "\n":
        message += end.rstrip("\n")
    stream = file if file is not None else sys.stdout
    level = logging.ERROR if stream is sys.stderr else logging.INFO
    __copilot_logger.log(level, message)


import os
import datetime

import pandas as pd

# ── Import the integration ────────────────────────────────────────────────────
from fxmacrodata_datareader import (
    FXMacroDataIndicatorReader,
    FXMacroDataForexReader,
    FXMacroDataCommoditiesReader,
    FXMacroDataCOTReader,
    get_data_fxmacrodata,
    register,
)

# Optional: load your API key from the environment
API_KEY = os.environ.get("FXMACRODATA_API_KEY")

# Date window used in all examples
START = "2022-01-01"
END = datetime.date.today().isoformat()


# =============================================================================
# 1. Macro indicator — standalone reader
# =============================================================================
__copilot_log_print("\n=== 1. USD Inflation (free) ===")
df_infl = FXMacroDataIndicatorReader("USD/inflation", start=START, end=END).read()
__copilot_log_print(df_infl.tail())

__copilot_log_print("\n=== 2. USD Policy Rate (free) ===")
df_rate = FXMacroDataIndicatorReader("USD/policy_rate", start=START, end=END).read()
__copilot_log_print(df_rate.tail())


# =============================================================================
# 2. Multiple indicators in one call — returns a combined DataFrame
# =============================================================================
__copilot_log_print("\n=== 3. Multiple USD indicators in one call ===")
df_multi = FXMacroDataIndicatorReader(
    ["USD/inflation", "USD/policy_rate", "USD/unemployment"],
    start=START,
    end=END,
).read()
__copilot_log_print(df_multi.tail())


# =============================================================================
# 3. FX spot rate — standalone reader
# =============================================================================
__copilot_log_print("\n=== 4. EUR/USD spot rate (free) ===")
df_fx = FXMacroDataForexReader("EURUSD", start=START, end=END).read()
__copilot_log_print(df_fx.tail())

__copilot_log_print("\n=== 5. Multiple FX pairs in one call ===")
df_pairs = FXMacroDataForexReader(
    ["EURUSD", "AUDUSD", "GBPUSD"], start=START, end=END
).read()
__copilot_log_print(df_pairs.tail())


# =============================================================================
# 4. Precious metals — standalone reader
# =============================================================================
__copilot_log_print("\n=== 6. Gold spot price (free) ===")
df_gold = FXMacroDataCommoditiesReader("gold", start=START, end=END).read()
__copilot_log_print(df_gold.tail())

__copilot_log_print("\n=== 7. All precious metals in one call ===")
df_metals = FXMacroDataCommoditiesReader(
    ["gold", "silver", "platinum"], start=START, end=END
).read()
__copilot_log_print(df_metals.tail())


# =============================================================================
# 5. COT positioning — requires API key
# =============================================================================
if API_KEY:
    __copilot_log_print("\n=== 8. EUR COT positioning ===")
    df_cot = FXMacroDataCOTReader("EUR", start=START, end=END, api_key=API_KEY).read()
    __copilot_log_print(df_cot.tail())
else:
    __copilot_log_print("\n=== 8. COT positioning — skipped (no FXMACRODATA_API_KEY set) ===")


# =============================================================================
# 6. Unified get_data_fxmacrodata() — auto-detects type
# =============================================================================
__copilot_log_print("\n=== 9. Auto-detection: indicator ===")
df = get_data_fxmacrodata("USD/gdp", start=START, end=END)
__copilot_log_print(df.tail())

__copilot_log_print("\n=== 10. Auto-detection: FX pair ===")
df = get_data_fxmacrodata("EURUSD", start=START, end=END)
__copilot_log_print(df.tail())

__copilot_log_print("\n=== 11. Auto-detection: commodity ===")
df = get_data_fxmacrodata("gold", start=START, end=END)
__copilot_log_print(df.tail())


# =============================================================================
# 7. DataReader interface (via register())
# =============================================================================
try:
    import pandas_datareader as pdr

    register()  # patch DataReader once

    __copilot_log_print("\n=== 12. DataReader: macro indicator ===")
    df = pdr.DataReader("USD/inflation", "fxmacrodata", start=START, end=END)
    __copilot_log_print(df.tail())

    __copilot_log_print("\n=== 13. DataReader: FX spot rate ===")
    df = pdr.DataReader("EURUSD", "fxmacrodata-forex", start=START, end=END)
    __copilot_log_print(df.tail())

    __copilot_log_print("\n=== 14. DataReader: precious metal ===")
    df = pdr.DataReader("gold", "fxmacrodata-commodity", start=START, end=END)
    __copilot_log_print(df.tail())

    if API_KEY:
        __copilot_log_print("\n=== 15. DataReader: COT positioning ===")
        df = pdr.DataReader(
            "EUR", "fxmacrodata-cot", start=START, end=END, api_key=API_KEY
        )
        __copilot_log_print(df.tail())

except ImportError:
    __copilot_log_print(
        "\n=== DataReader examples skipped "
        "(pandas-datareader not installed — pip install pandas-datareader) ==="
    )


# =============================================================================
# 8. Pro tier — multi-currency comparison (requires API key)
# =============================================================================
if API_KEY:
    __copilot_log_print("\n=== 16. Multi-currency policy rate comparison (Pro) ===")
    currencies = ["USD", "EUR", "GBP", "AUD", "JPY"]
    series = {}
    for ccy in currencies:
        df_r = FXMacroDataIndicatorReader(
            f"{ccy}/policy_rate", start=START, end=END, api_key=API_KEY
        ).read()
        if not df_r.empty:
            series[ccy] = df_r["val"]
    if series:
        combined = pd.DataFrame(series)
        __copilot_log_print(combined.tail())
else:
    __copilot_log_print(
        "\n=== 16. Multi-currency comparison skipped "
        "(set FXMACRODATA_API_KEY to run) ==="
    )
