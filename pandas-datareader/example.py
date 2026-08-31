"""
FXMacroData — pandas-datareader Integration Examples
======================================================
Demonstrates all four reader classes plus the DataReader-compatible interface.

USD inflation and policy_rate are free for the most recent 90 days, with no
API key. FX spot rates and commodities require a key.
All other currencies and COT data require a Professional API key.

Get your key at https://api.fxmacrodata.com-management
"""
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
print("\n=== 1. USD Inflation (free) ===")
df_infl = FXMacroDataIndicatorReader("USD/inflation", start=START, end=END).read()
print(df_infl.tail())

print("\n=== 2. USD Policy Rate (free) ===")
df_rate = FXMacroDataIndicatorReader("USD/policy_rate", start=START, end=END).read()
print(df_rate.tail())


# =============================================================================
# 2. Multiple indicators in one call — returns a combined DataFrame
# =============================================================================
print("\n=== 3. Multiple USD indicators in one call ===")
df_multi = FXMacroDataIndicatorReader(
    ["USD/inflation", "USD/policy_rate", "USD/unemployment"],
    start=START,
    end=END,
).read()
print(df_multi.tail())


# =============================================================================
# 3. FX spot rate — standalone reader
# =============================================================================
print("\n=== 4. EUR/USD spot rate (free) ===")
df_fx = FXMacroDataForexReader("EURUSD", start=START, end=END).read()
print(df_fx.tail())

print("\n=== 5. Multiple FX pairs in one call ===")
df_pairs = FXMacroDataForexReader(
    ["EURUSD", "AUDUSD", "GBPUSD"], start=START, end=END
).read()
print(df_pairs.tail())


# =============================================================================
# 4. Precious metals — standalone reader
# =============================================================================
print("\n=== 6. Gold spot price (free) ===")
df_gold = FXMacroDataCommoditiesReader("gold", start=START, end=END).read()
print(df_gold.tail())

print("\n=== 7. All precious metals in one call ===")
df_metals = FXMacroDataCommoditiesReader(
    ["gold", "silver", "platinum"], start=START, end=END
).read()
print(df_metals.tail())


# =============================================================================
# 5. COT positioning — requires API key
# =============================================================================
if API_KEY:
    print("\n=== 8. EUR COT positioning ===")
    df_cot = FXMacroDataCOTReader("EUR", start=START, end=END, api_key=API_KEY).read()
    print(df_cot.tail())
else:
    print("\n=== 8. COT positioning — skipped (no FXMACRODATA_API_KEY set) ===")


# =============================================================================
# 6. Unified get_data_fxmacrodata() — auto-detects type
# =============================================================================
print("\n=== 9. Auto-detection: indicator ===")
df = get_data_fxmacrodata("USD/gdp", start=START, end=END)
print(df.tail())

print("\n=== 10. Auto-detection: FX pair ===")
df = get_data_fxmacrodata("EURUSD", start=START, end=END)
print(df.tail())

print("\n=== 11. Auto-detection: commodity ===")
df = get_data_fxmacrodata("gold", start=START, end=END)
print(df.tail())


# =============================================================================
# 7. DataReader interface (via register())
# =============================================================================
try:
    import pandas_datareader as pdr

    register()  # patch DataReader once

    print("\n=== 12. DataReader: macro indicator ===")
    df = pdr.DataReader("USD/inflation", "fxmacrodata", start=START, end=END)
    print(df.tail())

    print("\n=== 13. DataReader: FX spot rate ===")
    df = pdr.DataReader("EURUSD", "fxmacrodata-forex", start=START, end=END)
    print(df.tail())

    print("\n=== 14. DataReader: precious metal ===")
    df = pdr.DataReader("gold", "fxmacrodata-commodity", start=START, end=END)
    print(df.tail())

    if API_KEY:
        print("\n=== 15. DataReader: COT positioning ===")
        df = pdr.DataReader(
            "EUR", "fxmacrodata-cot", start=START, end=END, api_key=API_KEY
        )
        print(df.tail())

except ImportError:
    print(
        "\n=== DataReader examples skipped "
        "(pandas-datareader not installed — pip install pandas-datareader) ==="
    )


# =============================================================================
# 8. Pro tier — multi-currency comparison (requires API key)
# =============================================================================
if API_KEY:
    print("\n=== 16. Multi-currency policy rate comparison (Pro) ===")
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
        print(combined.tail())
else:
    print(
        "\n=== 16. Multi-currency comparison skipped "
        "(set FXMACRODATA_API_KEY to run) ==="
    )
