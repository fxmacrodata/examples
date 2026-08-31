# FXMacroData — QuantConnect / LEAN Integration

Plug institutional-quality macroeconomic data from [FXMacroData](https://fxmacrodata.com) directly into your [QuantConnect](https://www.quantconnect.com) or local [LEAN](https://lean.io) algorithms.

---

## What's included

| File | Purpose |
|---|---|
| `fxmacrodata/lean.py` | Custom `PythonData` classes for LEAN |
| `fxmacrodata/__init__.py` | Package init |
| `algorithms/01_macro_monitor.py` | Beginner example — plot USD macro indicators (free) |
| `algorithms/02_policy_rate_fx.py` | Strategy — FX carry driven by rate differentials |

---

## Data types

### `FXMacroIndicator`

Macroeconomic indicator time series sourced directly from central banks and statistical agencies.

**Symbol format:** `{CURRENCY}_{INDICATOR}` (case-insensitive)

```python
from fxmacrodata.lean import FXMacroIndicator

# Inside initialize():
usd_rate   = self.add_data(FXMacroIndicator, "USD_POLICY_RATE").symbol
eur_infl   = self.add_data(FXMacroIndicator, "EUR_INFLATION").symbol
aud_gdp    = self.add_data(FXMacroIndicator, "AUD_GDP").symbol
jpy_unemp  = self.add_data(FXMacroIndicator, "JPY_UNEMPLOYMENT").symbol

# Inside on_data(slice):
if slice.contains_key(usd_rate):
    rate = slice[usd_rate].value                          # latest rate reading
    ann  = slice[usd_rate]["announcement_datetime"]       # Unix release timestamp
```

**Access:** USD announcement indicators are public. Non-USD announcement indicators require a Professional API key. See the public documentation for current published currency coverage.

**Common indicators:** `policy_rate`, `inflation`, `core_inflation`, `gdp`, `gdp_quarterly`, `unemployment`, `non_farm_payrolls`, `retail_sales`, `pmi`, `trade_balance`, `ppi`, `cpi`, and [40+ more](https://fxmacrodata.com/documentation).

---

### `FXMacroForex`

Daily FX spot-rate series (ECB reference rates).

**Symbol format:** `{BASE}{QUOTE}` (6-character pair)

```python
from fxmacrodata.lean import FXMacroForex

eurusd = self.add_data(FXMacroForex, "EURUSD").symbol
audusd = self.add_data(FXMacroForex, "AUDUSD").symbol

if slice.contains_key(eurusd):
    spot = slice[eurusd].value
```

**Supported pairs:** any combination of AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY, NZD, PLN, SEK, SGD, USD.

---

### `FXMacroCOT`

CFTC Commitment of Traders (COT) weekly positioning data for FX futures.

**Symbol format:** `{CURRENCY}` (3-char ISO code)

```python
from fxmacrodata.lean import FXMacroCOT

eur_cot = self.add_data(FXMacroCOT, "EUR").symbol
jpy_cot = self.add_data(FXMacroCOT, "JPY").symbol

if slice.contains_key(eur_cot):
    net   = slice[eur_cot].value                  # noncommercial net (longs − shorts)
    longs = slice[eur_cot]["long_positions"]
    oi    = slice[eur_cot]["open_interest"]
```

**Supported currencies:** AUD, CAD, CHF, EUR, GBP, JPY, NZD *(Pro key required)*

---

## Quick start

### Option A — QuantConnect Cloud

1. Create a new project at [quantconnect.com](https://www.quantconnect.com).
2. Upload the following files to your project:
   - `fxmacrodata/__init__.py`
   - `fxmacrodata/lean.py`
   - One of the example algorithms (or your own)
3. Set your API key in **Algorithm Configuration → Environment Variables**:
   ```
   FXMACRODATA_API_KEY = your_key_here
   ```
   *(Skip this step if you only use USD data — it's free.)*
4. Set the **main file** to your chosen algorithm and press **Backtest**.

---

### Option B — Local LEAN (CLI or Docker)

1. Install the [LEAN CLI](https://lean.io/docs/v2/lean-cli/getting-started/installation):
   ```bash
   pip install lean
   lean init
   ```

2. Copy the `fxmacrodata/` package into your LEAN project directory.

3. Install the runtime dependency:
   ```bash
   pip install requests
   ```

4. Export your API key (required for non-USD currencies):
   ```bash
   export FXMACRODATA_API_KEY=your_key_here
   ```

5. Copy an algorithm file into your `Algorithm/` directory and run:
   ```bash
   lean backtest "My Project"
   ```

   On the first run the data provider downloads and caches historical data in
   `<lean-data-folder>/fxmacrodata/`. Subsequent runs load from cache
   instantly.

---

## Data caching

`FXMacroIndicator`, `FXMacroForex`, and `FXMacroCOT` automatically download
the full history from the API on first use and cache it as flat CSV files in
the LEAN data directory:

```
<lean-data-folder>/
└── fxmacrodata/
    ├── indicators/
    │   ├── usd/policy_rate.csv
    │   ├── usd/inflation.csv
    │   └── eur/policy_rate.csv
    ├── forex/
    │   └── eurusd.csv
    └── cot/
        └── eur.csv
```

To force a refresh, delete the relevant CSV file and re-run the algorithm.
For live trading, schedule a periodic cache refresh by deleting and
re-downloading the file before each session start.

---

## API key

| Data | Access |
|---|---|
| USD announcement indicators | Public — no key required |
| FX spot rates | Public |
| Non-USD announcement indicators | Professional plan |
| COT positioning | Professional plan |

[Get your API key →](https://api.fxmacrodata.com-management)

Set the key as an environment variable:

```bash
# Local LEAN
export FXMACRODATA_API_KEY=your_key_here

# QuantConnect Cloud
# Algorithm Configuration → Environment Variables
# FXMACRODATA_API_KEY = your_key_here
```

---

## Example algorithms

### 01 — Macro Monitor (free)

[`algorithms/01_macro_monitor.py`](algorithms/01_macro_monitor.py)

Subscribes to four free USD indicators — policy rate, inflation, unemployment,
and GDP — and plots them on custom QuantConnect charts.  A good starting point
to verify the integration is working before adding a Professional key.

### 02 — Policy Rate Divergence Strategy (Pro)

[`algorithms/02_policy_rate_fx.py`](algorithms/02_policy_rate_fx.py)

Implements a macro-driven FX carry/divergence strategy across AUD/USD,
EUR/USD, and GBP/USD:

- Reads central-bank policy rates monthly via `FXMacroIndicator`.
- Computes rate differentials vs USD for each pair.
- Weights positions proportionally to the differential, capped at 20 % NAV.
- Uses `FXMacroCOT` as an optional sentiment confirmation.
- Includes a realised-vol guard that flattens all FX exposure when SPY
  20-day volatility exceeds 30 %.

---

## Supported indicators (full list)

See [fxmacrodata.com/documentation](https://fxmacrodata.com/documentation) for the complete catalogue.

| Indicator key | Description |
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

---

## Links

- 🌐 [FXMacroData Website](https://fxmacrodata.com)
- 📖 [API Documentation](https://fxmacrodata.com/documentation)
- 🔑 [Get your API key](https://api.fxmacrodata.com-management)
- 📊 [QuantConnect](https://www.quantconnect.com)
- 🚀 [LEAN Engine](https://lean.io)
