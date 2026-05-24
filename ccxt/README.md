# FXMacroData × CCXT

Use [FXMacroData](https://fxmacrodata.com) through the familiar
[CCXT](https://github.com/ccxt/ccxt) unified interface.  This integration
provides a drop-in CCXT exchange adapter so any existing CCXT-based trading
or analysis code can consume FXMacroData FX spot rates, commodity prices, and
macroeconomic indicator series with minimal changes.

> **Public FX routes and USD announcements work without an API key.**
> Add a [Professional key](https://fxmacrodata.com/api-management) to unlock
> protected non-USD announcements, COT positioning, and commodities data.

---

## Quick start

```bash
pip install -r requirements.txt
python example.py
```

Sample output:

```
FXMacroData × CCXT — Macro Carry Scanner
────────────────────────────────────────────────────────
  All data via standard CCXT interface
  EUR/USD, GBP/USD, XAU/USD  ·  USD inflation & policy rate
  No API key required — USD data is always free

Loading markets…
  30 FX pairs  |  3 commodity pairs

Fetching current rates for 7 symbols…
Fetching EUR/USD OHLCV…
Fetching USD CPI inflation…
Fetching USD policy rate…

────────────────────────────────────────────────────────
  Symbol         Last rate    1d change
────────────────────────────────────────────────────────
  EUR/USD          1.08542      +0.23%
  GBP/USD          1.26841      +0.15%
  AUD/USD          0.64231      -0.08%
  USD/JPY        151.42000      +0.31%
  USD/CHF          0.90122      -0.11%
  USD/CAD          1.36540      +0.04%
  XAU/USD       2341.50000      +0.62%
────────────────────────────────────────────────────────

  Macro snapshot (USD, latest released values)
────────────────────────────────────────────────────────
  CPI inflation (YoY)      :    2.40 %
  Inflation 3m momentum    :   -0.30 pp
  Fed policy rate          :    4.33 %
  Rate 6m change           :   -0.50 pp
  USD real rate (rate-CPI) :   +1.93 pp
────────────────────────────────────────────────────────

  Signal  ↓  SELL EUR/USD
  Why       USD real rate attractive → USD bullish
```

---

## Files

| File | Purpose |
|---|---|
| `fxmacrodata_ccxt.py` | Core adapter — CCXT exchange class |
| `example.py` | Runnable macro carry scanner |
| `requirements.txt` | Python dependencies |

---

## The CCXT adapter

### Instantiation

```python
from fxmacrodata_ccxt import fxmacrodata

# No key — public FX endpoints and USD announcements only
exchange = fxmacrodata()

# With a Professional API key (unlocks protected endpoints)
exchange = fxmacrodata({'apiKey': 'YOUR_KEY'})

# Or via environment variable (picked up automatically)
# export FXMACRODATA_API_KEY=your_key_here
exchange = fxmacrodata()
```

---

### `load_markets()` / `fetch_markets()`

Returns all available FX pairs and commodity markets in the standard CCXT
unified market structure.  No API request is made — the catalogue is static.

```python
markets = exchange.load_markets()

# List all FX symbols
fx = [s for s, m in markets.items() if m['info']['type'] == 'forex']
print(fx)
# ['EUR/USD', 'GBP/USD', 'AUD/USD', ...]

# List commodity symbols
comms = [s for s, m in markets.items() if m['info']['type'] == 'commodity']
print(comms)
# ['XAU/USD', 'XAG/USD', 'XPT/USD']
```

**Available markets (33 total)**

| Type | Examples |
|---|---|
| FX majors | EUR/USD, GBP/USD, AUD/USD, NZD/USD, USD/JPY, USD/CHF, USD/CAD |
| FX crosses | EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, … (23 pairs) |
| Commodities | XAU/USD (gold), XAG/USD (silver), XPT/USD (platinum) |

---

### `fetch_ohlcv(symbol, timeframe, since, limit)`

Fetch daily mid-market candles.  Because FXMacroData provides end-of-day
close prices only, `open == high == low == close` and `volume == 0`.

```python
# Last 90 trading days of EUR/USD
ohlcv = exchange.fetch_ohlcv('EUR/USD', '1d', limit=90)
ts, o, h, l, close, vol = ohlcv[-1]

# From a specific date
import datetime
since = int(datetime.datetime(2023, 1, 1,
                               tzinfo=datetime.timezone.utc).timestamp() * 1000)
ohlcv = exchange.fetch_ohlcv('EUR/USD', '1d', since=since)

# Gold (XAU/USD)
gold = exchange.fetch_ohlcv('XAU/USD', '1d', limit=252)

# Convert to pandas
import pandas as pd
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df.index = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
```

> **Note**: Only `'1d'` is supported as the timeframe.  Passing any other
> value raises `ccxt.NotSupported`.

---

### `fetch_ticker(symbol)`

Fetch the latest mid-market rate for a single symbol.

```python
ticker = exchange.fetch_ticker('EUR/USD')
print(ticker['last'])      # latest close
print(ticker['change'])    # 1-day change (absolute)
print(ticker['percentage']) # 1-day change (%)
```

Standard CCXT ticker keys returned: `symbol`, `timestamp`, `datetime`,
`last`, `close`, `open` (previous close), `change`, `percentage`, `average`.
Bid/ask and volume fields are `None` — FXMacroData is a data feed, not a
live exchange.

---

### `fetch_tickers(symbols)`

Fetch tickers for multiple symbols in one call.

```python
tickers = exchange.fetch_tickers(['EUR/USD', 'GBP/USD', 'XAU/USD'])
for sym, t in tickers.items():
    print(f"{sym}  {t['last']:.5f}  {t['percentage']:+.2f}%")
```

When `symbols=None`, the 7 major FX pairs are returned by default.

---

### `fetch_macro_indicator(currency, indicator, start_date, end_date)`

Custom extension for macroeconomic time series.  Not part of the standard
CCXT unified API.

```python
# USD CPI inflation (free)
rows = exchange.fetch_macro_indicator('USD', 'inflation',
                                      '2020-01-01', '2025-12-31')
print(rows[-1])
# {'date': '2025-02-12', 'val': 2.8, 'announcement_datetime': '2025-02-12T13:30:00Z'}

# USD policy rate (free)
rates = exchange.fetch_macro_indicator('USD', 'policy_rate',
                                       '2022-01-01', '2025-12-31')

# EUR inflation (requires Pro key)
eur_infl = exchange.fetch_macro_indicator('EUR', 'inflation',
                                          '2022-01-01', '2025-12-31',
                                          api_key='YOUR_KEY')
```

**Free USD indicators (sample)**

| Slug | Description |
|---|---|
| `inflation` | CPI Inflation (YoY %) |
| `policy_rate` | Fed Funds Rate (%) |
| `gdp` | GDP (annual YoY %) |
| `unemployment` | Unemployment Rate (%) |
| `non_farm_payrolls` | Non-Farm Payrolls (k) |
| `retail_sales` | Retail Sales (MoM %) |
| `pmi` | ISM Manufacturing PMI |
| `trade_balance` | Trade Balance (USD mn) |
| `core_inflation` | Core CPI (YoY %) |
| `housing_starts` | Housing Starts (k) |
| `industrial_production` | Industrial Production (YoY %) |
| `consumer_confidence` | Conference Board Consumer Confidence |
| … 30+ more | See [full catalogue](https://fxmacrodata.com/documentation) |

---

## Using the adapter in existing CCXT code

The adapter implements the same interface as any other CCXT exchange.  Drop
it in wherever you use a CCXT exchange object.

```python
import pandas as pd
from fxmacrodata_ccxt import fxmacrodata

# ── Data collection ───────────────────────────────────────────────
exchange = fxmacrodata()
exchange.load_markets()

pairs = ['EUR/USD', 'GBP/USD', 'AUD/USD', 'USD/JPY']
frames = {}
for pair in pairs:
    ohlcv = exchange.fetch_ohlcv(pair, '1d', limit=252)
    df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
    df.index = pd.to_datetime(df['ts'], unit='ms', utc=True)
    frames[pair] = df['c']

closes = pd.DataFrame(frames)
print(closes.tail())
```

---

## Combining CCXT data with macro signals

```python
import pandas as pd
from fxmacrodata_ccxt import fxmacrodata

exchange = fxmacrodata()

# FX data via standard CCXT
ohlcv = exchange.fetch_ohlcv('EUR/USD', '1d', limit=500)
eurusd = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'close', 'v'])
eurusd.index = pd.to_datetime(eurusd['ts'], unit='ms', utc=True)

# Macro data via custom extension
infl_rows = exchange.fetch_macro_indicator('USD', 'inflation',
                                           '2023-01-01', '2025-12-31')
infl = pd.DataFrame(infl_rows).set_index(pd.to_datetime(
    [r['date'] for r in infl_rows]
))['val'].sort_index()

# Forward-fill macro to daily cadence
infl_daily = infl.reindex(eurusd.index.normalize()).ffill()

# Compute signal: short EUR/USD when inflation rising fast
delta = infl_daily.diff(66)   # 3-month momentum (≈ 66 trading days)
signal = delta.apply(lambda x: -1 if x > 0.3 else (1 if x < -0.3 else 0))
print(signal.tail(10))
```

---

## API key

| Data | Access |
|---|---|
| USD announcement indicators | **Public** — no key required |
| FX spot rates (all pairs) | **Public** |
| Non-USD announcement indicators | Professional plan |
| Commodities | Professional plan |
| COT positioning | Professional plan |
| Release calendars | **Public** |

[Get your API key →](https://fxmacrodata.com/api-management)

Set the key as an environment variable (picked up automatically):

```bash
export FXMACRODATA_API_KEY=your_key_here
```

Or pass it at construction time:

```python
exchange = fxmacrodata({'apiKey': 'your_key_here'})
```

---

## Example options

```bash
# Default run (60-day lookback, with gold)
python example.py

# Wider lookback window
python example.py --lookback 120

# Exclude gold from the rates table
python example.py --no-gold

# Use a Pro key (unlocks all 18 currencies)
python example.py --api-key YOUR_KEY
```

---

## Notes

- **Close-only data**: FXMacroData provides daily mid-market close prices.
  `open`, `high`, and `low` are set equal to `close`.  Strategies that
  require distinct OHLC bars (e.g. candlestick patterns) are not applicable.

- **Timeframe**: Only `'1d'` is supported.  Passing any other value raises
  `ccxt.NotSupported`.

- **Volume**: `volume` is always `0` — FXMacroData is a data feed, not a
  live exchange.  Strategies that rely on volume signals are not applicable.

- **Bid/ask spread**: `bid`, `ask`, and related keys in tickers are `None`.

- **Rate limiting**: FXMacroData applies standard REST rate limits.  Avoid
  calling `fetch_tickers()` for all 33 markets in rapid succession.  The
  adapter respects CCXT's built-in `rateLimit` setting (200 ms by default).

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Documentation](https://fxmacrodata.com/documentation)
- [Get an API key](https://fxmacrodata.com/api-management)
- [CCXT docs](https://docs.ccxt.com)
- [CCXT GitHub](https://github.com/ccxt/ccxt)
