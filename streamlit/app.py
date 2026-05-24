"""
FXMacroData – Central Bank Rate Monitor
========================================
A Streamlit example app demonstrating how to use the FXMacroData REST API.

Free tier:   USD announcement indicators — no API key required.
Pro tier:    Non-USD announcement indicators — requires a Professional API key.
             Get yours at https://fxmacrodata.com/api-management
"""

import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://fxmacrodata.com/api"

SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

# Currencies available with a Professional API key (free = USD only)
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

# Indicators supported by the /v1/announcements/{currency}/{indicator} endpoint
INDICATORS = {
    "policy_rate": "Policy Rate (%)",
    "inflation": "CPI Inflation (YoY %)",
    "gdp": "GDP Growth (YoY %)",
    "unemployment": "Unemployment Rate (%)",
    "non_farm_payrolls": "Non-Farm Payrolls (k)",
    "retail_sales": "Retail Sales (MoM %)",
    "pmi": "Manufacturing PMI",
    "trade_balance": "Trade Balance",
}

INDICATOR_UNITS = {
    "policy_rate": "%",
    "inflation": "% YoY",
    "gdp": "% YoY",
    "unemployment": "%",
    "non_farm_payrolls": "k",
    "retail_sales": "% MoM",
    "pmi": "",
    "trade_balance": "",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_url(currency: str, indicator: str, api_key: Optional[str] = None) -> str:
    url = f"{API_BASE}/v1/announcements/{currency.lower()}/{indicator}"
    if api_key:
        url += f"?api_key={api_key}"
    return url


@st.cache_data(ttl=300, show_spinner=False)
def fetch_indicator(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch indicator data from the FXMacroData API.

    Returns (dataframe, error_message).  On success error_message is None.
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(
            f"{API_BASE}/v1/announcements/{currency.lower()}/{indicator}",
            params=params,
            timeout=15,
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code == 401:
        return None, (
            "🔑 **API key required for this currency.**  "
            f"[Get your free Professional key]({API_KEYS_URL}) to unlock protected non-USD announcements."
        )
    if resp.status_code == 403:
        return None, "❌ Invalid API key.  Please check your key and try again."
    if resp.status_code == 404:
        return None, f"No data found for **{currency} / {indicator}**."
    if not resp.ok:
        return None, f"API error {resp.status_code}: {resp.text[:200]}"

    payload = resp.json()
    rows = payload.get("data", [])
    if not rows:
        return None, f"No data returned for **{currency} / {indicator}**."

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df, None


def _plot_series(
    df: pd.DataFrame,
    title: str,
    y_label: str,
    color: str = "#1E88E5",
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val"],
            mode="lines+markers",
            name=title,
            line=dict(color=color, width=2),
            marker=dict(size=4),
            hovertemplate="%{x|%b %Y}: <b>%{y}</b><extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_label,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        height=380,
    )
    return fig


def _latest_value(df: pd.DataFrame) -> Optional[str]:
    clean = df.dropna(subset=["val"])
    if clean.empty:
        return None
    return f"{clean.iloc[-1]['val']:.2f}"


def _delta_value(df: pd.DataFrame) -> Optional[float]:
    clean = df.dropna(subset=["val"])
    if len(clean) < 2:
        return None
    return float(clean.iloc[-1]["val"]) - float(clean.iloc[-2]["val"])


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Central Bank Rate Monitor – FXMacroData",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image(
        "https://fxmacrodata.com/static/images/logo.png",
        use_container_width=True,
    )
    st.markdown(
        f"**[FXMacroData]({SITE_URL})** — institutional-grade macro & FX data API."
    )
    st.divider()

    st.subheader("🔑 API Key")
    api_key_input = st.text_input(
        "Professional API key",
        type="password",
        placeholder="Paste your API key here",
        help=(
            "USD announcement data is public — no key needed.  "
            "Enter your Professional key to unlock protected non-USD announcements."
        ),
    )
    api_key: Optional[str] = api_key_input.strip() or None

    if api_key:
        st.success("API key set ✅")
    else:
        st.info(
            f"No key?  [Get free access]({API_KEYS_URL}) — "
            "USD announcement data is public."
        )

    st.divider()
    st.subheader("⚙️ Settings")

    years_back = st.slider("History (years)", min_value=1, max_value=10, value=5)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=years_back * 365)

    st.divider()
    st.markdown(
        f"📖 [API Docs]({DOCS_URL})  •  "
        f"🔑 [Get API key]({API_KEYS_URL})  •  "
        f"🌐 [FXMacroData]({SITE_URL})"
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("📊 Central Bank Rate Monitor")
st.markdown(
    "Explore macroeconomic indicators sourced directly from central banks and "
    "statistical agencies via the **[FXMacroData API](https://fxmacrodata.com)**.\n\n"
    "**USD announcement data is public** — no API key required.  "
    f"[Get a Professional key]({API_KEYS_URL}) to unlock protected non-USD announcements."
)
st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_usd, tab_multi, tab_about = st.tabs(
    ["🇺🇸 USD Dashboard (Free)", "🌍 Multi-Currency (Pro)", "ℹ️ About"]
)

# ── Tab 1: USD Dashboard (free) ──────────────────────────────────────────────

with tab_usd:
    st.subheader("United States Macro Indicators")
    st.caption(
        "All data below is served for free — no API key required.  "
        "Data sourced from the Federal Reserve and US statistical agencies."
    )

    free_indicators = [
        ("policy_rate", "#1E88E5"),
        ("inflation", "#E53935"),
        ("gdp", "#43A047"),
        ("unemployment", "#FB8C00"),
    ]

    for indicator_key, color in free_indicators:
        indicator_label = INDICATORS[indicator_key]
        unit = INDICATOR_UNITS[indicator_key]

        with st.spinner(f"Loading {indicator_label}…"):
            df, err = fetch_indicator(
                "USD",
                indicator_key,
                None,
                start_date.isoformat(),
                end_date.isoformat(),
            )

        if err:
            st.warning(f"**{indicator_label}**: {err}")
            continue

        col_chart, col_metric = st.columns([4, 1])
        with col_chart:
            fig = _plot_series(df, f"USD {indicator_label}", unit, color)
            st.plotly_chart(fig, use_container_width=True)

        with col_metric:
            latest = _latest_value(df)
            delta = _delta_value(df)
            st.metric(
                label=f"Latest {indicator_label}",
                value=f"{latest} {unit}".strip() if latest is not None else "N/A",
                delta=f"{delta:+.2f} {unit}".strip() if delta is not None else None,
            )

        st.divider()

    # Additional USD indicators (expandable)
    with st.expander("📋 More USD Indicators"):
        extra_indicators = [
            ("non_farm_payrolls", "#7B1FA2"),
            ("retail_sales", "#00897B"),
            ("pmi", "#546E7A"),
        ]
        for indicator_key, color in extra_indicators:
            indicator_label = INDICATORS[indicator_key]
            unit = INDICATOR_UNITS[indicator_key]

            with st.spinner(f"Loading {indicator_label}…"):
                df, err = fetch_indicator(
                    "USD",
                    indicator_key,
                    None,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )

            if err:
                st.warning(f"**{indicator_label}**: {err}")
                continue

            fig = _plot_series(df, f"USD {indicator_label}", unit, color)
            st.plotly_chart(fig, use_container_width=True)
            st.divider()

# ── Tab 2: Multi-Currency (pro) ───────────────────────────────────────────────

with tab_multi:
    st.subheader("Multi-Currency Comparison")

    if not api_key:
        st.info(
            f"🔑 Enter your **Professional API key** in the sidebar to unlock "
            f"data for all 18 currencies.\n\n"
            f"[Get your free API key]({API_KEYS_URL}) — "
            "Professional plan starts at **$25/month**."
        )
        st.markdown("---")
        st.markdown("#### What you'll unlock:")
        cols = st.columns(3)
        currencies_preview = [
            ("🇪🇺 EUR", "European Central Bank"),
            ("🇬🇧 GBP", "Bank of England"),
            ("🇦🇺 AUD", "Reserve Bank of Australia"),
            ("🇯🇵 JPY", "Bank of Japan"),
            ("🇨🇦 CAD", "Bank of Canada"),
            ("🇨🇭 CHF", "Swiss National Bank"),
            ("🇳🇿 NZD", "Reserve Bank of New Zealand"),
            ("🇨🇳 CNY", "People's Bank of China"),
            ("🇸🇬 SGD", "Monetary Authority of Singapore"),
        ]
        for i, (flag_code, bank) in enumerate(currencies_preview):
            with cols[i % 3]:
                st.markdown(f"**{flag_code}** — {bank}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_currencies = st.multiselect(
                "Select currencies to compare",
                options=["USD"] + PRO_CURRENCIES,
                default=["USD", "EUR", "GBP", "AUD"],
                help="USD is always free; other currencies require a Professional key.",
            )
        with col2:
            selected_indicator = st.selectbox(
                "Select indicator",
                options=list(INDICATORS.keys()),
                format_func=lambda k: INDICATORS[k],
                index=0,
            )

        if not selected_currencies:
            st.warning("Please select at least one currency.")
        else:
            indicator_label = INDICATORS[selected_indicator]
            unit = INDICATOR_UNITS[selected_indicator]

            fig = go.Figure()
            colors = [
                "#1E88E5",
                "#E53935",
                "#43A047",
                "#FB8C00",
                "#7B1FA2",
                "#00897B",
                "#546E7A",
                "#F4511E",
            ]

            errors = []
            fetched: dict[str, pd.DataFrame] = {}
            for i, currency in enumerate(selected_currencies):
                curr_api_key = None if currency == "USD" else api_key
                with st.spinner(f"Loading {currency} {indicator_label}…"):
                    df, err = fetch_indicator(
                        currency,
                        selected_indicator,
                        curr_api_key,
                        start_date.isoformat(),
                        end_date.isoformat(),
                    )
                if err:
                    errors.append(f"**{currency}**: {err}")
                    continue

                fetched[currency] = df
                color = colors[i % len(colors)]
                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df["val"],
                        mode="lines",
                        name=currency,
                        line=dict(color=color, width=2),
                        hovertemplate=(
                            f"{currency} %{{x|%b %Y}}: <b>%{{y}}</b><extra></extra>"
                        ),
                    )
                )

            if errors:
                for e in errors:
                    st.warning(e)

            fig.update_layout(
                title=f"{indicator_label} — Multi-Currency Comparison",
                xaxis_title="Date",
                yaxis_title=unit or indicator_label,
                template="plotly_white",
                hovermode="x unified",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                margin=dict(l=40, r=20, t=70, b=40),
                height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Summary table — reuse already-fetched data
            st.subheader("Latest Values")
            summary_rows = []
            for currency in selected_currencies:
                df = fetched.get(currency)
                if df is None:
                    continue
                clean = df.dropna(subset=["val"])
                if clean.empty:
                    continue
                latest_row = clean.iloc[-1]
                prev_row = clean.iloc[-2] if len(clean) > 1 else None
                delta = (
                    float(latest_row["val"]) - float(prev_row["val"])
                    if prev_row is not None
                    else None
                )
                summary_rows.append(
                    {
                        "Currency": currency,
                        "Latest Date": latest_row["date"].strftime("%Y-%m-%d"),
                        f"Latest {unit or 'Value'}": round(float(latest_row["val"]), 4),
                        "Change": round(delta, 4) if delta is not None else None,
                    }
                )

            if summary_rows:
                st.dataframe(
                    pd.DataFrame(summary_rows).set_index("Currency"),
                    use_container_width=True,
                )

# ── Tab 3: About ─────────────────────────────────────────────────────────────

with tab_about:
    st.subheader("About FXMacroData")
    st.markdown(f"""
**[FXMacroData]({SITE_URL})** is a professional macroeconomic data API built for FX
traders, quantitative analysts, and algorithmic trading teams.

### What you get

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
*This example app is open-source.  Fork it, extend it, and deploy it on
[Streamlit Community Cloud](https://share.streamlit.io) for free.*
""")
