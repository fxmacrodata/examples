# FXMacroData × Blankly

Use [FXMacroData](https://fxmacrodata.com) as a data source inside
[Blankly](https://blankly.finance) backtests.  This integration provides
data-loader helpers for every public FXMacroData endpoint plus a
`KeylessExchange` factory that lets you run fully keyless backtests with
no brokerage account required.

> **USD announcement data is public for the most recent 90 days. EUR/USD spot
> rates need an API key.**
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
FXMacroData × Blankly — Inflation Signal Strategy
──────────────────────────────────────────────────────────────
  Period         : 2024-06-01 → 2026-04-17
  Initial cash   : $100,000
  Instrument     : EUR/USD spot
  Signal         : USD CPI inflation 3-month momentum (free data)
  Lookback       : 66 business days (≈ 3 months)
  Threshold      : ±0.1 pp

Fetching EUR/USD spot rates from FXMacroData…
Fetching USD CPI inflation from FXMacroData…

Starting portfolio value: $100,000.00

──────────────────────────────────────────────────────────────
RESULTS
──────────────────────────────────────────────────────────────
  Final portfolio value  :    $108,210.40
  Total return           :      +8.21%
  Sharpe ratio           :        0.431
  Max drawdown           :       -7.15%
  Total trades           :           12
──────────────────────────────────────────────────────────────
```

---

## Files

| File | Purpose |
|---|---|
| `fxmacrodata_blankly.py` | Core library — data fetchers, exchange factory, macro signal helper |
| `example.py` | Runnable example strategy (Inflation Signal) |
| `requirements.txt` | Python dependencies |

---

## The data helpers

### `fetch_forex`

Daily mid-market FX spot rates from the `/v1/forex/{base}/{quote}` endpoint,
returned as a blankly-compatible OHLCV DataFrame with a Unix `time` column.

```python
from fxmacrodata_blankly import fetch_forex

df = fetch_forex("EUR", "USD", "2022-01-01", "2024-12-31")
# columns: time (epoch), open, high, low, close, volume
```

Pass the DataFrame directly to `create_exchange` to avoid a double API call:

```python
exchange = create_exchange("EUR", "USD", df=df)
```

---

### `fetch_indicator`

Macroeconomic time series from the `/v1/announcements/{currency}/{indicator}`
endpoint.  Monthly and quarterly releases are **forward-filled to a
business-day daily cadence** so each row holds the most recently released
reading.

```python
from fxmacrodata_blankly import fetch_indicator

inflation = fetch_indicator("USD", "inflation", "2022-01-01", "2024-12-31")
# DatetimeIndex, column: "val" (forward-filled)
```

Use `get_macro_signal` inside strategy callbacks to read values without
look-ahead bias:

```python
val = get_macro_signal(inflation, state.time)  # state.time is Unix epoch
```

**Free USD indicators** — no API key needed:

| Slug | Description |
|---|---|
| `inflation` | CPI Inflation (YoY %) |
| `policy_rate` | Fed Funds Rate (%) |
| `gdp` | GDP (USD bn) |
| `unemployment` | Unemployment Rate (%) |
| `non_farm_payrolls` | Non-Farm Payrolls (k) |
| `retail_sales` | Retail Sales (MoM %) |
| `pmi` | Manufacturing PMI |
| `trade_balance` | Trade Balance (USD mn) |
| …40+ more | See [full catalogue](https://fxmacrodata.com/documentation) |

---

### `fetch_commodity`

Daily precious-metal spot prices from the `/v1/commodities/{indicator}`
endpoint.  Returns a blankly-compatible OHLCV DataFrame.  Requires a
Professional API key.

```python
from fxmacrodata_blankly import fetch_commodity

gold = fetch_commodity("gold", "2022-01-01", "2024-12-31", api_key="YOUR_KEY")
```

Supported: `gold`, `silver`, `platinum`.

---

### `create_exchange`

Creates a `blankly.KeylessExchange` for one FX pair backed by FXMacroData
daily spot rates.  No brokerage account or API keys are needed for most pairs.

```python
from fxmacrodata_blankly import create_exchange
import blankly

exchange = create_exchange("EUR", "USD", "2022-01-01", "2024-12-31")
strategy = blankly.Strategy(exchange)
```

---

### `get_macro_signal`

Retrieves the most recently available macro value as of a given timestamp.
Designed for use inside blankly `price_event` and `init` functions to avoid
look-ahead bias.

```python
from fxmacrodata_blankly import get_macro_signal

def price_event(price, symbol, state: blankly.StrategyState):
    val = get_macro_signal(state.variables['inflation'], state.time)
    if val is None:
        return  # no data yet
    # … use val in your logic …
```

---

## Example strategy

`example.py` implements an **Inflation Signal** strategy:

1. Load **EUR/USD** daily spot as the price feed (free).
2. Load **US CPI inflation** as a macro signal (free).
3. Compute **3-month momentum** on the forward-filled daily inflation series.
4. **Short EUR/USD** when 3-month inflation delta is positive (rising inflation →
   Fed likely hawkish → USD strengthening).
5. **Long EUR/USD** when 3-month inflation delta is negative (falling inflation →
   Fed likely dovish → USD weakening).

```bash
# Default run (2024-06-01 → today, $100k capital)
python example.py

# Custom date range
python example.py --start 2023-01-01 --end 2025-12-31

# With a Professional API key (unlocks all 18 currencies)
python example.py --api-key YOUR_KEY
```

---

## Build your own strategy

```python
import blankly
from fxmacrodata_blankly import (
    create_exchange,
    fetch_indicator,
    get_macro_signal,
)

# ── Pre-fetch macro data ───────────────────────────────────────────────────────
start, end = "2022-01-01", "2024-12-31"
inflation = fetch_indicator("USD", "inflation",   start, end)
fed_rate  = fetch_indicator("USD", "policy_rate", start, end)


# ── Strategy callbacks ────────────────────────────────────────────────────────
def init(symbol, state: blankly.StrategyState):
    state.variables["inflation"] = inflation
    state.variables["fed_rate"]  = fed_rate
    state.variables["in_trade"]  = False


def price_event(price, symbol, state: blankly.StrategyState):
    infl = get_macro_signal(state.variables["inflation"], state.time)
    rate = get_macro_signal(state.variables["fed_rate"],  state.time)

    if infl is None or rate is None:
        return

    real_rate = rate - infl   # real (inflation-adjusted) policy rate

    interface = state.interface
    size      = max(1, int(5_000 / price))

    if real_rate < -0.5 and not state.variables["in_trade"]:
        # Negative real rate → dovish → long EUR/USD
        interface.market_order(symbol, side="buy", size=size)
        state.variables["in_trade"] = True
    elif real_rate > 0.5 and state.variables["in_trade"]:
        curr = interface.account[state.base_asset].available
        if curr > 0:
            interface.market_order(symbol, side="sell", size=int(curr))
        state.variables["in_trade"] = False


# ── Run ───────────────────────────────────────────────────────────────────────
exchange = create_exchange("EUR", "USD", start, end)
strategy = blankly.Strategy(exchange)
if not hasattr(strategy, "globals"):
    strategy.globals = {}

strategy.add_price_event(price_event, symbol="EUR-USD", resolution="1d", init=init)

results = strategy.backtest(
    start_date=start,
    end_date=end,
    initial_values={"USD": 100_000},
    GUI_output=False,
)
print(results)
```

---

## Notes

- **Close-only feeds**: The FXMacroData REST API provides daily mid-market close
  prices, not OHLCV candles.  `open`, `high`, and `low` are set equal to `close`
  in the OHLCV DataFrame written to the `PriceReader`.  Strategies or indicators
  that require distinct OHLCV bars (e.g. candlestick patterns) are not applicable
  here.

- **Forward-filling**: Macro indicators are released monthly or quarterly.
  `fetch_indicator()` reindexes to business-day frequency and forward-fills each
  row with the latest released value.  Rows before the first available observation
  will have `NaN` — `get_macro_signal` returns `None` in those cases.

- **`state.globals`**: Blankly strategies share state across symbols via
  `state.variables`.  Pre-fetched macro DataFrames are stored there in `init` and
  read in `price_event`.  See `example.py` for a working pattern.

- **Keyless exchange**: `create_exchange` uses a `blankly.KeylessExchange` backed
  by a temporary CSV, so no brokerage credentials are required.

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Documentation](https://fxmacrodata.com/documentation)
- [Get an API key](https://fxmacrodata.com/api-management)
- [Blankly docs](https://docs.blankly.finance)
- [Blankly GitHub](https://github.com/Blankly-Finance/Blankly)
