# FXMacroData × Freqtrade

Use [FXMacroData](https://fxmacrodata.com) as a macro signal source inside
[Freqtrade](https://www.freqtrade.io) strategies.  This integration provides
data-loader helpers for every public FXMacroData endpoint plus a ready-to-run
example strategy.

> **The public example paths use USD announcements and can run without an API key.**
> Add a [Professional key](https://api.fxmacrodata.com-management) to unlock
> protected non-USD announcements, COT positioning, and commodities data.

---

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy the files into your Freqtrade user_data/strategies/ folder
cp fxmacrodata_ft.py MacroSignalStrategy.py \
   ~/.freqtrade/user_data/strategies/

# Backtest (requires BTC/USDT 1d OHLCV data already downloaded)
freqtrade download-data --exchange binance --pairs BTC/USDT --timeframe 1d \
    --timerange 20200101-20251231

freqtrade backtesting \
    --strategy MacroSignalStrategy \
    --timeframe 1d \
    --timerange 20200101-20251231 \
    --pair BTC/USDT

# Dry-run (paper trading)
freqtrade trade --strategy MacroSignalStrategy --dry-run
```

---

## Files

| File | Purpose |
|---|---|
| `fxmacrodata_ft.py` | Core library — data loaders & merge helper |
| `MacroSignalStrategy.py` | Runnable Freqtrade strategy (macro BTC signal) |
| `requirements.txt` | Python dependencies |

---

## The data loaders

All three loaders return plain **pandas DataFrames** and work independently
of Freqtrade — useful in research notebooks or any other framework.

### `fetch_indicator`

Macroeconomic time series from the `/v1/announcements/{currency}/{indicator}`
endpoint.  Monthly and quarterly releases are **forward-filled to a
business-day daily cadence** so each row holds the most recently released
reading.

```python
from fxmacrodata_ft import fetch_indicator

inflation = fetch_indicator("USD", "inflation", "2020-01-01", "2025-12-31")
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

### `fetch_forex`

Daily mid-market FX spot rates from the `/v1/forex/{base}/{quote}` endpoint.

```python
from fxmacrodata_ft import fetch_forex

eurusd = fetch_forex("EUR", "USD", "2022-01-01", "2025-12-31")
# DatetimeIndex, column: "close"
```

---

### `fetch_commodity`

Daily precious-metal spot prices from the `/v1/commodities/{indicator}`
endpoint.

```python
from fxmacrodata_ft import fetch_commodity

gold = fetch_commodity("gold", "2022-01-01", "2025-12-31")
# DatetimeIndex, column: "close" (USD per troy ounce)
```

Supported: `gold`, `silver`, `platinum`.

---

## The `merge_macro` helper

`merge_macro` aligns a macro series onto any Freqtrade OHLCV DataFrame using
`pd.merge_asof`.  It works for any timeframe (1d, 4h, 1h, …) and guarantees
no future data leakage — each bar receives the *last published* macro value
as of that bar's timestamp.

```python
from fxmacrodata_ft import fetch_indicator, merge_macro

inflation = fetch_indicator("USD", "inflation", "2020-01-01", "2025-12-31")

# Inside populate_indicators:
dataframe = merge_macro(dataframe, inflation, "macro_inflation")
# → adds column "macro_inflation" holding CPI YoY % for each OHLCV bar
```

For forex and commodity DataFrames (column `"close"` instead of `"val"`):

```python
gold = fetch_commodity("gold", "2020-01-01", "2025-12-31")
dataframe = merge_macro(dataframe, gold, "gold_price", value_col="close")
```

---

## Example strategy

`MacroSignalStrategy.py` is a daily BTC/USDT strategy driven by the
**USD real policy rate** — the Fed Funds Rate minus CPI inflation.

### Signal logic

```
real_rate = policy_rate (%) − inflation (%)
```

| Condition | Interpretation | Action |
|---|---|---|
| `real_rate < −0.5 pp` | Loose monetary policy → risk-on | **Long BTC/USDT** |
| `real_rate > +0.5 pp` | Tight monetary policy → risk-off | **Exit long** |

USD announcement series are free for the most recent 90 days. FX spot rates and
commodities require an API key.

### How it works

1. On startup, `MacroSignalStrategy.__init__` calls `fetch_indicator` for
   `USD/policy_rate` and `USD/inflation`, caching both DataFrames in memory.
2. In `populate_indicators`, `merge_macro` aligns each series onto the daily
   OHLCV bars using a backward `merge_asof` — the bar gets the last known
   macro value, not a future one.
3. `macro_real_rate` is computed as `policy_rate − inflation`.
4. Entry and exit signals are generated in `populate_entry_trend` /
   `populate_exit_trend`.

---

## Build your own strategy

```python
from freqtrade.strategy import IStrategy
from fxmacrodata_ft import fetch_indicator, fetch_commodity, merge_macro

class MyMacroStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    minimal_roi = {"0": 100}
    stoploss = -0.10
    startup_candle_count = 30

    def __init__(self, config):
        super().__init__(config)
        # Pre-load macro data once
        self._inflation = fetch_indicator("USD", "inflation",
                                          "2018-01-01", "2025-12-31")
        self._gold = fetch_commodity("gold", "2018-01-01", "2025-12-31")

    def populate_indicators(self, dataframe, metadata):
        dataframe = merge_macro(dataframe, self._inflation, "cpi")
        dataframe = merge_macro(dataframe, self._gold, "gold",
                                value_col="close")
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # Enter when CPI is falling and gold is rising
        dataframe.loc[
            (dataframe["cpi"] < 3.0) &
            (dataframe["gold"] > dataframe["gold"].shift(22)) &
            (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        dataframe.loc[
            dataframe["cpi"] > 5.0,
            "exit_long",
        ] = 1
        return dataframe
```

---

## Using multiple macro signals

```python
def __init__(self, config):
    super().__init__(config)
    start, end = "2018-01-01", "2025-12-31"
    self._rate    = fetch_indicator("USD", "policy_rate",     start, end)
    self._infl    = fetch_indicator("USD", "inflation",       start, end)
    self._nfp     = fetch_indicator("USD", "non_farm_payrolls", start, end)
    self._gold    = fetch_commodity("gold",  start, end)

def populate_indicators(self, dataframe, metadata):
    dataframe = merge_macro(dataframe, self._rate,  "macro_rate")
    dataframe = merge_macro(dataframe, self._infl,  "macro_infl")
    dataframe = merge_macro(dataframe, self._nfp,   "macro_nfp")
    dataframe = merge_macro(dataframe, self._gold,  "macro_gold",
                            value_col="close")
    dataframe["macro_real_rate"] = dataframe["macro_rate"] - dataframe["macro_infl"]
    return dataframe
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

[Get your API key →](https://api.fxmacrodata.com-management)

Set the key as an environment variable (picked up automatically):

```bash
export FXMACRODATA_API_KEY=your_key_here
```

Or configure it in `config.json` and read it in `__init__`:

```json
{
  "fxmacrodata_api_key": "your_key_here"
}
```

```python
self._api_key = config.get("fxmacrodata_api_key")
```

---

## Notes

- **Daily timeframe recommended**: FXMacroData macro releases are monthly or
  quarterly. Using a shorter timeframe is fine — `merge_macro` handles
  intraday alignment correctly — but the signal changes at most once per
  month, so sub-daily timeframes add no new information from these series.

- **Startup candle count**: Set `startup_candle_count` to at least 30 to
  ensure the OHLCV history covers the `startup_candle_count` warm-up period
  before the first trade.

- **Forward-filling**: `fetch_indicator` reindexes macro releases to
  business-day frequency and forward-fills.  Bars before the first available
  observation will have `NaN` — check with `dataframe["col"].notna()`.

- **Live trading refresh**: The macro series are fetched once on startup.
  Call `strategy.reload_macro()` or restart the bot to pull a fresh release.

- **Backtesting**: Freqtrade calls `populate_indicators` with the full OHLCV
  history; `merge_macro` uses a backward `merge_asof` so each bar only sees
  data that was available at that point in time.

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Documentation](https://fxmacrodata.com/documentation)
- [Get an API key](https://api.fxmacrodata.com-management)
- [Freqtrade documentation](https://www.freqtrade.io/en/stable/)
- [Freqtrade strategy customisation](https://www.freqtrade.io/en/stable/strategy-customization/)
