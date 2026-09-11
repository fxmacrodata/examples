# FXMacroData — pandas-datareader Integration

Use FXMacroData as a pandas-datareader-compatible data source inside any
Python workflow that already relies on
[pandas-datareader](https://pandas-datareader.readthedocs.io/).

---

## Install

```bash
pip install -r requirements.txt
```

Or just the bare minimum (standalone readers, no `DataReader` patching):

```bash
pip install pandas requests
```

### pandas-datareader compatibility

The standalone reader classes (`FXMacroDataIndicatorReader`, etc.) and
`get_data_fxmacrodata()` work with **any recent version of pandas**.

The `register()` / `DataReader` interface requires
[pandas-datareader](https://pandas-datareader.readthedocs.io/).
`pandas-datareader` 0.10.0 is only compatible with **pandas < 3.0**.
If you need the `DataReader` interface, pin an older pandas version:

```bash
pip install "pandas<3" pandas-datareader requests
```

---

## Quick start

```python
import fxmacrodata_datareader as fxmd

# USD announcement data is public — no API key needed
df = fxmd.get_data_fxmacrodata("USD/inflation", "2020-01-01", "2025-12-31")
print(df.head())
#                     val  announcement_datetime
# date
# 2020-01-31    2.5       1580400000
# 2020-02-29    2.3       1583078400
```

---

## DataReader interface

Calling `fxmd.register()` once patches
`pandas_datareader.data.DataReader` so you can use FXMacroData like any
built-in data source:

```python
import pandas_datareader as pdr
import fxmacrodata_datareader as fxmd

fxmd.register()  # one-time patch

# Macro indicator (USD announcements are public)
df = pdr.DataReader("USD/inflation", "fxmacrodata", start, end)

# With API key
df = pdr.DataReader("EUR/policy_rate", "fxmacrodata", start, end,
                    api_key="YOUR_KEY")

# FX spot rate
df = pdr.DataReader("EURUSD", "fxmacrodata-forex", start, end)

# Precious metal
df = pdr.DataReader("gold", "fxmacrodata-commodity", start, end)

# COT positioning (requires API key)
df = pdr.DataReader("EUR", "fxmacrodata-cot", start, end, api_key="YOUR_KEY")
```

---

## Data types

### Macro indicators — `FXMacroDataIndicatorReader`

Macroeconomic time series sourced directly from central banks and
statistical agencies.

**Symbol format:** `"{CURRENCY}/{indicator}"` or `"{CURRENCY}_{indicator}"`

```python
from fxmacrodata_datareader import FXMacroDataIndicatorReader

# Single indicator
df = FXMacroDataIndicatorReader("USD/inflation",
                                start="2020-01-01", end="2025-12-31").read()

# Multiple indicators — returns a combined DataFrame (one column per series)
df = FXMacroDataIndicatorReader(
    ["USD/inflation", "USD/policy_rate", "USD/unemployment"],
    start="2020-01-01", end="2025-12-31",
).read()
```

**Returned columns:** `val`, `announcement_datetime`, `pct_change`,
`pct_change_12m` (where available).

**Access:** USD announcement indicators are public. Non-USD announcement
indicators require a Professional API key. See the public documentation for
current published currency coverage.

**Common indicators:**

| Key | Description |
|---|---|
| `policy_rate` | Central-bank benchmark rate |
| `inflation` | CPI YoY % |
| `core_inflation` | Core CPI YoY % |
| `gdp` | GDP YoY % |
| `gdp_quarterly` | GDP QoQ % |
| `unemployment` | Unemployment rate % |
| `non_farm_payrolls` | US Non-Farm Payrolls (k) |
| `retail_sales` | Retail sales MoM % |
| `pmi` | Manufacturing PMI |
| `trade_balance` | Trade balance |
| `ppi` | Producer price index YoY % |
| `current_account_balance` | Current account balance |
| `gov_bond_10y` | 10-year government bond yield |
| `breakeven_inflation_rate` | 10-year breakeven inflation |
| `consumer_confidence` | Consumer confidence index |

Full catalogue: [fxmacrodata.com/documentation](https://fxmacrodata.com/documentation)

---

### FX spot rates — `FXMacroDataForexReader`

Daily ECB reference rates for major FX pairs.

**Symbol format:** `"EURUSD"` (6 chars) or `"EUR/USD"` (slash-separated)

```python
from fxmacrodata_datareader import FXMacroDataForexReader

# Single pair
df = FXMacroDataForexReader("EURUSD", start="2020-01-01", end="2025-12-31").read()

# Multiple pairs — returns a combined DataFrame (one column per pair)
df = FXMacroDataForexReader(
    ["EURUSD", "GBPUSD", "AUDUSD"],
    start="2020-01-01", end="2025-12-31",
).read()
```

**Returned column:** `val` (daily mid-market spot rate).

**Supported currencies:** AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY,
NZD, PLN, SEK, SGD, USD.

---

### Precious metals — `FXMacroDataCommoditiesReader`

Daily LBMA fix / spot prices in USD per troy ounce.

**Symbols:** `"gold"`, `"silver"`, `"platinum"`

```python
from fxmacrodata_datareader import FXMacroDataCommoditiesReader

# Single commodity
df = FXMacroDataCommoditiesReader("gold",
                                  start="2020-01-01", end="2025-12-31").read()

# Multiple commodities — returns a combined DataFrame (one column per metal)
df = FXMacroDataCommoditiesReader(
    ["gold", "silver", "platinum"],
    start="2020-01-01", end="2025-12-31",
).read()
```

**Returned columns:** `val`, `pct_change`, `pct_change_12m` (where available).

---

### CFTC COT positioning — `FXMacroDataCOTReader`

Weekly CFTC Legacy Futures-Only Commitment of Traders report for FX futures.

**Symbol:** 3-letter currency code — `"EUR"`, `"GBP"`, `"JPY"`, etc.

```python
from fxmacrodata_datareader import FXMacroDataCOTReader

df = FXMacroDataCOTReader("EUR", start="2020-01-01", end="2025-12-31",
                          api_key="YOUR_KEY").read()
```

**Returned columns:** `net_noncommercial`, `long_noncommercial`,
`short_noncommercial`, `open_interest`, `long_commercial`,
`short_commercial`.

**Supported currencies:** AUD, CAD, CHF, EUR, GBP, JPY, NZD
*(Professional key required)*

---

## Unified convenience function

`get_data_fxmacrodata()` auto-detects the data type from the symbol format:

```python
import fxmacrodata_datareader as fxmd

# Indicator  →  "USD/inflation" or "USD_inflation"
df = fxmd.get_data_fxmacrodata("USD/inflation", "2020-01-01", "2025-12-31")

# FX pair    →  6-char string or slash-separated
df = fxmd.get_data_fxmacrodata("EURUSD", "2020-01-01", "2025-12-31")

# Commodity  →  "gold", "silver", or "platinum"
df = fxmd.get_data_fxmacrodata("gold", "2020-01-01", "2025-12-31")

# Override auto-detection with data_type=
df = fxmd.get_data_fxmacrodata("EUR", "2020-01-01", "2025-12-31",
                                data_type="cot", api_key="YOUR_KEY")
```

---

## API key

| Data | Access |
|---|---|
| USD announcement indicators | Public — no key needed |
| Major FX pairs | Public — no key needed |
| Precious metals | Professional plan |
| Non-USD announcement indicators | Professional plan |
| COT positioning data | Professional plan |

[Get your API key →](https://api.fxmacrodata.com-management)

Set the key as an environment variable so you never have to hardcode it:

```bash
export FXMACRODATA_API_KEY=your_key_here
```

Or pass it explicitly:

```python
df = FXMacroDataIndicatorReader("EUR/policy_rate", api_key="YOUR_KEY").read()
```

---

## Run the examples

```bash
pip install -r requirements.txt
python example.py
```

Set `FXMACRODATA_API_KEY` first to also run the Pro-tier examples.

---

## Links

- 🌐 [FXMacroData Website](https://fxmacrodata.com)
- 📖 [API Documentation](https://fxmacrodata.com/documentation)
- 🔑 [Get your API key](https://api.fxmacrodata.com-management)
- 📦 [pandas-datareader](https://pandas-datareader.readthedocs.io/)
