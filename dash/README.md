# FXMacroData – Policy Divergence Studio (Plotly Dash)

A **Plotly Dash** example app focused on two-country macro comparison.
It tracks policy and macro divergence (spread, trend, volatility) and
generates an analyst-style narrative, powered by the
**[FXMacroData API](https://fxmacrodata.com)**.

> **USD announcement data is public — no API key required.**  
> Enter a [Professional API key](https://fxmacrodata.com/api-management) to
> unlock protected non-USD announcement coverage.

---

## What this app does

| Capability | Policy Divergence Studio |
|---|---|
| Core workflow | Compare Country A vs Country B on one macro indicator |
| Main outputs | Spread level, spread trend, spread volatility |
| Visuals | Dual-country line chart + spread area chart |
| Decision support | Cross-indicator scoreboard + narrative summary |

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| Divergence Lab | Two-country series + spread analytics | USD only without key |
| Scoreboard | Indicator-by-indicator strength snapshot | USD only without key |
| Narrative | Auto-generated regime summary | No |

---

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open <http://localhost:8050> in your browser.

---

## Deploy to Render (free tier)

1. Fork or copy this directory into a **public** GitHub repository.
2. Sign up at <https://render.com> and create a **New Web Service**.
3. Connect the GitHub repo.
4. Set the **Start Command** to:
   ```
   gunicorn app:server
   ```
5. Add your API key as an environment variable in Render:
   - Key: `FXMACRODATA_API_KEY`
   - Value: your `rnd_...` key from FXMacroData API management
   - Then read it in `app.py` with `os.getenv("FXMACRODATA_API_KEY", "")`.
6. Click **Deploy** — a `*.onrender.com` URL is generated automatically.

---

## Deploy to Hugging Face Spaces (free)

1. Create a new Space at <https://huggingface.co/spaces> (choose the
   **Docker** or **Gradio** SDK — or use the generic Docker path for Dash).
2. Upload `app.py` and `requirements.txt` plus a minimal `Dockerfile`:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY app.py .
   EXPOSE 7860
   CMD ["gunicorn", "--bind", "0.0.0.0:7860", "app:server"]
   ```
3. Add your API key in **Settings → Secrets** as `FXMACRODATA_API_KEY`.
4. The Space builds automatically — share the generated URL.

---

## Submit to the Dash community gallery

Once deployed, submit the app to the open-source Dash example index:

- **Open-source gallery PR**: <https://github.com/AnnMarieW/dash-app-gallery>
- **Show & Tell forum post**: <https://community.plotly.com/c/dash/show-and-tell/7>

---

## API endpoints used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/announcements/usd/{indicator}` | Free | USD macro indicator history |
| `GET /v1/announcements/{currency}/{indicator}` | API key | Non-USD indicator history |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 🔑 [Get an API key](https://fxmacrodata.com/api-management)
