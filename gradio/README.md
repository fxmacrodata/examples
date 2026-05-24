# FXMacroData – FX & Macro Explorer (Gradio)

A **Gradio** example app for exploring macroeconomic indicators, FX spot rates,
and economic release calendars, powered by the
**[FXMacroData API](https://fxmacrodata.com)**.

> **USD announcement data is public — no API key required.**  
> Enter a [Professional API key](https://fxmacrodata.com/api-management) to
> unlock protected non-USD announcements.

---

## What makes this different

| | This Gradio app | Streamlit app | Dash app |
|---|---|---|---|
| **Concept** | On-demand FX & macro explorer | Central bank rate monitor | Macro momentum heatmap |
| **Visualisation** | Time-series + FX rates + calendar | Individual time-series line charts | Colour-coded momentum grid |
| **Interaction** | Click-to-query any indicator, pair, or calendar | Linear scrolling dashboard | Click heatmap cell → drill-down |
| **Multi-currency** | Side-by-side overlay chart | Multi-currency comparison chart | Heatmap row per currency |
| **Unique feature** | FX spot rates + release calendar tabs | Latest-value metric cards | Sparkline deep-dive per currency |

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| 📈 Indicator Explorer | Historical time series for any currency × indicator + summary stats | USD only without key |
| 🌍 Multi-Currency | Overlay any indicator across up to 18 currencies | USD only without key |
| 💱 FX Rates | Daily FX spot rate chart for any major/cross pair | No |
| 🗓️ Release Calendar | Upcoming economic data release dates | No |
| ℹ️ About | Feature overview and API links | No |

---

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open <http://localhost:7860> in your browser.

---

## Deploy to Hugging Face Spaces (free)

1. Create a free account at <https://huggingface.co>.
2. Click **New Space**, set the SDK to **Gradio**, and give the Space a name.
3. Upload `app.py` and `requirements.txt` via the web editor, or push via git:
   ```bash
   git clone https://huggingface.co/spaces/<your-username>/<your-space-name>
   cp app.py requirements.txt <your-space-name>/
   cd <your-space-name> && git add . && git commit -m "Add FXMacroData Gradio app" && git push
   ```
4. *(Optional)* Add your API key as a Space secret:
   - Open **Settings → Variables and secrets** and add:
     - Name: `FXMACRODATA_API_KEY`
     - Value: your Professional API key
   - Then read it in `app.py` with `os.getenv("FXMACRODATA_API_KEY", "")` and
     pre-populate the key input.
5. The Space builds automatically — share the generated `*.hf.space` URL.

---

## API endpoints used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/announcements/usd/{indicator}` | Free | USD macro indicator history |
| `GET /v1/announcements/{currency}/{indicator}` | API key | Non-USD indicator history |
| `GET /v1/forex/{base}/{quote}` | Free | FX spot rate history |
| `GET /v1/calendar/{currency}` | Free | Upcoming release dates for supported currencies |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 🔑 [Get an API key](https://fxmacrodata.com/api-management)
