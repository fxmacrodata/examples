# FXMacroData × Zipline

Use [FXMacroData](https://fxmacrodata.com) as a data source inside
[zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) backtests.
This integration provides a Zipline bundle for FX spot rates and three
DataFrame loader functions for macro indicators, FX, and commodities.

> **The public demo paths use FX rates and USD announcements, so they run without an API key.**
> Add a [Professional key](https://api.fxmacrodata.com-management) to unlock
> protected non-USD announcements, COT positioning, and commodities data.

---

## Quick start

```bash
pip install -r requirements.txt
python example.py
```

Sample output:

```
FXMacroData × Zipline — Policy Rate Divergence Strategy
──────────────────────────────────────────────────────────────
  Period         : 2022-01-01 → 2026-04-11
  Initial cash   : $100,000
  Instrument     : EUR/USD spot (FXMacroData bundle)
  Signal         : EUR vs USD central-bank rate differential
  Dead-band      : ±0.25 pp
  Rebalance freq : every 21 trading days (≈ 1 month)

Ingesting bundle 'fxmacrodata' from FXMacroData…
Fetching USD policy rate from FXMacroData…
Fetching EUR policy rate from FXMacroData…

Starting backtest: 2022-01-01 → 2026-04-11

──────────────────────────────────────────────────────────────
RESULTS
──────────────────────────────────────────────────────────────
  Final portfolio value  :    $108,241.30
  Total return           :      +8.24%
  Sharpe ratio (ann.)    :        0.531
  Max drawdown           :       -6.18%
  Total orders placed    :           14
──────────────────────────────────────────────────────────────
```

---

## Files

| File | Purpose |
|---|---|
| `fxmacrodata_zipline.py` | Core library — data loaders & bundle registration |
| `example.py` | Runnable strategy (Policy Rate Divergence) |
| `requirements.txt` | Python dependencies |

---

## The data loaders

All three loaders return plain **pandas DataFrames** and work independently of
Zipline — useful for research notebooks, pandas-based analysis, or any other
backtesting framework.

### `fetch_forex`

Daily mid-market FX spot rates from the `/v1/forex/{base}/{quote}` endpoint.

```python
from fxmacrodata_zipline import fetch_forex

df = fetch_forex("EUR", "USD", "2022-01-01", "2024-12-31")
# DatetimeIndex, column: "close"
print(df.tail())
```

---

### `fetch_indicator`

Macroeconomic time series from the `/v1/announcements/{currency}/{indicator}`
endpoint.  Monthly and quarterly releases are **forward-filled to a
business-day daily cadence** so each row holds the most recently released
reading.

```python
from fxmacrodata_zipline import fetch_indicator

inflation = fetch_indicator("USD", "inflation", "2020-01-01", "2024-12-31")
# DatetimeIndex, column: "val" (forward-filled)
print(inflation.loc["2023-07-01", "val"])   # 3.0 (July 2023 CPI YoY %)
```

**Free USD indicators** — no API key needed:

| Slug | Description |
|---|---|
| `inflation` | CPI Inflation (YoY %) |
| `policy_rate` | Fed Funds Rate (%) |
| `gdp` | GDP YoY % |
| `unemployment` | Unemployment Rate (%) |
| `non_farm_payrolls` | Non-Farm Payrolls (k) |
| `retail_sales` | Retail Sales (MoM %) |
| `pmi` | Manufacturing PMI |
| `trade_balance` | Trade Balance (USD mn) |
| … 40+ more | See [full catalogue](https://fxmacrodata.com/documentation) |

---

### `fetch_commodity`

Daily precious-metal spot prices from the `/v1/commodities/{indicator}`
endpoint.

```python
from fxmacrodata_zipline import fetch_commodity

gold = fetch_commodity("gold", "2022-01-01", "2024-12-31")
# DatetimeIndex, column: "close" (USD per troy ounce)
```

Supported: `gold`, `silver`, `platinum`.

---

## The Zipline bundle

`register_fxmacrodata_bundle` creates a Zipline daily-bar bundle with FX spot
rates as tradeable assets.  Each pair is an equity-like instrument where
`open == high == low == close` (mid-market close only) and `volume == 0`.

### Step 1 — Register

Call `register_fxmacrodata_bundle` once, before `run_algorithm`.

```python
from fxmacrodata_zipline import register_fxmacrodata_bundle

register_fxmacrodata_bundle(
    bundle_name="fxmacrodata",       # used in run_algorithm(bundle=...)
    pairs=["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"],
    start_date="2015-01-01",
    api_key=None,                     # public FX data only
)
```

### Step 2 — Ingest

Download and cache the data (once, or when you want to refresh):

```python
from fxmacrodata_zipline import ingest_fxmacrodata_bundle
ingest_fxmacrodata_bundle()          # saves to ~/.zipline/data/fxmacrodata/
```

Or from the command line after adding the registration to
`~/.zipline/extension.py`:

```bash
zipline ingest -b fxmacrodata
```

### Step 3 — Run a strategy

```python
import pandas as pd
from zipline import run_algorithm
from zipline.api import symbol, order_target_percent, record

from fxmacrodata_zipline import fetch_indicator

# Pre-load macro signal (forward-filled DataFrame)
usd_rate = fetch_indicator("USD", "policy_rate", "2020-01-01", "2025-12-31")
usd_infl = fetch_indicator("USD", "inflation",   "2020-01-01", "2025-12-31")


def initialize(context):
    context.eurusd    = symbol("EURUSD")
    context.usd_rate  = usd_rate
    context.usd_infl  = usd_infl
    context.bar_count = 0


def handle_data(context, data):
    context.bar_count += 1
    if context.bar_count % 21 != 0:   # rebalance monthly
        return

    today = data.current_dt.normalize()
    rate_series = context.usd_rate.loc[:today, "val"].dropna()
    infl_series = context.usd_infl.loc[:today, "val"].dropna()

    if rate_series.empty or infl_series.empty:
        return

    rate = float(rate_series.iloc[-1])
    infl = float(infl_series.iloc[-1])
    real_rate = rate - infl    # real policy rate

    # Positive real rate → USD attractive → short EUR/USD
    # Negative real rate → USD unattractive → long EUR/USD
    if real_rate > 0.5:
        order_target_percent(context.eurusd, -0.9)
    elif real_rate < -0.5:
        order_target_percent(context.eurusd, 0.9)
    else:
        order_target_percent(context.eurusd, 0.0)

    record(eurusd=data.current(context.eurusd, "price"),
           real_rate=real_rate)


perf = run_algorithm(
    start=pd.Timestamp("2020-01-01", tz="UTC"),
    end=pd.Timestamp("2025-12-31", tz="UTC"),
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100_000,
    bundle="fxmacrodata",
)

print(perf[["portfolio_value", "eurusd", "real_rate"]].tail(10))
```

---

## Example strategy

`example.py` implements a **Policy Rate Divergence** strategy:

1. Load **EUR/USD** daily spot as the price feed via the FXMacroData bundle.
2. Load **EUR** and **USD central-bank policy rates** as macro signals.
3. Compute the **rate differential** (EUR rate − USD rate) each month.
4. **Long EUR/USD** when EUR rate > USD rate by more than the dead-band (EUR
   carry advantage → EUR relatively bid).
5. **Short EUR/USD** when USD rate > EUR rate by more than the dead-band (USD
   carry advantage → USD relatively bid).
6. **Flat** when rates are within the dead-band.

```bash
# Default run (2022-01-01 → today, $100k capital)
python example.py

# Custom date range
python example.py --start 2020-01-01 --end 2024-12-31

# Use Professional API key (required for EUR policy rate)
python example.py --api-key YOUR_KEY

# Skip bundle re-ingestion (use cached data from a previous run)
python example.py --no-ingest --api-key YOUR_KEY
```

---

## Using macro data in notebooks (no Zipline needed)

The fetch helpers work anywhere pandas is available:

```python
import matplotlib.pyplot as plt
from fxmacrodata_zipline import fetch_forex, fetch_indicator

eurusd = fetch_forex("EUR", "USD", "2020-01-01", "2025-12-31")
infl   = fetch_indicator("USD", "inflation", "2020-01-01", "2025-12-31")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
eurusd["close"].plot(ax=ax1, title="EUR/USD", color="steelblue")
infl["val"].plot(ax=ax2, title="USD CPI Inflation (YoY %)", color="firebrick")
plt.tight_layout()
plt.show()
```

---

## API key

| Data | Access |
|---|---|
| USD announcement indicators | **Public** — no key required (most recent 90 days) |
| FX spot rates (all pairs) | **Public** |
| Non-USD announcement indicators | Professional plan |
| Commodities | Professional plan |
| COT positioning | Professional plan |
| Release calendars | **Public** |

[Get your API key →](https://api.fxmacrodata.com-management)

Set the key as an environment variable (picked up automatically):

```bash
export FXMACRODATA_API_KEY=your_key_here
```

Or pass it explicitly to any loader:

```python
df = fetch_indicator("EUR", "inflation", "2020-01-01", "2025-12-31",
                     api_key="your_key_here")
```

---

## Notes

- **Close-only prices**: The FXMacroData REST API provides daily mid-market
  close prices.  `open`, `high`, and `low` are set equal to `close` in the
  bundle.  Strategies requiring distinct OHLC candles are not applicable.

- **Forward-filling**: `fetch_indicator` reindexes macro releases to business-
  day frequency and forward-fills each bar with the latest released value.
  Bars before the first available observation will have `NaN` — guard against
  these with `pd.isna(val)` or `.dropna()`.

- **Bundle cache**: Ingested data lives in `~/.zipline/data/fxmacrodata/`.
  Delete this directory and re-run `ingest_fxmacrodata_bundle()` to refresh.

- **FX-as-equity model**: Zipline treats each pair as an equity-like instrument.
  Position sizes are in "share" units (e.g. 1000 units of EURUSD = 1000 EUR
  notional).  `order_target_percent` sizes positions as a fraction of NAV.

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Documentation](https://fxmacrodata.com/documentation)
- [Get an API key](https://api.fxmacrodata.com-management)
- [zipline-reloaded docs](https://zipline.ml4trading.io)
- [exchange-calendars](https://github.com/gerrymanoim/exchange_calendars)
