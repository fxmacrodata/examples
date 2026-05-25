# FXMacroData – Central Bank Rate Monitor (Streamlit)

A Streamlit example app that visualizes macroeconomic indicators from the
**[FXMacroData API](https://fxmacrodata.com)**.

> **USD announcement data is public — no API key required.**  
> Enter a [Professional API key](https://fxmacrodata.com/api-management) in the
> sidebar to unlock protected non-USD announcements.

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| 🇺🇸 USD Dashboard | Policy rate, inflation, GDP, unemployment, snapshot table, release timeline | No |
| 🌍 Multi-Currency | Compare any indicator across up to 18 currencies | Yes (for non-USD) |
| ℹ️ About | Feature overview and API links | No |

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501> in your browser.

---

## Deploy to Streamlit Community Cloud (free)

1. Fork or copy this directory into a **public** GitHub repository.
2. Sign in at <https://share.streamlit.io> with your GitHub account.
3. Click **New app**, select your repo, branch, and set the main file to
   `app.py` (or the path to it within your repo).
4. *(Optional)* Add your API key as a Streamlit secret:
   - In the Cloud dashboard open **Settings → Secrets** and add:
     ```toml
     FXMACRODATA_API_KEY = "your_key_here"
     ```
   - Then read it in `app.py` with
     `st.secrets.get("FXMACRODATA_API_KEY", "")`.
5. Click **Deploy** — a live URL is generated automatically.

---

## Deploy to Hugging Face Spaces (free)

1. Create a new Space at <https://huggingface.co/spaces> (choose the
   **Streamlit** SDK).
2. Upload `app.py` and `requirements.txt` via the web editor or
   `git push` to the Space repo.
3. Add your API key in **Settings → Secrets** as `FXMACRODATA_API_KEY`.
4. The Space builds automatically — share the generated URL.

---

## API endpoints used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/announcements/usd/{indicator}` | Free | USD macro indicator history |
| `GET /v1/announcements/{currency}/{indicator}` | API key | Non-USD indicator history |
| `GET /v1/calendar/usd` | Free | Upcoming USD macro release schedule |

Full API reference: <https://fxmacrodata.com/documentation>

---

## Links

- 🌐 [FXMacroData](https://fxmacrodata.com)
- 📖 [API Docs](https://fxmacrodata.com/documentation)
- 🔑 [Get an API key](https://fxmacrodata.com/api-management)
