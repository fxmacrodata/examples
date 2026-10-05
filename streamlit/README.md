# FXMacroData – Central Bank Rate Monitor (Streamlit)

A Streamlit example app that visualizes macroeconomic indicators from the
**[FXMacroData API](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit)**.

> **USD announcement data is public — no API key required.**  
> Enter an [API key](https://fxmacrodata.com/api-management?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit) in the
> sidebar to unlock protected non-USD announcements.

---

## Features

| Tab | What it shows | API key needed? |
|---|---|---|
| USD Dashboard | Latest readings, recent releases with publication times and source links, upcoming release calendar. With a key: up to 10 years of charts | No |
| Multi-Currency | Compare policy rates, inflation and unemployment across up to 22 currencies | Yes |
| About | Free vs paid coverage and API links | No |

Without a key the API returns the most recent 90 days of USD data, delayed by
15 minutes. A key removes both limits.

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The dark theme lives in `.streamlit/config.toml`. Streamlit reads it from the
directory you launch from; Community Cloud launches from the repository root,
so this repo keeps a copy at `/.streamlit/config.toml` as well.

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
   - The app uses it server-side for every visitor and never shows it in the
     sidebar input. Leave it unset to run the public app keyless.
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

Full API reference: <https://fxmacrodata.com/documentation?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit>

---

## Links

- [FXMacroData](https://fxmacrodata.com/?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit)
- [API Docs](https://fxmacrodata.com/documentation?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit)
- [Get an API key](https://fxmacrodata.com/api-management?utm_source=github&utm_medium=referral&utm_campaign=examples&utm_content=streamlit)
