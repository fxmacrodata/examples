# FXMacroData × Backtrader

Use [FXMacroData](https://fxmacrodata.com) as a data source inside
[Backtrader](https://www.backtrader.com/) backtests.  This integration provides
three ready-to-use `PandasData` feed classes and loader helpers for every
public FXMacroData endpoint.

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
FXMacroData × Backtrader — Inflation Signal Strategy
──────────────────────────────────────────────────────────────
  Period         : 2024-06-01 → 2026-04-11
  Initial cash   : $100,000
  Instrument     : EUR/USD spot
  Signal         : USD CPI inflation 3-month momentum (free data)
  Commission     : ≈ 1.5 pip spread

Fetching EUR/USD spot rates from FXMacroData…
Fetching USD policy rate from FXMacroData…

Starting portfolio value: $100,000.00

...

──────────────────────────────────────────────────────────────
RESULTS
──────────────────────────────────────────────────────────────
  Final portfolio value  :    $107,432.10
  Total return           :      +7.43%
  Sharpe ratio           :        0.412
  Max drawdown           :       -8.23%
  Total closed trades    :            6
  Win rate               :       66.7%
  Avg net P&L per trade  :    $1,238.68
──────────────────────────────────────────────────────────────
```

---

## Files

| File | Purpose |
|---|---|
| `fxmacrodata_bt.py` | Core library — data feeds & loader functions |
| `example.py` | Runnable example strategy (Policy Rate Divergence) |
| `requirements.txt` | Python dependencies |

---

## The data feeds

### `FXSpotData`

Daily mid-market FX spot rates from the `/v1/forex/{base}/{quote}` endpoint.

```python
from fxmacrodata_bt import load_forex

eurusd = load_forex("EUR", "USD", "2020-01-01", "2024-12-31")
cerebro.adddata(eurusd, name="EURUSD")
```

Access in strategy:

```python
price = self.data.close[0]   # today's EUR/USD rate
```

---

### `MacroIndicatorData`

Macroeconomic time series from the `/v1/announcements/{currency}/{indicator}`
endpoint.  Monthly and quarterly releases are **forward-filled to a
business-day daily cadence** so each bar holds the most recently released
reading.

```python
from fxmacrodata_bt import load_indicator

inflation = load_indicator("USD", "inflation", "2020-01-01", "2024-12-31")
cerebro.adddata(inflation, name="USD_inflation")
```

Access in strategy:

```python
inf_val  = self.datas[1].close[0]   # latest CPI reading (YoY %)
inf_prev = self.datas[1].close[-22] # reading from ~1 month ago
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

### `CommodityData`

Daily precious-metal spot prices from the `/v1/commodities/{indicator}`
endpoint.  Requires a Professional API key.

```python
from fxmacrodata_bt import load_commodity

gold = load_commodity("gold", "2025-01-01", "2025-12-31", api_key="YOUR_KEY")
cerebro.adddata(gold, name="gold")
```

Supported: `gold`, `silver`, `platinum`.

---

## Example strategy

`example.py` implements an **Inflation Signal** strategy:

1. Load **EUR/USD** daily spot as the price feed (free).
2. Load **US CPI inflation** as a macro signal (free).
3. Compute **3-month momentum** on the forward-filled daily inflation series.
4. **Short EUR/USD** when 3-month inflation delta is positive (rising inflation → Fed
   likely hawkish → USD strengthening).
5. **Long EUR/USD** when 3-month inflation delta is negative (falling inflation → Fed
   likely dovish → USD weakening).

```bash
# Default run (2024-06-01 → today, $100k capital)
python example.py

# Custom date range
python example.py --start 2024-01-01 --end 2025-12-31

# No chart window (useful in headless environments)
python example.py --no-plot

# With a Professional API key (unlocks all 18 currencies)
python example.py --api-key YOUR_KEY
```

---

## Build your own strategy

```python
import backtrader as bt
from fxmacrodata_bt import load_forex, load_indicator, load_commodity

class MyMacroStrategy(bt.Strategy):
    def __init__(self):
        self.fx     = self.datas[0]  # EUR/USD price
        self.signal = self.datas[1]  # USD inflation

    def next(self):
        import math
        if len(self.signal) <= 22:
            return  # wait for lookback window to fill

        val      = self.signal.close[0]
        val_prev = self.signal.close[-22]  # ~1 month ago
        if math.isnan(val) or math.isnan(val_prev):
            return

        delta = val - val_prev

        # Rising inflation → short EUR/USD; falling inflation → long EUR/USD
        if delta > 0.1 and not self.position:
            self.sell(size=10_000)
        elif delta < -0.1 and not self.position:
            self.buy(size=10_000)
        elif self.position.size < 0 and delta < -0.1:
            self.close()
        elif self.position.size > 0 and delta > 0.1:
            self.close()


cerebro = bt.Cerebro()

start, end = "2024-06-01", "2026-04-11"
cerebro.adddata(load_forex("EUR", "USD", start, end), name="EURUSD")
cerebro.adddata(load_indicator("USD", "inflation", start, end), name="USD_inflation")

cerebro.addstrategy(MyMacroStrategy)
cerebro.broker.setcash(100_000)

results = cerebro.run()
cerebro.plot(style="line", iplot=False)
```

---

## Combining multiple feeds

```python
cerebro = bt.Cerebro()

# Price data
cerebro.adddata(load_forex("EUR", "USD", start, end), name="EURUSD")

# Multiple macro signals (requires Pro key for non-USD currencies)
cerebro.adddata(load_indicator("USD", "policy_rate", start, end), name="fed_rate")
cerebro.adddata(load_indicator("USD", "inflation",   start, end), name="us_cpi")

# Commodity overlay
cerebro.adddata(load_commodity("gold", start, end), name="gold")
```

Access in strategy:

```python
def __init__(self):
    self.eurusd    = self.getdatabyname("EURUSD")
    self.fed_rate  = self.getdatabyname("fed_rate")
    self.us_cpi    = self.getdatabyname("us_cpi")
    self.gold      = self.getdatabyname("gold")
```

---

## Notes

- **Close-only feeds**: The FXMacroData REST API provides daily mid-market close
  prices, not OHLCV candles.  `open`, `high`, and `low` are set to `-1`
  (Backtrader will mirror the `close`).  Strategies or indicators that require
  distinct OHLCV bars (e.g. candlestick patterns) are not applicable here.

- **Forward-filling**: Macro indicators are released monthly or quarterly.
  `load_indicator()` reindexes to business-day frequency and forward-fills each
  bar with the latest released value.  Bars before the first available
  observation will have `NaN` — guard against these with `math.isnan(val)`.

- **Plotting**: If the Backtrader chart window fails to open (common in
  headless or newer matplotlib environments), run with `--no-plot` or pin
  `matplotlib==3.8.*` in your environment.

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Documentation](https://fxmacrodata.com/documentation)
- [Get an API key](https://fxmacrodata.com/api-management)
- [Backtrader docs](https://www.backtrader.com/docu/)
