"""
FXMacroData – FX & Macro Explorer
==================================
A Gradio example app for exploring macroeconomic indicators, FX spot rates,
and economic release calendars via the FXMacroData REST API.

Free tier  : USD macro indicators + any FX pair — no API key required.
Pro tier   : All 18 currencies — requires a Professional API key.
             Get yours at https://fxmacrodata.com/api-management

Run locally
-----------
    pip install -r requirements.txt
    python app.py
    # then open http://localhost:7860

Deploy to Hugging Face Spaces (free)
--------------------------------------
    # Choose the Gradio SDK when creating a new Space.
    # Upload app.py and requirements.txt — the Space builds automatically.
    # See README.md for full deploy steps.
"""

import datetime
import time
from typing import Optional

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import requests

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

CURRENCY_FLAGS = {
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

# (display_label, unit)
INDICATORS: dict[str, tuple[str, str]] = {
    "policy_rate": ("Policy Rate", "%"),
    "inflation": ("CPI Inflation (YoY)", "% YoY"),
    "gdp": ("GDP Growth (YoY)", "% YoY"),
    "unemployment": ("Unemployment Rate", "%"),
    "non_farm_payrolls": ("Non-Farm Payrolls", "k"),
    "retail_sales": ("Retail Sales (MoM)", "% MoM"),
    "pmi": ("Manufacturing PMI", ""),
    "trade_balance": ("Trade Balance", ""),
}

FX_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
    "USD/CAD",
    "USD/CHF",
    "NZD/USD",
    "USD/CNY",
    "GBP/EUR",
    "AUD/JPY",
    "EUR/GBP",
    "EUR/JPY",
    "GBP/JPY",
]

CHART_COLORS = [
    "#1E88E5",
    "#E53935",
    "#43A047",
    "#FB8C00",
    "#7B1FA2",
    "#00897B",
    "#546E7A",
    "#F4511E",
]

_CACHE_TTL = 300  # seconds

# ─── In-memory request cache ──────────────────────────────────────────────────

_cache: dict = {}


def _cache_get(key: str) -> Optional[tuple]:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
        return entry[1], entry[2]
    return None


def _cache_put(key: str, data, status: str) -> None:
    _cache[key] = (time.monotonic(), data, status)


# ─── API helpers ──────────────────────────────────────────────────────────────


def fetch_indicator(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], str]:
    """Fetch indicator time-series from the FXMacroData announcements endpoint.

    Returns ``(df, status)`` where ``status`` is ``"ok"`` on success or an
    error message string on failure.
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
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code == 401:
        msg = f"🔑 API key required for {currency}. [Get yours here]({API_KEYS_URL})."
        _cache_put(cache_key, None, msg)
        return None, msg
    if resp.status_code == 403:
        return None, "❌ Invalid API key — please check and try again."
    if resp.status_code == 404:
        msg = f"No data found for {currency} / {indicator}."
        _cache_put(cache_key, None, msg)
        return None, msg
    if not resp.ok:
        return None, f"API error {resp.status_code}."

    rows = resp.json().get("data", [])
    if not rows:
        msg = f"No data returned for {currency} / {indicator}."
        _cache_put(cache_key, None, msg)
        return None, msg

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    _cache_put(cache_key, df, "ok")
    return df, "ok"


def fetch_forex(
    base: str,
    quote: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], str]:
    """Fetch FX spot rate history from the FXMacroData forex endpoint."""
    cache_key = f"fx|{base}|{quote}|{api_key or ''}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(
            f"{API_BASE}/forex/{base.lower()}/{quote.lower()}",
            params=params,
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code == 401:
        msg = f"🔑 API key required. [Get yours here]({API_KEYS_URL})."
        _cache_put(cache_key, None, msg)
        return None, msg
    if resp.status_code == 403:
        return None, "❌ Invalid API key — please check and try again."
    if not resp.ok:
        return None, f"API error {resp.status_code}."

    rows = resp.json().get("data", [])
    if not rows:
        msg = f"No FX data returned for {base}/{quote}."
        _cache_put(cache_key, None, msg)
        return None, msg

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    _cache_put(cache_key, df, "ok")
    return df, "ok"


def fetch_calendar(
    currency: str,
    api_key: Optional[str],
) -> tuple[Optional[list], str]:
    """Fetch upcoming release calendar from the FXMacroData calendar endpoint."""
    cache_key = f"cal|{currency}|{api_key or ''}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict = {}
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(
            f"{API_BASE}/calendar/{currency.lower()}",
            params=params,
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code == 401:
        msg = (
            f"🔑 API key required for {currency} calendar. "
            f"[Get yours here]({API_KEYS_URL})."
        )
        _cache_put(cache_key, None, msg)
        return None, msg
    if resp.status_code == 403:
        return None, "❌ Invalid API key — please check and try again."
    if not resp.ok:
        return None, f"API error {resp.status_code}."

    events = resp.json().get("data", [])
    if not events:
        msg = f"No upcoming releases found for {currency}."
        _cache_put(cache_key, None, msg)
        return None, msg

    _cache_put(cache_key, events, "ok")
    return events, "ok"


# ─── UI callback functions ────────────────────────────────────────────────────


def _label_to_key(label: str) -> str:
    """Resolve a display label back to its INDICATORS dict key."""
    for key, (lbl, _) in INDICATORS.items():
        if lbl == label:
            return key
    return label


def explore_indicator(
    currency: str,
    indicator_label: str,
    years_back: int,
    api_key: str,
) -> tuple[Optional[go.Figure], str, Optional[pd.DataFrame]]:
    """Load and chart a macro indicator time series."""
    indicator_key = _label_to_key(indicator_label)
    label, unit = INDICATORS[indicator_key]

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=int(years_back) * 365)

    key: Optional[str] = (
        None if currency == FREE_CURRENCY else (api_key.strip() if api_key else None)
    )
    df, status = fetch_indicator(
        currency,
        indicator_key,
        key,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    if df is None:
        return None, status, None

    flag = CURRENCY_FLAGS.get(currency, "")
    title = f"{flag} {currency} {label}"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val"],
            mode="lines+markers",
            name=title,
            line=dict(color=CHART_COLORS[0], width=2),
            marker=dict(size=4),
            hovertemplate="%{x|%b %Y}: <b>%{y}</b><extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=unit or label,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=60, b=40),
        height=420,
    )

    # Build a summary stats table
    clean = df.dropna(subset=["val"])
    if not clean.empty:
        latest_val = float(clean.iloc[-1]["val"])
        prev_val = float(clean.iloc[-2]["val"]) if len(clean) > 1 else None
        change = (latest_val - prev_val) if prev_val is not None else None
        stats_rows = [
            ("Latest value", f"{latest_val:.4g} {unit}".strip()),
            ("Latest date", clean.iloc[-1]["date"].strftime("%Y-%m-%d")),
            (
                "Previous value",
                f"{prev_val:.4g} {unit}".strip() if prev_val is not None else "N/A",
            ),
            (
                "Change",
                f"{change:+.4g} {unit}".strip() if change is not None else "N/A",
            ),
            ("Period min", f"{clean['val'].min():.4g} {unit}".strip()),
            ("Period max", f"{clean['val'].max():.4g} {unit}".strip()),
            ("Data points", str(len(clean))),
        ]
    else:
        stats_rows = []

    stats_df = pd.DataFrame(stats_rows, columns=["Metric", "Value"])

    return fig, "✅ Data loaded successfully.", stats_df


def explore_forex(
    pair: str,
    years_back: int,
    api_key: str,
) -> tuple[Optional[go.Figure], str, Optional[pd.DataFrame]]:
    """Load and chart a FX spot rate series."""
    base, quote = pair.split("/")

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=int(years_back) * 365)

    key: Optional[str] = api_key.strip() if api_key else None
    df, status = fetch_forex(
        base,
        quote,
        key,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    if df is None:
        return None, status, None

    title = f"{base}/{quote} Exchange Rate"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val"],
            mode="lines",
            name=f"{base}/{quote}",
            line=dict(color=CHART_COLORS[0], width=2),
            hovertemplate="%{x|%Y-%m-%d}: <b>%{y:.5f}</b><extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=f"{base}/{quote}",
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=60, b=40),
        height=420,
    )

    # Recent rates table (last 20, newest first)
    table = df[["date", "val"]].tail(20).iloc[::-1].copy()
    table.columns = ["Date", "Rate"]
    table["Date"] = table["Date"].dt.strftime("%Y-%m-%d")
    table["Rate"] = table["Rate"].round(5)
    table = table.reset_index(drop=True)

    return fig, "✅ Data loaded successfully.", table


def explore_calendar(
    currency: str,
    api_key: str,
) -> tuple[str, Optional[pd.DataFrame]]:
    """Load upcoming release calendar for a currency."""
    key: Optional[str] = (
        None if currency == FREE_CURRENCY else (api_key.strip() if api_key else None)
    )
    events, status = fetch_calendar(currency, key)

    if events is None:
        return status, None

    rows = []
    for event in events:
        ts = event.get("announcement_datetime")
        if ts:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            release_date = dt.strftime("%Y-%m-%d")
            release_time = dt.strftime("%H:%M UTC")
        else:
            release_date = release_time = "—"

        release_key = event.get("release", "")
        label, unit = INDICATORS.get(
            release_key, (release_key.replace("_", " ").title(), "")
        )

        rows.append(
            {
                "Date": release_date,
                "Time (UTC)": release_time,
                "Indicator": label,
                "Currency": currency,
            }
        )

    if not rows:
        return "No upcoming releases found.", None

    df = pd.DataFrame(rows).drop_duplicates(subset=["Date", "Indicator"])
    df = df.sort_values("Date").reset_index(drop=True)

    return "✅ Calendar loaded.", df


def compare_currencies(
    currencies: list[str],
    indicator_label: str,
    years_back: int,
    api_key: str,
) -> tuple[Optional[go.Figure], str]:
    """Compare a single indicator across multiple currencies."""
    if not currencies:
        return None, "⚠️ Please select at least one currency."

    indicator_key = _label_to_key(indicator_label)
    label, unit = INDICATORS[indicator_key]

    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=int(years_back) * 365)
    key: Optional[str] = api_key.strip() if api_key else None

    fig = go.Figure()
    errors: list[str] = []

    for i, currency in enumerate(currencies):
        curr_key = None if currency == FREE_CURRENCY else key
        df, status = fetch_indicator(
            currency,
            indicator_key,
            curr_key,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        if df is None:
            errors.append(f"**{currency}**: {status}")
            continue

        flag = CURRENCY_FLAGS.get(currency, "")
        color = CHART_COLORS[i % len(CHART_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["val"],
                mode="lines",
                name=f"{flag} {currency}",
                line=dict(color=color, width=2),
                hovertemplate=f"{currency} %{{x|%b %Y}}: <b>%{{y}}</b><extra></extra>",
            )
        )

    if not fig.data:
        return None, "\n\n".join(errors) if errors else "No data available."

    fig.update_layout(
        title=f"{label} — Multi-Currency Comparison",
        xaxis_title="Date",
        yaxis_title=unit or label,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=80, b=40),
        height=460,
    )

    msg = "✅ Data loaded."
    if errors:
        msg += "\n\n⚠️ " + "; ".join(errors)
    return fig, msg


# ─── Gradio interface ─────────────────────────────────────────────────────────

_INDICATOR_LABELS = [label for label, _ in INDICATORS.values()]

_ABOUT_MD = f"""
## About FXMacroData

**[FXMacroData]({SITE_URL})** is a professional macroeconomic data API built for
FX traders, quantitative analysts, and systematic trading teams.

### What you get

- 📊 **40+ indicators** per currency — inflation, GDP, unemployment, policy rates,
  PMI, retail sales, and more.
- 🏦 **18 currencies** — USD, EUR, GBP, AUD, JPY, CAD, CHF, NZD, CNY, HKD, SGD,
  KRW, NOK, SEK, DKK, PLN, BRL, MXN.
- ⚡ **Low-latency REST API** — clean JSON, zero pre-processing required.
- 💱 **FX spot rates** — daily closing prices for all major and cross pairs.
- 🗓️ **Release calendars** — know exactly when the next data drop lands.
- 📈 **COT positioning data** — CFTC Commitment of Traders for FX futures.
- 💎 **Precious metals** — daily gold, silver, and platinum spot prices.

### Free vs Professional

| Feature | Free | Professional |
|---|---|---|
| USD macro indicators | ✅ | ✅ |
| FX spot rates | ✅ | ✅ |
| All 18 currency indicators | ❌ | ✅ |
| COT positioning data | ❌ | ✅ |
| Release calendars | ❌ | ✅ |
| Commercial use | ❌ | ✅ |
| **Price** | **$0** | **$25/month** |

### Links

- 🌐 [FXMacroData Website]({SITE_URL})
- 📖 [API Documentation]({DOCS_URL})
- 🔑 [Get your API key]({API_KEYS_URL})

---
*This example app is open-source. Fork it and deploy it on
[Hugging Face Spaces](https://huggingface.co/spaces) for free.*
"""

with gr.Blocks(title="FX & Macro Explorer – FXMacroData") as demo:

    gr.Markdown(f"""
        # 📊 FX & Macro Explorer
        **[FXMacroData]({SITE_URL})** · Institutional-grade macroeconomic and FX data API

        > **USD announcement data is public** — no API key required.
        > [Get a Professional key]({API_KEYS_URL}) to unlock protected non-USD announcements.
        """)

    with gr.Row():
        api_key_input = gr.Textbox(
            label="🔑 Professional API Key (optional)",
            placeholder="Paste your key to unlock protected non-USD announcements",
            type="password",
            scale=2,
        )
        with gr.Column(scale=3):
            gr.Markdown(
                f"No key? **USD announcement data is public.**  \n"
                f"[Get a Professional key]({API_KEYS_URL}) — unlocks all 18 currencies."
            )

    with gr.Tabs():

        # ── Tab 1: Indicator Explorer ──────────────────────────────────────────
        with gr.Tab("📈 Indicator Explorer"):
            gr.Markdown(
                "Select a currency and indicator to explore the historical time series.  \n"
                "USD is always free. A Professional API key is required for other currencies."
            )

            with gr.Row():
                ind_currency = gr.Dropdown(
                    choices=ALL_CURRENCIES,
                    value=FREE_CURRENCY,
                    label="Currency",
                    scale=1,
                )
                ind_indicator = gr.Dropdown(
                    choices=_INDICATOR_LABELS,
                    value="Policy Rate",
                    label="Indicator",
                    scale=2,
                )
                ind_years = gr.Slider(
                    minimum=1,
                    maximum=15,
                    value=5,
                    step=1,
                    label="History (years)",
                    scale=2,
                )

            ind_btn = gr.Button("🔍 Load Data", variant="primary")
            ind_status = gr.Markdown("*Press **Load Data** to fetch the indicator.*")
            ind_chart = gr.Plot(label="Time Series")
            ind_stats = gr.DataFrame(label="Summary Statistics", interactive=False)

            ind_btn.click(
                fn=explore_indicator,
                inputs=[ind_currency, ind_indicator, ind_years, api_key_input],
                outputs=[ind_chart, ind_status, ind_stats],
            )

        # ── Tab 2: Multi-Currency Comparison ──────────────────────────────────
        with gr.Tab("🌍 Multi-Currency"):
            gr.Markdown(
                "Compare a single indicator across multiple currencies on one chart.  \n"
                "USD is free. A Professional API key is required for all other currencies."
            )

            with gr.Row():
                mc_currencies = gr.CheckboxGroup(
                    choices=ALL_CURRENCIES,
                    value=[FREE_CURRENCY, "EUR", "GBP", "AUD"],
                    label="Currencies to compare",
                    scale=3,
                )
                with gr.Column(scale=2):
                    mc_indicator = gr.Dropdown(
                        choices=_INDICATOR_LABELS,
                        value="Policy Rate",
                        label="Indicator",
                    )
                    mc_years = gr.Slider(
                        minimum=1,
                        maximum=15,
                        value=5,
                        step=1,
                        label="History (years)",
                    )

            mc_btn = gr.Button("🔍 Compare", variant="primary")
            mc_status = gr.Markdown(
                "*Press **Compare** to fetch and overlay the series.*"
            )
            mc_chart = gr.Plot(label="Multi-Currency Comparison")

            mc_btn.click(
                fn=compare_currencies,
                inputs=[mc_currencies, mc_indicator, mc_years, api_key_input],
                outputs=[mc_chart, mc_status],
            )

        # ── Tab 3: FX Rates ────────────────────────────────────────────────────
        with gr.Tab("💱 FX Rates"):
            gr.Markdown(
                "Look up historical FX spot rates for any currency pair.  \n"
                "All pairs are available with no API key required."
            )

            with gr.Row():
                fx_pair = gr.Dropdown(
                    choices=FX_PAIRS,
                    value="EUR/USD",
                    label="Currency Pair",
                    scale=2,
                )
                fx_years = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=2,
                    step=1,
                    label="History (years)",
                    scale=3,
                )

            fx_btn = gr.Button("🔍 Load Rates", variant="primary")
            fx_status = gr.Markdown(
                "*Press **Load Rates** to fetch the exchange rate history.*"
            )
            fx_chart = gr.Plot(label="Exchange Rate")
            fx_table = gr.DataFrame(
                label="Recent Rates (newest first)", interactive=False
            )

            fx_btn.click(
                fn=explore_forex,
                inputs=[fx_pair, fx_years, api_key_input],
                outputs=[fx_chart, fx_status, fx_table],
            )

        # ── Tab 4: Release Calendar ────────────────────────────────────────────
        with gr.Tab("🗓️ Release Calendar"):
            gr.Markdown(
                "See upcoming economic data release dates for a currency.  \n"
                "USD calendar is free. Other currencies require a Professional API key."
            )

            with gr.Row():
                cal_currency = gr.Dropdown(
                    choices=ALL_CURRENCIES,
                    value=FREE_CURRENCY,
                    label="Currency",
                    scale=1,
                )

            cal_btn = gr.Button("📅 Load Calendar", variant="primary")
            cal_status = gr.Markdown(
                "*Press **Load Calendar** to fetch upcoming releases.*"
            )
            cal_table = gr.DataFrame(label="Upcoming Releases", interactive=False)

            cal_btn.click(
                fn=explore_calendar,
                inputs=[cal_currency, api_key_input],
                outputs=[cal_status, cal_table],
            )

        # ── Tab 5: About ───────────────────────────────────────────────────────
        with gr.Tab("ℹ️ About"):
            gr.Markdown(_ABOUT_MD)


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
