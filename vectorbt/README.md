# FXMacroData – VectorBT Integration

A **Jupyter notebook** that demonstrates how to backtest FX trading strategies
using macroeconomic data from the **[FXMacroData API](https://fxmacrodata.com)**
and the **[VectorBT](https://vectorbt.dev)** backtesting library.

> **USD announcement indicators are public for the most recent 90 days. EUR/USD
> forex data requires an API key.**  
> Enter a [Professional API key](https://api.fxmacrodata.com-management) to
> unlock protected non-USD announcements and the interest-rate carry strategy.

---

## What you'll learn

| Strategy | Description | API key needed? |
|---|---|---|
| **MA Crossover** | Fast/slow moving-average crossover on EUR/USD | No |
| **Parameter Sweep** | Vectorised optimisation of MA windows with VectorBT | No |
| **Carry Trade** | Enter when EUR rate > USD rate; exit when differential flips | Yes (EUR policy rate) |
| **Multi-Pair Basket** | Carry basket across multiple currency pairs | Yes |

---

## Run locally

```bash
pip install -r requirements.txt
jupyter notebook fxmacrodata_vectorbt.ipynb
```

Open the notebook in your browser and run the cells top to bottom.  
Set `API_KEY` in the **Configuration** cell to unlock Pro strategies.

---

## Notebook structure

1. **Setup & imports** — install check, library imports
2. **Configuration** — API key, date range, currency pair
3. **Data helpers** — `fetch_forex()` and `fetch_indicator()` wrappers
4. **Strategy 1 – MA Crossover** — 10/50-day MA on EUR/USD, full stats
5. **Strategy 2 – Parameter Optimisation** — vectorised sweep across window pairs
6. **Strategy 3 – Carry Trade** — policy-rate differential as entry/exit signal
7. **Portfolio comparison** — equity curves for all strategies side by side

---

## API endpoints used

| Endpoint | Auth | Used for |
|---|---|---|
| `GET /v1/forex/{base}/{quote}` | Free | EUR/USD daily close prices |
| `GET /v1/announcements/usd/policy_rate` | Free | USD Federal Funds Rate |
| `GET /v1/announcements/eur/policy_rate` | API key | ECB deposit rate |
| `GET /v1/announcements/{currency}/policy_rate` | API key | Multi-currency carry |

Full API reference: [fxmacrodata.com/documentation](https://fxmacrodata.com/documentation)

---

## VectorBT key concepts used

| VectorBT feature | Purpose |
|---|---|
| `vbt.MA.run(close, window=...)` | Vectorised moving-average indicator |
| `ma.ma_crossed_above(other_ma)` | Boolean entry signals |
| `vbt.Portfolio.from_signals()` | Simulate portfolio from entry/exit masks |
| `portfolio.stats()` | Full performance statistics table |
| `portfolio.plot()` | Interactive equity curve (Plotly) |
| Multi-column `close` | Batch backtest across multiple pairs simultaneously |
| Parameter arrays | Grid search — pass `window=[5,10,20]` to test all at once |

---

## Useful links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 🔑 [Get an API key](https://api.fxmacrodata.com-management)
- 📦 [VectorBT documentation](https://vectorbt.dev)
- 💬 [VectorBT community](https://github.com/polakowo/vectorbt/discussions)
