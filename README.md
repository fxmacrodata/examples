# FXMacroData Examples Hub

This directory is the source bundle for the public examples repository:
https://github.com/fxmacrodata/examples

Use these projects to publish demos across app stores, template directories,
and hosting platforms so developers discover FXMacroData quickly and then move
to a paid plan at:

- https://fxmacrodata.com/subscribe

> Public endpoints (USD announcements, calendar, market sessions,
> data catalogue) can be used without an API key.
> Protected endpoints (non-USD announcements, FX spot history, COT,
> commodities) require a paid key from the subscribe flow.

---

## Deployable app matrix

| App | Framework | Hosted on | Live URL |
|---|---|---|---|
| Central Bank Rate Monitor | Streamlit | Streamlit Community Cloud | _deploy link_ |
| FX Trade Setup Studio | Web (Vanilla JS) | GitHub Pages / Netlify / Vercel Static | _deploy link_ |
| FX & Macro Explorer | Gradio | Hugging Face Spaces | _deploy link_ |
| FX Macro Heatmap | Plotly Dash | Render | _deploy link_ |
| Conversational FX Macro Monitor | Plotly Dash + Dash MCP | Render | _deploy link_ |
| Macro Intelligence Dashboard | HoloViz Panel | Hugging Face Spaces | _deploy link_ |
| FX Market Intelligence | Next.js | Vercel | _deploy link_ |
| USD Macro Snapshot API | FastAPI | Railway/Render/Fly.io | _deploy link_ |
| USD Macro Landing App | Flask | Render/Railway | _deploy link_ |
| Edge Macro Widget Proxy | Cloudflare Worker | Cloudflare | _deploy link_ |
| Netlify Macro Widget | Netlify Functions + static | Netlify | _deploy link_ |
| Policy Rate Divergence | Backtrader | Local script | — |
| Policy Rate Divergence | Zipline | Local script | — |
| Macro Signal (BTC/USDT) | Freqtrade | Local strategy | — |
| FX Strategy Backtesting | VectorBT (Jupyter) | Run locally / JupyterHub | — |
| Macro Data Access | pandas-datareader | Local script | — |
| Macro Carry Scanner | CCXT | Local script | — |
| Carry Rebalance Bot | Blankly | Local strategy | — |

## Distribution-first publishing loop

1. Launch each app in the public examples repo.
2. Add a visible CTA to https://fxmacrodata.com/subscribe in app header/footer.
3. Submit links to framework galleries and community indexes.
4. Add badges/screenshots to this README once each app is live.

Suggested distribution targets:

- Vercel templates
- Streamlit gallery
- Hugging Face Spaces
- Netlify templates/examples
- Cloudflare Worker examples
- Plotly Dash Show and Tell
- Reddit (`r/algotrading`, `r/quant`, `r/forex`) and X build threads

---

## Key safety policy (required)

Never commit or print real API keys. Use only these patterns:

- Environment variables (`FXMACRODATA_API_KEY`)
- Host-level encrypted secrets (Vercel/Netlify/Render/Cloudflare)
- `.env.example` templates only (never real `.env` files)
- Optional user-entered key fields that stay in memory only

Before publishing, run a scan:

```bash
grep -RInE "(sk-|AIza|FXMACRODATA_API_KEY\s*=\s*['\"][^'\"]+)" . || true
```

---

## QuantConnect / LEAN Integration

Use FXMacroData as a custom data source inside [QuantConnect](https://www.quantconnect.com)
backtests and live-trading algorithms.

```bash
cd quantconnect   # copy fxmacrodata/ into your LEAN project
```

See [`quantconnect/README.md`](quantconnect/README.md) for setup instructions and two
example algorithms:

- **Macro Monitor** — plot USD indicators in QuantConnect charts (free, no key)
- **Policy Rate Divergence** — FX carry strategy driven by central-bank rate differentials

---

## Freqtrade Integration

Use FXMacroData as a macro signal source inside
[Freqtrade](https://www.freqtrade.io) strategies.

```bash
cd freqtrade
cp fxmacrodata_ft.py MacroSignalStrategy.py \
   ~/.freqtrade/user_data/strategies/
freqtrade backtesting --strategy MacroSignalStrategy --timeframe 1d \
    --timerange 20200101-20251231 --pair BTC/USDT
```

See [`freqtrade/README.md`](freqtrade/README.md) for setup and the included
Macro Signal strategy (BTC/USDT driven by the USD real policy rate).

---

## Zipline Integration

Use FXMacroData as a custom bundle and macro data source inside
[zipline-reloaded](https://zipline.ml4trading.io) backtests.

```bash
cd zipline   && pip install -r requirements.txt && python example.py
```

See [`zipline/README.md`](zipline/README.md) for setup and the included
Policy Rate Divergence strategy (EUR/USD carry driven by central-bank rate
differentials).

---

## CCXT Integration

Use FXMacroData through the [CCXT](https://github.com/ccxt/ccxt) unified
interface.  The adapter implements the standard CCXT exchange API so you can
plug FXMacroData into any existing CCXT-based trading or analysis workflow.

```bash
cd ccxt      && pip install -r requirements.txt && python example.py
```

See [`ccxt/README.md`](ccxt/README.md) for setup and usage.  Supported CCXT
methods:

- `load_markets()` — 30 FX pairs + XAU/USD, XAG/USD, XPT/USD
- `fetch_ohlcv(symbol, '1d', since, limit)` — daily mid-market candles
- `fetch_ticker(symbol)` / `fetch_tickers(symbols)` — latest rates
- `fetch_macro_indicator(currency, indicator)` — macro extension

---

## Quick start (run any app locally)

```bash
# Python apps (pick one)
cd streamlit   && pip install -r requirements.txt && streamlit run app.py
cd gradio      && pip install -r requirements.txt && python app.py
cd dash        && pip install -r requirements.txt && python app.py
cd dash-mcp    && pip install -r requirements.txt && python app.py
cd panel       && pip install -r requirements.txt && panel serve app.py --autoreload
cd flask       && pip install -r requirements.txt && python app.py
cd fastapi     && pip install -r requirements.txt && uvicorn app:app --reload --port 8010
cd backtrader  && pip install -r requirements.txt && python example.py
cd zipline     && pip install -r requirements.txt && python example.py
cd freqtrade   # copy fxmacrodata_ft.py + MacroSignalStrategy.py into user_data/strategies/

# pandas-datareader
cd pandas-datareader && pip install -r requirements.txt && python example.py

# VectorBT Jupyter notebook
cd vectorbt && pip install -r requirements.txt && jupyter notebook fxmacrodata_vectorbt.ipynb

# CCXT macro scanner
cd ccxt      && pip install -r requirements.txt && python example.py

# Next.js app
cd vercel && npm install && npm run dev

# Netlify app
cd netlify-widget && npm install && npm run dev

# FX Trade Setup Studio (static app)
cd pollinations/fx-trade-setup-studio && python -m http.server 8080

# Cloudflare Worker
cd cloudflare-worker && npm install && npm run dev

# QuantConnect / LEAN — copy the fxmacrodata/ package into your LEAN project
# then follow quantconnect/README.md
```

---

## Deploy yourself

### Streamlit → Streamlit Community Cloud

1. Fork this repo (or push `streamlit/` to your own public repo).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. **New app** → select repo → set main file to `streamlit/app.py`.
4. Click **Deploy**.

### Gradio → Hugging Face Spaces

1. Create a Space at [huggingface.co/spaces](https://huggingface.co/spaces) → SDK: **Gradio**.
2. Upload `gradio/app.py` and `gradio/requirements.txt`.
3. Space builds automatically.

### Dash → Render

1. Fork this repo.
2. Go to [render.com](https://render.com) → **New Web Service** → connect repo.
3. Set root directory to `dash/`, start command: `gunicorn app:server`.
4. Or use the included `render.yaml` blueprint: **New → Blueprint** → connect repo.

### Dash MCP → Render

1. Fork this repo.
2. Go to [render.com](https://render.com) → **New Web Service** → connect repo.
3. Set root directory to `dash-mcp/`, start command: `gunicorn app:server`.
4. Add `FXMACRODATA_API_KEY` as an environment variable for protected FX spot history.
5. Connect MCP clients to `https://<your-service>.onrender.com/_mcp`.

### Panel → Hugging Face Spaces (Docker)

1. Create a Space at [huggingface.co/spaces](https://huggingface.co/spaces) → SDK: **Docker**.
2. Upload `panel/app.py`, `panel/requirements.txt`, and `panel/Dockerfile`.
3. Space builds automatically.

### VectorBT → run locally or on JupyterHub

```bash
cd vectorbt
pip install -r requirements.txt
jupyter notebook fxmacrodata_vectorbt.ipynb
```

Or launch on any hosted Jupyter environment (Google Colab, JupyterHub, Binder)
by uploading `fxmacrodata_vectorbt.ipynb` and `requirements.txt`.

### Vercel → Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Ffxmacrodata%2Fexamples%2Ftree%2Fmain%2Fvercel)

Or manually: [vercel.com](https://vercel.com) → **Add New → Project** → import repo → root directory: `vercel/`.

### Flask / FastAPI → Render or Railway

1. Push `flask/` or `fastapi/` to your public examples repo.
2. Create a new service on Render/Railway.
3. Set start command:
    - Flask: `gunicorn app:app`
    - FastAPI: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Add `FXMACRODATA_API_KEY` as an environment variable only if you need protected endpoints.

### Netlify Functions

1. Import the repo into Netlify.
2. Set base directory to `netlify-widget/`.
3. Add optional environment variable: `FXMACRODATA_API_KEY`.
4. Deploy and share your `.netlify.app` URL.

### Cloudflare Worker

1. Deploy `cloudflare-worker/` via `wrangler deploy`.
2. Add optional secret with `wrangler secret put FXMACRODATA_API_KEY`.
3. Use the Worker URL from any frontend widget.

---

## API key (optional)

All apps accept an API key at runtime via a sidebar input. To pre-configure:

| Platform | Method |
|---|---|
| Streamlit Cloud | Settings → Secrets → `FXMACRODATA_API_KEY = "key"` |
| HF Spaces | Settings → Secrets → `FXMACRODATA_API_KEY` |
| Render | Environment → `FXMACRODATA_API_KEY` |
| Vercel | Settings → Environment Variables → `FXMACRODATA_API_KEY` |

---

## pandas-datareader Integration

Use FXMacroData as a drop-in data source inside any workflow that already uses
[pandas-datareader](https://pandas-datareader.readthedocs.io/).

```bash
cd pandas-datareader && pip install -r requirements.txt && python example.py
```

See [`pandas-datareader/README.md`](pandas-datareader/README.md) for the full
guide and two usage patterns:

- **Standalone readers** — `FXMacroDataIndicatorReader`, `FXMacroDataForexReader`,
  `FXMacroDataCommoditiesReader`, `FXMacroDataCOTReader`
- **DataReader interface** — register once and use `pdr.DataReader("USD/inflation", "fxmacrodata", ...)`

---

## API endpoints used

| Endpoint | Auth | Used by |
|---|---|---|
| `GET /v1/announcements/usd/{indicator}` | Free | Streamlit, Dash, Gradio, Panel |
| `GET /v1/announcements/{currency}/{indicator}` | API key | All |
| `GET /v1/forex/{base}/{quote}` | API key | Gradio, Backtrader, VectorBT, Dash MCP |
| `GET /v1/calendar/{currency}` | Free | Gradio, Vercel |
| `GET /v1/commodities/{indicator}` | API key | Panel, Vercel, Backtrader |
| `GET /v1/cot/{currency}` | API key | Vercel |

Full reference: [fxmacrodata.com/documentation](https://fxmacrodata.com/documentation)

---

## Links

- [FXMacroData](https://fxmacrodata.com)
- [API Docs](https://fxmacrodata.com/documentation)
- [Subscribe](https://fxmacrodata.com/subscribe)
- [API management](https://api.fxmacrodata.com-management)
- [Public examples repository](https://github.com/fxmacrodata/examples)
- [Security and key policy](./SECURITY_AND_KEYS.md)
- [Public repo publishing playbook](./PUBLIC_REPO_PUBLISHING_PLAYBOOK.md)
