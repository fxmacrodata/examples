from datetime import date, timedelta

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

API_BASE = "https://api.fxmacrodata.com/v1"
SUBSCRIBE_URL = "https://fxmacrodata.com/subscribe"

app = FastAPI(title="FXMacroData FastAPI Example", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/usd/latest")
def usd_latest() -> dict:
    url = f"{API_BASE}/announcements/usd/latest"
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc


@app.get("/api/usd/inflation")
def usd_inflation(days: int = 365) -> dict:
    end_date = date.today()
    start_date = end_date - timedelta(days=max(30, min(days, 3650)))
    url = f"{API_BASE}/announcements/usd/inflation"
    params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
    try:
        res = requests.get(url, params=params, timeout=20)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc


@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    return f"""
<!doctype html>
<html>
  <head>
    <meta charset='utf-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <title>FXMacroData FastAPI Example</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: #f0f9ff; color: #0f172a; }}
      .wrap {{ max-width: 840px; margin: 30px auto; padding: 0 16px; }}
      .hero {{ background: #0f172a; color: white; padding: 20px; border-radius: 14px; }}
      .card {{ margin-top: 16px; background: white; border-radius: 14px; padding: 20px; border: 1px solid #cbd5e1; }}
      a.btn {{ display:inline-block; margin-top: 10px; background:#0f766e; color:white; text-decoration:none; padding:10px 14px; border-radius:8px; font-weight:600; }}
      code {{ background:#e2e8f0; padding:2px 6px; border-radius:6px; }}
    </style>
  </head>
  <body>
    <div class='wrap'>
      <div class='hero'>
        <h1>FastAPI Starter for FXMacroData</h1>
        <p>Public endpoints only, no key needed to get started.</p>
        <a class='btn' href='{SUBSCRIBE_URL}' target='_blank' rel='noopener noreferrer'>Subscribe for full endpoint access</a>
      </div>
      <div class='card'>
        <h3>Example routes</h3>
        <p><code>/api/usd/latest</code> - Latest USD indicator values</p>
        <p><code>/api/usd/inflation?days=365</code> - USD inflation history</p>
      </div>
    </div>
  </body>
</html>
"""
