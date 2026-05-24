# FXMacroData – FX Macro Intelligence Dashboard (HoloViz Panel)

A **HoloViz Panel** example app that visualises macroeconomic indicators and
precious metals prices across 18 currencies, powered by the
**[FXMacroData API](https://fxmacrodata.com)**.

> **USD announcement data is public.**  
> Enter a [Professional API key](https://fxmacrodata.com/api-management) to
> unlock non-USD announcements and the precious-metals endpoint.

---

## Features

- 💎 **Precious Metals** tab — daily gold, silver, and platinum spot prices with
   latest-price metrics, sourced from the `/v1/commodities/{indicator}` endpoint.
- 📊 **Macro Indicators** tab — explore any of 8 macro indicators for any
   supported currency (USD public; non-USD with a Pro key).
- 🌍 **Multi-Currency Compare** tab — overlay multiple currencies on a single
  chart and compare latest readings in a summary table.
- ℹ️ **About** tab — API endpoint reference and feature comparison table.
- 5-minute server-side response cache to avoid redundant API calls on re-render.
- Sidebar API key input + history-range slider that reactively refresh all charts.

---

## Run locally

```bash
pip install -r requirements.txt
panel serve app.py --autoreload
# then open http://localhost:5006/app
```

---

## Deploy to Hugging Face Spaces (free)

1. Create a free account at <https://huggingface.co>.
2. Click **New Space**, enter a name, choose **Docker** as the SDK.
3. Create a `Dockerfile` in the Space:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY app.py .
   EXPOSE 7860
   CMD ["panel", "serve", "app.py", "--port", "7860", \
        "--address", "0.0.0.0", "--allow-websocket-origin=*"]
   ```
4. Add `app.py` and `requirements.txt` to the Space repo.
5. The app builds automatically. Add your `FXMACRODATA_API_KEY` under
   **Settings → Variables and secrets**.

---

## Deploy to Render (free tier)

1. Push this directory to a public GitHub repository.
2. Sign up at <https://render.com> and click **New → Web Service**.
3. Connect the repository and set the **Root Directory** to `examples/panel`
   (if deploying from this monorepo).
4. Set the **Start Command** to:
   ```
   panel serve app.py --port $PORT --address 0.0.0.0 --allow-websocket-origin=*
   ```
   The `Procfile` included here handles this automatically.
5. Add `FXMACRODATA_API_KEY` under **Environment** if you want to pre-populate
   the key (optional — users can also enter it in the sidebar).

---

## Deploy to Heroku

```bash
heroku create my-fxmacrodata-panel
git push heroku main
```

The included `Procfile` is used automatically.

---

## API endpoints used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/announcements/usd/{indicator}` | Free | USD macro indicator history |
| `GET /v1/announcements/{currency}/{indicator}` | API key | Non-USD indicator history |
| `GET /v1/commodities/{indicator}` | API key | Precious metals spot prices |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 🔑 [Get an API key](https://fxmacrodata.com/api-management)
- 🖥️ [HoloViz Panel](https://panel.holoviz.org)
