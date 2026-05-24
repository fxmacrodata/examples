# FXMacroData – FX Macro Heatmap (Plotly Dash)

A **Plotly Dash** example app that visualises macroeconomic indicator momentum
across 18 currencies as a colour-coded heatmap, powered by the
**[FXMacroData API](https://fxmacrodata.com)**.

> **USD announcement data is public — no API key required.**  
> Enter a [Professional API key](https://fxmacrodata.com/api-management) to
> unlock protected non-USD announcement coverage.

---

## What makes this different

| | This Dash app | Streamlit app |
|---|---|---|
| **Concept** | Macro momentum heatmap | Central bank rate monitor |
| **Visualisation** | Colour-coded grid (all currencies × indicators at a glance) | Individual time-series line charts |
| **Interaction** | Click any cell → time-series drills down inline | Linear scrolling dashboard |
| **Deep Dive tab** | Sparkline grid for every indicator of a chosen currency | Multi-currency comparison chart |

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| 🌡️ Macro Heatmap | Colour-coded momentum for every indicator × currency | USD only without key |
| 📊 Deep Dive | Sparkline grid for all indicators of a chosen currency | USD only without key |
| ℹ️ About | Feature overview and API links | No |

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
5. *(Optional)* Add your API key as an environment variable:
   - Key: `FXMACRODATA_API_KEY`
   - Value: your key
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
