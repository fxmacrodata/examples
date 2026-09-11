import os
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, render_template_string

app = Flask(__name__)

API_BASE = "https://api.fxmacrodata.com/v1"
SUBSCRIBE_URL = "https://fxmacrodata.com/subscribe"
DOCS_URL = "https://fxmacrodata.com/documentation"

TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>FXMacroData Flask Example</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }
      .wrap { max-width: 980px; margin: 0 auto; padding: 24px; }
      .hero { background: linear-gradient(120deg, #0b3b5b, #0f766e); color: white; padding: 24px; border-radius: 12px; }
      .hero a { color: #a7f3d0; font-weight: 700; }
      .card { margin-top: 18px; background: white; border: 1px solid #dbeafe; border-radius: 12px; padding: 18px; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; }
      th, td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; }
      .muted { color: #475569; font-size: 13px; }
      .cta { display: inline-block; margin-top: 8px; background: #0f766e; color: white; text-decoration: none; padding: 10px 14px; border-radius: 8px; }
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"hero\">
        <h1>USD Macro Snapshot (Flask)</h1>
        <p>Public, no-key example app powered by FXMacroData.</p>
        <a href=\"{{ subscribe_url }}\" target=\"_blank\" rel=\"noopener noreferrer\">Upgrade for full non-USD + COT + commodities access</a>
      </div>
      <div class=\"card\">
        <h2>Latest USD Inflation Releases</h2>
        <p class=\"muted\">Endpoint: /v1/announcements/usd/inflation (public)</p>
        {% if rows %}
        <table>
          <thead><tr><th>Date</th><th>Value</th><th>Announcement</th></tr></thead>
          <tbody>
            {% for r in rows %}
            <tr>
              <td>{{ r.get('date', '—') }}</td>
              <td>{{ r.get('val', '—') }}</td>
              <td>{{ r.get('announcement_datetime', '—') }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
        {% else %}
        <p>No data available.</p>
        {% endif %}
      </div>
      <div class=\"card\">
        <h3>Next steps</h3>
        <ul>
          <li>Fork this app and customize your niche landing page.</li>
          <li>Add protected endpoint support via env var API key.</li>
          <li>Drive paid conversion with a clear CTA to subscribe.</li>
        </ul>
        <a class=\"cta\" href=\"{{ docs_url }}\" target=\"_blank\" rel=\"noopener noreferrer\">Read API docs</a>
      </div>
    </div>
  </body>
</html>
"""


def fetch_usd_inflation():
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=365)
    url = f"{API_BASE}/announcements/usd/inflation"
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    payload = resp.json() if resp.content else {}
    return payload.get("data", [])[-12:]


@app.get("/")
def index():
    rows = []
    try:
        rows = fetch_usd_inflation()
    except Exception:
        rows = []

    return render_template_string(
        TEMPLATE,
        rows=rows,
        subscribe_url=SUBSCRIBE_URL,
        docs_url=DOCS_URL,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
