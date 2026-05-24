"""
FXMacroData – FX Macro Intelligence Dashboard
==============================================
A HoloViz Panel example app that visualises macroeconomic indicators and
precious metals prices across major currencies, powered by the FXMacroData
REST API.

Free tier  : USD macro indicators + precious metals — no API key required.
Pro tier   : Full 18-currency grid — requires a Professional API key.
             Get yours at https://fxmacrodata.com/api-management

Run locally
-----------
    pip install -r requirements.txt
    panel serve app.py --autoreload
    # then open http://localhost:5006/app

Deploy to Hugging Face Spaces
------------------------------
    # See README.md for full deploy steps.
    panel serve app.py --port 7860 --address 0.0.0.0 --allow-websocket-origin=*

Deploy to Render (free tier)
-----------------------------
    # Start command (from Procfile):
    panel serve app.py --port $PORT --address 0.0.0.0 --allow-websocket-origin=*
"""

import datetime
import time
from typing import Optional

import pandas as pd
import panel as pn
import plotly.graph_objects as go
import requests

# ─── Panel initialisation ─────────────────────────────────────────────────────

pn.extension("plotly", sizing_mode="stretch_width")

# ─── Constants ────────────────────────────────────────────────────────────────

API_BASE = "https://fxmacrodata.com/api/v1"
SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

FREE_CURRENCY = "USD"

PRO_CURRENCIES = [
    "EUR",
    "GBP",
    "AUD",
    "JPY",
    "CAD",
    "CHF",
    "NZD",
    "CNY",
    "HKD",
    "SGD",
    "KRW",
    "NOK",
    "SEK",
    "DKK",
    "PLN",
    "BRL",
    "MXN",
]

ALL_CURRENCIES = [FREE_CURRENCY] + PRO_CURRENCIES

# (display label, unit suffix)
INDICATORS: dict[str, tuple[str, str]] = {
    "policy_rate": ("Policy Rate", "%"),
    "inflation": ("Inflation", "% YoY"),
    "gdp": ("GDP Growth", "% YoY"),
    "unemployment": ("Unemployment", "%"),
    "non_farm_payrolls": ("Non-Farm Payrolls", "k"),
    "retail_sales": ("Retail Sales", "% MoM"),
    "pmi": ("PMI", ""),
    "trade_balance": ("Trade Balance", ""),
}

COMMODITIES = ["gold", "silver", "platinum"]

COMMODITY_DISPLAY_METADATA: dict[str, tuple[str, str, str]] = {
    "gold": ("Gold (XAU/USD)", "USD / troy oz", "#D4AF37"),
    "silver": ("Silver (XAG/USD)", "USD / troy oz", "#94A3B8"),
    "platinum": ("Platinum (XPT/USD)", "USD / troy oz", "#7EC8E3"),
}

CURRENCY_FLAGS: dict[str, str] = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "AUD": "🇦🇺",
    "JPY": "🇯🇵",
    "CAD": "🇨🇦",
    "CHF": "🇨🇭",
    "NZD": "🇳🇿",
    "CNY": "🇨🇳",
    "HKD": "🇭🇰",
    "SGD": "🇸🇬",
    "KRW": "🇰🇷",
    "NOK": "🇳🇴",
    "SEK": "🇸🇪",
    "DKK": "🇩🇰",
    "PLN": "🇵🇱",
    "BRL": "🇧🇷",
    "MXN": "🇲🇽",
}

CHART_COLORS = [
    "#1E88E5",
    "#E53935",
    "#43A047",
    "#FB8C00",
    "#7B1FA2",
    "#00897B",
    "#546E7A",
    "#F4511E",
    "#00ACC1",
    "#8E24AA",
    "#3949AB",
    "#039BE5",
]

_API_RESPONSE_CACHE: dict = {}
_CACHE_TTL = 300  # 5-minute server-side in-memory cache


# ─── Request cache ────────────────────────────────────────────────────────────


def _cache_get(key: str):
    entry = _API_RESPONSE_CACHE.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_put(key: str, value) -> None:
    _API_RESPONSE_CACHE[key] = (time.monotonic(), value)


# ─── API helpers ──────────────────────────────────────────────────────────────


def fetch_indicator(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch indicator time-series from the FXMacroData API.

    Returns ``(dataframe, None)`` on success or ``(None, error_message)``
    on failure.
    """
    cache_key = f"ind|{currency}|{indicator}|{api_key or ''}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(
            f"{API_BASE}/announcements/{currency.lower()}/{indicator}",
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code == 401:
        result = (
            None,
            (
                f"🔑 **API key required** for {currency} data.  "
                f"[Get your free Professional key]({API_KEYS_URL})."
            ),
        )
    elif resp.status_code == 403:
        result = (None, "❌ **Invalid API key.** Please check your key and try again.")
    elif resp.status_code == 404:
        result = (None, f"No data found for **{currency} / {indicator}**.")
    elif not resp.ok:
        result = (None, f"API error {resp.status_code}: {resp.text[:120]}")
    else:
        rows = resp.json().get("data", [])
        if not rows:
            result = (None, f"No data returned for **{currency} / {indicator}**.")
        else:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            result = (df.sort_values("date").reset_index(drop=True), None)

    _cache_put(cache_key, result)
    return result


def fetch_commodity(
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch commodity (precious metals) time-series from the FXMacroData API."""
    cache_key = f"comm|{indicator}|{api_key or ''}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(
            f"{API_BASE}/commodities/{indicator.lower()}",
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if not resp.ok:
        result = (None, f"API error {resp.status_code}: {resp.text[:120]}")
    else:
        rows = resp.json().get("data", [])
        if not rows:
            result = (None, f"No data returned for **{indicator}**.")
        else:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            result = (df.sort_values("date").reset_index(drop=True), None)

    _cache_put(cache_key, result)
    return result


# ─── Chart builders ───────────────────────────────────────────────────────────


def _line_chart(
    df: pd.DataFrame,
    title: str,
    y_label: str,
    color: str = "#1E88E5",
    height: int = 360,
) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=df["date"],
            y=df["val"],
            mode="lines",
            name=title,
            line=dict(color=color, width=2),
            hovertemplate="%{x|%Y-%m-%d}: <b>%{y}</b><extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        height=height,
    )
    return fig


def _multi_line_chart(
    series: dict[str, pd.DataFrame],
    title: str,
    y_label: str,
    height: int = 420,
) -> go.Figure:
    fig = go.Figure()
    for i, (label, df) in enumerate(series.items()):
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["val"],
                mode="lines",
                name=label,
                line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                hovertemplate=(
                    f"{label} %{{x|%Y-%m-%d}}: <b>%{{y}}</b><extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=70, b=40),
        height=height,
    )
    return fig


# ─── Utilities ────────────────────────────────────────────────────────────────


def _date_range(years: int) -> tuple[str, str]:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=years * 365)
    return start.isoformat(), end.isoformat()


def _extract_code(currency_label: str) -> str:
    """Extract ISO code from a label like '🇺🇸 USD' → 'USD'."""
    return currency_label.split()[-1]


def _metric_md(
    label: str, latest: Optional[float], delta: Optional[float], unit: str
) -> str:
    if latest is None:
        return f"**{label}**\n\n*No data*"
    val_str = f"{latest:,.4g} {unit}".strip()
    delta_str = f"  Δ {delta:+.4g}" if delta is not None else ""
    return f"**{label}**\n\n{val_str}{delta_str}"


# ─── Sidebar widgets ──────────────────────────────────────────────────────────

w_api_key = pn.widgets.PasswordInput(
    name="Professional API Key",
    placeholder="Paste your key (USD is always free)",
    sizing_mode="stretch_width",
)

w_years = pn.widgets.IntSlider(
    name="History (years)",
    start=1,
    end=10,
    value=5,
    sizing_mode="stretch_width",
)

# ─── Metals tab widgets ───────────────────────────────────────────────────────

# (no extra widgets needed — uses global api_key + years)

# ─── Macro indicator tab widgets ──────────────────────────────────────────────

w_currency = pn.widgets.Select(
    name="Currency",
    options={f"{CURRENCY_FLAGS.get(c, '')} {c}": c for c in ALL_CURRENCIES},
    value="USD",
    width=180,
)

w_indicator = pn.widgets.Select(
    name="Indicator",
    options={v[0]: k for k, v in INDICATORS.items()},
    value="policy_rate",
    width=200,
)

# ─── Multi-currency compare tab widgets ───────────────────────────────────────

w_multi_currencies = pn.widgets.MultiChoice(
    name="Currencies to compare",
    options={f"{CURRENCY_FLAGS.get(c, '')} {c}": c for c in ALL_CURRENCIES},
    value=["USD", "EUR", "GBP", "AUD"],
    sizing_mode="stretch_width",
)

w_multi_indicator = pn.widgets.Select(
    name="Indicator",
    options={v[0]: k for k, v in INDICATORS.items()},
    value="policy_rate",
    width=200,
)


# ─── View builders ────────────────────────────────────────────────────────────


def _info(msg: str) -> pn.pane.Markdown:
    return pn.pane.Markdown(
        f"> ℹ️ {msg}",
        sizing_mode="stretch_width",
    )


def _warn(msg: str) -> pn.pane.Markdown:
    return pn.pane.Markdown(
        f"> ⚠️ {msg}",
        sizing_mode="stretch_width",
    )


def metals_view(years: int, api_key: str) -> pn.Column:
    start, end = _date_range(years)
    key = api_key.strip() or None
    items: list = [
        pn.pane.Markdown(
            "Daily **gold**, **silver**, and **platinum** spot prices sourced "
            "from official bullion data via the FXMacroData API.  \n"
            "_Precious metals data is available on the free tier — no API key required._",
            sizing_mode="stretch_width",
        ),
        pn.layout.Divider(),
    ]

    for commodity in COMMODITIES:
        label, unit, color = COMMODITY_DISPLAY_METADATA[commodity]
        df, err = fetch_commodity(commodity, key, start, end)

        if err:
            items.append(_warn(f"**{label}**: {err}"))
            continue

        clean = df.dropna(subset=["val"])
        latest = float(clean.iloc[-1]["val"]) if not clean.empty else None
        prev = float(clean.iloc[-2]["val"]) if len(clean) > 1 else None
        delta = (latest - prev) if (latest is not None and prev is not None) else None

        metric = _metric_md(label, latest, delta, unit)
        chart = pn.pane.Plotly(
            _line_chart(df, label, unit, color),
            sizing_mode="stretch_width",
        )
        items.append(
            pn.Row(
                pn.pane.Markdown(metric, width=200, align="center"),
                chart,
                sizing_mode="stretch_width",
            )
        )
        items.append(pn.layout.Divider())

    return pn.Column(*items, sizing_mode="stretch_width")


def macro_view(
    currency: str, indicator_key: str, years: int, api_key: str
) -> pn.Column:
    start, end = _date_range(years)
    key = api_key.strip() or None

    if currency != FREE_CURRENCY and not key:
        return pn.Column(
            _info(
                f"Enter your **Professional API key** in the sidebar to load "
                f"{currency} data.  "
                f"[Get a free key]({API_KEYS_URL})."
            ),
            sizing_mode="stretch_width",
        )

    label, unit = INDICATORS.get(indicator_key, (indicator_key, ""))
    flag = CURRENCY_FLAGS.get(currency, "")
    title = f"{flag} {currency} — {label}"

    df, err = fetch_indicator(currency, indicator_key, key, start, end)
    if err:
        return pn.Column(_warn(err), sizing_mode="stretch_width")

    clean = df.dropna(subset=["val"])
    latest = float(clean.iloc[-1]["val"]) if not clean.empty else None
    prev = float(clean.iloc[-2]["val"]) if len(clean) > 1 else None
    delta = (latest - prev) if (latest is not None and prev is not None) else None

    return pn.Column(
        pn.pane.Markdown(
            _metric_md(title, latest, delta, unit),
            sizing_mode="stretch_width",
        ),
        pn.pane.Plotly(
            _line_chart(df, title, unit or label),
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )


def multi_view(
    currencies: list,
    indicator_key: str,
    years: int,
    api_key: str,
) -> pn.Column:
    if not currencies:
        return pn.Column(
            _warn("Select at least one currency above."),
            sizing_mode="stretch_width",
        )

    start, end = _date_range(years)
    key = api_key.strip() or None
    label, unit = INDICATORS.get(indicator_key, (indicator_key, ""))

    series: dict[str, pd.DataFrame] = {}
    notices: list[str] = []

    for currency in currencies:
        curr_key = None if currency == FREE_CURRENCY else key
        if currency != FREE_CURRENCY and not key:
            notices.append(
                f"**{currency}**: API key required — "
                f"[get a free key]({API_KEYS_URL})."
            )
            continue

        df, err = fetch_indicator(currency, indicator_key, curr_key, start, end)
        if err:
            notices.append(f"**{currency}**: {err}")
            continue

        flag = CURRENCY_FLAGS.get(currency, "")
        series[f"{flag} {currency}"] = df

    items: list = []

    if notices:
        items.append(_warn("  \n".join(notices)))

    if not series:
        if not notices:
            items.append(_warn("No data loaded."))
        return pn.Column(*items, sizing_mode="stretch_width")

    items.append(
        pn.pane.Plotly(
            _multi_line_chart(
                series, f"{label} — Multi-Currency Comparison", unit or label
            ),
            sizing_mode="stretch_width",
        )
    )

    # Summary table
    rows = []
    for currency_label, df in series.items():
        clean = df.dropna(subset=["val"])
        if clean.empty:
            continue
        last = clean.iloc[-1]
        prev = clean.iloc[-2] if len(clean) > 1 else None
        delta = float(last["val"]) - float(prev["val"]) if prev is not None else None
        rows.append(
            {
                "Currency": currency_label,
                "Latest Date": last["date"].strftime("%Y-%m-%d"),
                f"Latest {unit or 'Value'}": round(float(last["val"]), 4),
                "Change": round(delta, 4) if delta is not None else None,
            }
        )

    if rows:
        items.append(
            pn.widgets.DataFrame(
                pd.DataFrame(rows).set_index("Currency"),
                sizing_mode="stretch_width",
                disabled=True,
            )
        )

    return pn.Column(*items, sizing_mode="stretch_width")


# ─── About content ────────────────────────────────────────────────────────────

_ABOUT_MD = f"""
## About This App

**[FXMacroData]({SITE_URL})** is a professional macroeconomic data API built for FX
traders, quantitative analysts, and algorithmic trading teams.  This Panel app
demonstrates three of the API's endpoint families.

### API Endpoints Used

| Endpoint | Auth | Description |
|---|---|---|
| `GET /v1/announcements/usd/{{indicator}}` | Free | USD macro indicator history |
| `GET /v1/announcements/{{currency}}/{{indicator}}` | API key | Non-USD indicator history |
| `GET /v1/commodities/{{indicator}}` | Free | Precious metals spot prices |

### What's Included in FXMacroData

- 📊 **40+ indicators** per currency — inflation, GDP, unemployment, policy rates,
  PMI, retail sales, and more.
- 🏦 **18 currencies** — USD, EUR, GBP, AUD, JPY, CAD, CHF, NZD, CNY, HKD, SGD,
  KRW, NOK, SEK, DKK, PLN, BRL, MXN.
- ⚡ **Low-latency REST API** — clean JSON, zero pre-processing required.
- 🗓️ **Release calendars** — know exactly when the next data drop lands.
- 📈 **COT positioning data** — CFTC Commitment of Traders for FX futures.
- 💎 **Precious metals** — daily gold, silver, and platinum spot prices.

### Free vs Professional

| Feature | Free | Professional |
|---|---|---|
| USD macro indicators | ✅ | ✅ |
| Precious metals data | ✅ | ✅ |
| All 18 currency indicators | ❌ | ✅ |
| COT positioning data | ❌ | ✅ |
| Release calendars | ❌ | ✅ |
| Commercial use | ❌ | ✅ |
| Price | $0 | $25/month |

### Links

- 🌐 [FXMacroData Website]({SITE_URL})
- 📖 [API Documentation]({DOCS_URL})
- 🔑 [Get your API key]({API_KEYS_URL})

---
*This example app is open-source.  Run it locally with `panel serve app.py --autoreload`.*
"""


# ─── Bind reactive views to widgets ──────────────────────────────────────────

metals_pane = pn.bind(metals_view, years=w_years, api_key=w_api_key)
macro_pane = pn.bind(
    macro_view,
    currency=w_currency,
    indicator_key=w_indicator,
    years=w_years,
    api_key=w_api_key,
)
multi_pane = pn.bind(
    multi_view,
    currencies=w_multi_currencies,
    indicator_key=w_multi_indicator,
    years=w_years,
    api_key=w_api_key,
)

# ─── Tab layout ───────────────────────────────────────────────────────────────

tabs = pn.Tabs(
    (
        "💎 Precious Metals",
        pn.Column(metals_pane, sizing_mode="stretch_width"),
    ),
    (
        "📊 Macro Indicators",
        pn.Column(
            pn.Row(w_currency, w_indicator, sizing_mode="stretch_width"),
            macro_pane,
            sizing_mode="stretch_width",
        ),
    ),
    (
        "🌍 Multi-Currency Compare",
        pn.Column(
            pn.Row(w_multi_currencies, w_multi_indicator, sizing_mode="stretch_width"),
            multi_pane,
            sizing_mode="stretch_width",
        ),
    ),
    ("ℹ️ About", pn.pane.Markdown(_ABOUT_MD, sizing_mode="stretch_width")),
    sizing_mode="stretch_width",
    dynamic=True,
)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

sidebar = pn.Column(
    pn.pane.Markdown(
        f"## FXMacroData\n\n"
        f"Institutional-grade macro & FX data API.\n\n"
        f"[Website]({SITE_URL}) · [Docs]({DOCS_URL}) · [API Keys]({API_KEYS_URL})",
        sizing_mode="stretch_width",
    ),
    pn.layout.Divider(),
    w_api_key,
    pn.pane.Markdown(
        "_USD announcement data is public — no API key required.  \n"
        f"[Get a Professional key]({API_KEYS_URL}) to unlock protected non-USD announcements._",
        sizing_mode="stretch_width",
    ),
    pn.layout.Divider(),
    w_years,
    sizing_mode="stretch_width",
)

# ─── App template ─────────────────────────────────────────────────────────────

template = pn.template.FastListTemplate(
    title="FXMacroData – FX Macro Intelligence Dashboard",
    sidebar=sidebar,
    main=[tabs],
    header_background="#0B1426",
    accent="#22C55E",
)

template.servable()
