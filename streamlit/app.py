"""
FXMacroData – Central Bank Rate Monitor
========================================
A Streamlit example app demonstrating how to use the FXMacroData REST API.

Free tier:   USD announcement indicators — no API key required.
Paid plans:  Non-USD announcement indicators — require an API key.
             Get yours at https://fxmacrodata.com/api-management
"""

import base64
import datetime
import html
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://api.fxmacrodata.com"

_UTM = "utm_source=streamlit&utm_medium=integration&utm_campaign=examples&utm_content=streamlit"
SITE_URL = f"https://fxmacrodata.com/?{_UTM}"
DOCS_URL = f"https://fxmacrodata.com/documentation?{_UTM}"
API_KEYS_URL = f"https://fxmacrodata.com/api-management?{_UTM}"
SUBSCRIBE_URL = f"https://fxmacrodata.com/subscribe?{_UTM}"
SOURCE_URL = "https://github.com/fxmacrodata/examples/tree/main/streamlit"

# Currencies available with an API key (free = USD only), with their central bank.
PRO_CURRENCIES = {
    "EUR": "European Central Bank",
    "GBP": "Bank of England",
    "JPY": "Bank of Japan",
    "AUD": "Reserve Bank of Australia",
    "CAD": "Bank of Canada",
    "CHF": "Swiss National Bank",
    "NZD": "Reserve Bank of New Zealand",
    "CNY": "People's Bank of China",
    "CNH": "People's Bank of China (offshore)",
    "SEK": "Sveriges Riksbank",
    "NOK": "Norges Bank",
    "DKK": "Danmarks Nationalbank",
    "KRW": "Bank of Korea",
    "BRL": "Banco Central do Brasil",
    "HUF": "Magyar Nemzeti Bank",
    "ILS": "Bank of Israel",
    "MYR": "Bank Negara Malaysia",
    "NGN": "Central Bank of Nigeria",
    "PEN": "Banco Central de Reserva del Perú",
    "THB": "Bank of Thailand",
    "TWD": "Central Bank of the Republic of China (Taiwan)",
}

# Indicators served by /v1/announcements/{currency}/{indicator}.
#   field    – row field to plot ("val" unless the headline number is a change)
#   scale    – multiplier applied to that field
#   kind     – "step" (policy rates), "line" or "bar"
INDICATORS = {
    "policy_rate": dict(label="Policy Rate", unit="%", decimals=2, kind="step"),
    "inflation": dict(label="CPI Inflation", unit="% YoY", decimals=1, kind="line"),
    "core_inflation": dict(label="Core CPI Inflation", unit="% YoY", decimals=1, kind="line"),
    "unemployment": dict(label="Unemployment Rate", unit="%", decimals=1, kind="line"),
    "non_farm_payrolls": dict(
        label="Non-Farm Payrolls", unit="k MoM", decimals=0, kind="bar",
        field="change", scale=0.001, signed=True,
    ),
    "gdp": dict(label="Real GDP", unit="USD bn", decimals=0, kind="line"),
    "retail_sales": dict(label="Retail Sales", unit="% MoM", decimals=2, kind="bar", signed=True),
    "trade_balance": dict(
        label="Trade Balance", unit="USD bn", decimals=1, kind="bar", scale=0.001, signed=True,
    ),
}

# Indicators that share a unit across currencies, so they can be compared.
COMPARABLE_INDICATORS = ["policy_rate", "inflation", "core_inflation", "unemployment"]

MAX_PAGES = 30

PLACEHOLDER_KEY_MARKERS = ("PASTE_", "YOUR_", "REPLACE", "DUMMY", "EXAMPLE", "CHANGEME")

# FXMacroData palette: near-black grounds, dark panels, neon accents.
INK_BLACK = "#010409"
PAGE_BG = "#0d1117"
PAGE_BG_SOFT = "#050811"
SURFACE = "#161b22"
SURFACE_RAISED = "#21262d"
BORDER = "#30363d"
TEXT_STRONG = "#f0f6fc"
TEXT = "#cdd9e5"
TEXT_MUTED = "#8b949e"
CYAN = "#00e5ff"
MINT = "#00ff9c"
MAGENTA = "#ff4d9d"
AMBER = "#ffd60a"
CTA_INK = "#061014"
CHART_TICK = "#e6edf3"
CHART_GRID = "rgba(80,90,102,0.45)"
SERIES = ["#4cc2ff", MINT, MAGENTA, AMBER, "#c586c0", "#ff8a3d", CYAN, "#b5cea8"]

FONT_SANS = '"Space Grotesk", "Inter", "Segoe UI", Arial, sans-serif'
FONT_MONO = '"IBM Plex Mono", "JetBrains Mono", Consolas, monospace'


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


def _is_placeholder(key: str) -> bool:
    upper_key = key.upper()
    return any(marker in upper_key for marker in PLACEHOLDER_KEY_MARKERS)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_indicator(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
    page_size: int = 100,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch indicator data from the FXMacroData API.

    Returns (dataframe, error_message).  On success error_message is None.
    The dataframe has ``date`` (reference period), a numeric ``value``,
    ``released`` (publication time, UTC) and ``source_url``.

    Without an API key the API returns the most recent 90 days only.
    """
    spec = INDICATORS[indicator]
    headers = {"X-API-Key": api_key} if api_key else {}
    rows: list[dict] = []

    # The endpoint is paginated (100 rows per page at most), newest first.
    for page in range(MAX_PAGES):
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": page_size,
            "offset": page * page_size,
        }
        try:
            resp = requests.get(
                f"{API_BASE}/v1/announcements/{currency.lower()}/{indicator}",
                params=params,
                headers=headers,
                timeout=15,
            )
        except requests.exceptions.RequestException as exc:
            return None, f"Network error: {exc}"

        if resp.status_code == 401:
            return None, "An API key is required for this currency."
        if resp.status_code == 403:
            return None, "This API key does not have access. Check the key and try again."
        if resp.status_code == 404:
            return None, "No data found."
        if not resp.ok:
            return None, f"API error {resp.status_code}."

        payload = resp.json()
        rows.extend(payload.get("data", []))
        if not (payload.get("pagination") or {}).get("has_more"):
            break

    if not rows:
        return None, "No data returned for this period."

    df = pd.DataFrame(rows)
    field = spec.get("field", "val")
    if field not in df.columns:
        field = "val"
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df[field], errors="coerce") * spec.get("scale", 1)
    # announcement_datetime is epoch seconds (UTC): when the figure was published.
    if "announcement_datetime" in df.columns:
        df["released"] = pd.to_datetime(
            df["announcement_datetime"], unit="s", utc=True, errors="coerce"
        )
    else:
        df["released"] = pd.NaT
    if "source_url" not in df.columns:
        df["source_url"] = None
    df = df.dropna(subset=["value"]).drop_duplicates("date").sort_values("date")
    if df.empty:
        return None, "No data returned for this period."
    return df[["date", "value", "released", "source_url"]].reset_index(drop=True), None


@st.cache_data(ttl=300, show_spinner=False)
def validate_api_key(api_key: str) -> str:
    """Check an API key against a protected non-USD endpoint.

    Returns "valid", "invalid", "placeholder" or "unknown".
    """
    if _is_placeholder(api_key):
        return "placeholder"
    try:
        resp = requests.get(
            f"{API_BASE}/v1/announcements/eur/policy_rate",
            headers={"X-API-Key": api_key},
            timeout=12,
        )
    except requests.exceptions.RequestException:
        return "unknown"
    if resp.status_code == 200:
        return "valid"
    if resp.status_code in (401, 403):
        return "invalid"
    return "unknown"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_calendar(
    currency: str,
    api_key: Optional[str],
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch upcoming macro releases from the FXMacroData calendar endpoint."""
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        resp = requests.get(
            f"{API_BASE}/v1/calendar/{currency.lower()}", headers=headers, timeout=15
        )
    except requests.exceptions.RequestException as exc:
        return None, f"Network error: {exc}"

    if resp.status_code in (401, 403):
        return None, "An API key is required for this currency calendar."
    if not resp.ok:
        return None, f"Calendar API error {resp.status_code}."

    rows = resp.json().get("data", [])
    if not rows:
        return None, "No upcoming releases returned."

    df = pd.DataFrame(rows)
    # announcement_datetime is epoch seconds (UTC).
    df["when"] = pd.to_datetime(df["announcement_datetime"], unit="s", utc=True, errors="coerce")
    df = df.dropna(subset=["when"])
    df = df[df["when"] >= pd.Timestamp.now(tz="UTC")].sort_values("when")
    if df.empty:
        return None, "No upcoming releases returned."
    return df.reset_index(drop=True), None


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------


def _html(markup: str) -> None:
    """Render raw HTML. Lines are left-stripped so Markdown never sees a code block."""
    st.markdown(
        "\n".join(line.strip() for line in markup.strip().splitlines()),
        unsafe_allow_html=True,
    )


def _alert(kind: str, body: str) -> None:
    """kind: info | success | warning | danger. ``body`` is trusted HTML."""
    _html(f'<div class="fxmd-alert fxmd-alert--{kind}">{body}</div>')


def _link(label: str, url: str) -> str:
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'


def _fmt(value: float, spec: dict, signed: Optional[bool] = None) -> str:
    signed = spec.get("signed", False) if signed is None else signed
    return f"{value:{'+' if signed else ''},.{spec['decimals']}f}"


def _period(ts: pd.Timestamp) -> str:
    return ts.strftime("%b %Y")


def _base_layout(title: str, unit: str, height: int) -> dict:
    axis = dict(
        gridcolor=CHART_GRID,
        linecolor=BORDER,
        zerolinecolor="rgba(120,132,148,0.7)",
        tickfont=dict(family=FONT_MONO, size=11, color=CHART_TICK),
        title_font=dict(family=FONT_MONO, size=11, color=TEXT_MUTED),
    )
    return dict(
        title=dict(
            text=f"{title}<span style='color:{TEXT_MUTED};font-size:12px'>  {unit}</span>",
            font=dict(family=FONT_SANS, size=15, color=TEXT_STRONG),
            x=0, xref="paper", y=0.95, yanchor="top", pad=dict(l=2),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_SANS, color=TEXT),
        xaxis=dict(**axis, showgrid=False),
        yaxis=dict(**axis, side="right"),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=SURFACE_RAISED, bordercolor=BORDER,
            font=dict(family=FONT_MONO, size=12, color=TEXT_STRONG),
        ),
        margin=dict(l=16, r=12, t=52, b=28),
        height=height,
        showlegend=False,
    )


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _plot_series(df: pd.DataFrame, indicator: str, color: str, height: int = 300) -> go.Figure:
    spec = INDICATORS[indicator]
    hover = f"%{{y:,.{spec['decimals']}f}}<extra></extra>"
    fig = go.Figure()
    if spec["kind"] == "bar":
        fig.add_trace(
            go.Bar(
                x=df["date"], y=df["value"],
                marker=dict(
                    color=[MINT if v >= 0 else MAGENTA for v in df["value"]],
                    line=dict(width=0),
                ),
                hovertemplate=hover,
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["value"], mode="lines",
                line=dict(color=color, width=2, shape="hv" if spec["kind"] == "step" else "linear"),
                fill="tozeroy" if spec["kind"] == "step" else None,
                fillcolor=_rgba(color, 0.08),
                hovertemplate=hover,
            )
        )
    fig.update_layout(**_base_layout(spec["label"], spec["unit"], height))
    fig.update_xaxes(hoverformat="%b %Y")
    return fig


def _chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def _stat_card(indicator: str, df: Optional[pd.DataFrame]) -> str:
    spec = INDICATORS[indicator]
    if df is None or df.empty:
        return (
            f'<div class="fxmd-stat"><span class="fxmd-label">{spec["label"]}</span>'
            '<span class="fxmd-stat-value">n/a</span>'
            '<span class="fxmd-stat-note">Temporarily unavailable</span></div>'
        )
    latest = df.iloc[-1]
    note = _period(latest["date"])
    if len(df) > 1:
        note += f' · prior {_fmt(df.iloc[-2]["value"], spec)}'
    return (
        f'<div class="fxmd-stat"><span class="fxmd-label">{spec["label"]}</span>'
        f'<span class="fxmd-stat-value">{_fmt(latest["value"], spec)}'
        f'<small>{spec["unit"]}</small></span>'
        f'<span class="fxmd-stat-note">{note}</span></div>'
    )


def _logo_data_uri() -> str:
    logo = Path(__file__).parent / "assets" / "fxmacrodata-logo.svg"
    try:
        return "data:image/svg+xml;base64," + base64.b64encode(logo.read_bytes()).decode()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Page config and theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Central Bank Rate Monitor – FXMacroData",
    page_icon=str(Path(__file__).parent / "assets" / "fxmacrodata-icon.svg"),
    layout="wide",
    initial_sidebar_state="auto",
)

_html(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@400..700&display=swap');

    :root {{ color-scheme: dark; }}
    html, body, .stApp, .stApp [data-testid="stMarkdownContainer"], .stApp p, .stApp li,
    .stApp label, .stApp button, .stApp input {{
        font-family: {FONT_SANS};
    }}
    .stApp {{
        background:
            radial-gradient(circle at 72% 0%, rgba(0,229,255,0.07), transparent 32%),
            linear-gradient(115deg, {PAGE_BG_SOFT} 0%, #08111d 42%, #07101b 66%, {INK_BLACK} 100%);
        background-attachment: fixed;
        color: {TEXT};
    }}
    [data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stHeader"] *, [data-testid="stToolbar"] * {{ color: {TEXT_MUTED}; }}
    [data-testid="stMainBlockContainer"], .block-container {{
        padding-top: 2.75rem; padding-bottom: 3rem; max-width: 1280px;
    }}
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
        font-family: {FONT_SANS}; color: {TEXT_STRONG}; letter-spacing: 0;
    }}
    .stApp a {{ color: {CYAN}; text-decoration: none; }}
    .stApp a:hover {{ text-decoration: underline; }}
    .stApp a:focus-visible, .stApp button:focus-visible {{ outline: 2px solid {CYAN}; outline-offset: 2px; }}
    hr {{ border-color: {BORDER} !important; }}

    /* Sidebar */
    [data-testid="stSidebar"] {{ background: {PAGE_BG}; border-right: 1px solid {BORDER}; }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{ color: {TEXT}; }}
    .fxmd-logo {{ display: block; width: 190px; height: auto; margin: 0 0 14px; }}
    .fxmd-side-note {{ color: {TEXT_MUTED}; font-size: 13px; line-height: 1.5; margin: 0 0 6px; }}
    .fxmd-side-links {{ display: grid; gap: 10px; font-size: 14px; }}

    /* Labels, chips, buttons */
    .fxmd-label {{
        display: block; font-family: {FONT_MONO}; font-size: 12px; font-weight: 600;
        letter-spacing: 0.14em; text-transform: uppercase; color: {MINT}; line-height: 1.3;
    }}
    .fxmd-chip {{
        display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px;
        border-radius: 999px; font-size: 12px; font-weight: 700; line-height: 1.2;
        border: 1px solid rgba(0,229,255,0.36); background: rgba(0,229,255,0.10); color: #d8fffb;
    }}
    .fxmd-chip--live {{ border-color: rgba(0,255,156,0.45); background: rgba(0,255,156,0.12); color: #8fffd2; }}
    .fxmd-chip--amber {{ border-color: rgba(255,214,10,0.45); background: rgba(255,214,10,0.10); color: {AMBER}; }}
    .fxmd-dot {{ width: 8px; height: 8px; border-radius: 50%; background: {MINT}; box-shadow: 0 0 10px {MINT}; }}
    .stApp a.fxmd-btn {{
        display: inline-flex; align-items: center; justify-content: center; height: 44px;
        padding: 0 20px; border-radius: 8px; font-size: 16px; font-weight: 700;
        text-decoration: none; border: 1px solid rgba(0,229,255,0.36);
        background: {SURFACE}; color: {TEXT_STRONG};
    }}
    .stApp a.fxmd-btn:hover {{ background: {SURFACE_RAISED}; text-decoration: none; }}
    .stApp a.fxmd-btn--primary, .stApp a.fxmd-btn--primary:visited {{
        border: 0; color: {CTA_INK}; background: linear-gradient(90deg, {CYAN}, {MINT});
        box-shadow: 0 14px 34px rgba(0,229,255,0.26), inset 0 0 0 1px rgba(0,255,156,0.45);
    }}
    .stApp a.fxmd-btn--primary:hover {{
        color: {CTA_INK}; background: linear-gradient(90deg, {MINT}, {CYAN});
        box-shadow: 0 18px 42px rgba(0,255,156,0.24), inset 0 0 0 1px rgba(0,229,255,0.52);
    }}

    /* Hero */
    .fxmd-hero {{
        position: relative; overflow: hidden; border: 1px solid {BORDER}; border-radius: 8px;
        padding: 28px 28px 26px; margin-bottom: 14px;
        background:
            radial-gradient(circle at 82% 20%, rgba(0,229,255,0.14), transparent 34%),
            linear-gradient(180deg, rgba(22,27,34,0.96), rgba(13,17,23,0.94));
        box-shadow: 0 24px 64px rgba(0,0,0,0.42);
    }}
    .fxmd-hero::before {{
        content: ""; position: absolute; inset: 0; pointer-events: none; opacity: 0.055;
        background-image:
            linear-gradient({CYAN} 1px, transparent 1px),
            linear-gradient(90deg, {CYAN} 1px, transparent 1px);
        background-size: 56px 56px;
        -webkit-mask-image: linear-gradient(180deg, #000, transparent);
        mask-image: linear-gradient(180deg, #000, transparent);
    }}
    .fxmd-hero > * {{ position: relative; }}
    .stApp .fxmd-hero h1 {{
        margin: 10px 0 0; padding: 0; font-size: clamp(32px, 4.4vw, 52px);
        line-height: 0.98; font-weight: 700;
    }}
    .stApp .fxmd-hero p {{ margin: 14px 0 0; max-width: 62ch; font-size: 18px; line-height: 1.55; color: {TEXT}; }}
    .fxmd-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}

    /* Stat cards */
    .fxmd-stats {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); margin-bottom: 8px; }}
    .fxmd-stat, .fxmd-panel {{
        border: 1px solid {BORDER}; border-radius: 8px; padding: 18px;
        background: linear-gradient(180deg, rgba(22,27,34,0.96), rgba(13,17,23,0.94));
    }}
    .fxmd-stat-value {{
        display: block; margin-top: 10px; font-family: {FONT_MONO}; font-size: 30px;
        font-weight: 600; line-height: 1.1; color: {TEXT_STRONG};
    }}
    .fxmd-stat-value small {{ margin-left: 8px; font-size: 13px; font-weight: 400; color: {TEXT_MUTED}; }}
    .fxmd-stat-note {{ display: block; margin-top: 8px; font-family: {FONT_MONO}; font-size: 12px; color: {TEXT_MUTED}; }}

    /* Section heads */
    .fxmd-section {{ margin: 22px 0 12px; }}
    .stApp .fxmd-section h2 {{ margin: 6px 0 0; padding: 0; font-size: 22px; line-height: 1.15; font-weight: 700; }}
    .stApp .fxmd-section p {{ margin: 6px 0 0; font-size: 14px; color: {TEXT_MUTED}; }}

    /* Chart panels */
    [data-testid="stPlotlyChart"] {{
        border: 1px solid {BORDER}; border-radius: 8px; overflow: hidden;
        background: linear-gradient(180deg, rgba(22,27,34,0.96), rgba(13,17,23,0.94));
    }}

    /* Alerts */
    .fxmd-alert {{
        border: 1px solid {BORDER}; border-left: 3px solid {CYAN}; border-radius: 8px;
        padding: 12px 14px; margin: 0 0 12px; background: {SURFACE};
        font-size: 14px; line-height: 1.5; color: {TEXT};
    }}
    .fxmd-alert strong {{ color: {TEXT_STRONG}; }}
    .fxmd-alert--success {{ border-left-color: {MINT}; }}
    .fxmd-alert--warning {{ border-left-color: {AMBER}; }}
    .fxmd-alert--danger {{ border-left-color: {MAGENTA}; }}

    /* Tables */
    .fxmd-table-wrap {{ border: 1px solid {BORDER}; border-radius: 8px; overflow-x: auto; background: {PAGE_BG}; }}
    table.fxmd-table {{ width: 100%; border-collapse: collapse; margin: 0; }}
    .fxmd-table th {{
        padding: 11px 16px; text-align: left; white-space: nowrap; background: {SURFACE};
        font-family: {FONT_MONO}; font-size: 11px; font-weight: 400; letter-spacing: 0.12em;
        text-transform: uppercase; color: {TEXT_MUTED}; border: 0; border-bottom: 1px solid {BORDER};
    }}
    .fxmd-table td {{
        padding: 11px 16px; font-size: 14px; color: {TEXT}; border: 0;
        border-bottom: 1px solid rgba(48,54,61,0.6); white-space: nowrap;
    }}
    .fxmd-table tr:last-child td {{ border-bottom: 0; }}
    .fxmd-table td.num, .fxmd-table th.num {{ text-align: right; }}
    .fxmd-table td.num, .fxmd-table td.mono {{ font-family: {FONT_MONO}; font-size: 13px; color: {TEXT_STRONG}; }}
    .fxmd-table td.cyan {{ color: {CYAN}; }}
    .fxmd-table td.muted {{ color: {TEXT_MUTED}; }}
    .fxmd-table td.up {{ color: {MINT}; }}
    .fxmd-table td.down {{ color: {MAGENTA}; }}
    .fxmd-table .unit {{ margin-left: 6px; font-family: {FONT_MONO}; font-size: 11px; color: {TEXT_MUTED}; }}
    .fxmd-cta-panel {{
        display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
        gap: 18px; margin-top: 14px; border-color: rgba(0,229,255,0.36);
    }}
    .fxmd-cta-panel > div:first-child {{ flex: 1 1 380px; }}
    .fxmd-cta-panel .fxmd-row {{ margin-top: 0; }}
    .stApp .fxmd-cta-panel h3 {{ margin: 8px 0 0; padding: 0; font-size: 20px; line-height: 1.2; font-weight: 700; }}
    .stApp .fxmd-cta-panel p {{ margin: 8px 0 0; max-width: 68ch; font-size: 14px; line-height: 1.55; color: {TEXT}; }}
    .fxmd-table .yes {{ color: {MINT}; }}
    .fxmd-table .no {{ color: {TEXT_MUTED}; }}
    .fxmd-tag {{
        display: inline-block; padding: 2px 8px; border-radius: 999px; font-family: {FONT_MONO};
        font-size: 11px; border: 1px solid {BORDER}; color: {TEXT_MUTED};
    }}
    .fxmd-tag--high {{ border-color: rgba(255,214,10,0.45); color: {AMBER}; background: rgba(255,214,10,0.10); }}

    /* Central bank grid */
    .fxmd-banks {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }}
    .fxmd-bank {{
        display: flex; align-items: baseline; gap: 12px; padding: 12px 14px;
        border: 1px solid {BORDER}; border-radius: 8px; background: {SURFACE};
    }}
    .fxmd-bank b {{ font-family: {FONT_MONO}; font-size: 13px; font-weight: 600; color: {CYAN}; }}
    .fxmd-bank span {{ font-size: 13px; color: {TEXT}; }}

    /* Streamlit widgets */
    [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid {BORDER}; }}
    [data-baseweb="tab-border"] {{ background-color: transparent !important; }}
    [data-baseweb="tab-highlight"] {{ background-color: {CYAN} !important; }}
    button[data-baseweb="tab"] {{ padding: 0 14px; height: 44px; }}
    button[data-baseweb="tab"] p {{ font-size: 14px; font-weight: 700; color: {TEXT_MUTED}; }}
    button[data-baseweb="tab"]:hover p {{ color: {TEXT}; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ color: {TEXT_STRONG}; }}
    [data-testid="stWidgetLabel"] p {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
    [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div {{
        background-color: {INK_BLACK} !important; border-color: {BORDER} !important; border-radius: 8px !important;
    }}
    [data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
        border-color: rgba(0,229,255,0.64) !important; box-shadow: 0 0 0 3px rgba(0,229,255,0.13);
    }}
    [data-testid="stTextInput"] input {{
        background-color: transparent !important; color: {TEXT_STRONG} !important;
        font-family: {FONT_MONO}; font-size: 13px; caret-color: {CYAN};
    }}
    [data-testid="stTextInput"] input::placeholder {{ color: {TEXT_MUTED}; opacity: 1; }}
    [data-testid="stTextInput"] button {{ background: transparent !important; color: {TEXT_MUTED} !important; }}
    [data-baseweb="tag"] {{
        background-color: rgba(0,229,255,0.10) !important; border: 1px solid rgba(0,229,255,0.36);
        border-radius: 999px !important;
    }}
    [data-baseweb="tag"] span, [data-baseweb="tag"] svg {{ color: #d8fffb !important; fill: #d8fffb !important; }}
    [data-testid="stSlider"] [data-testid="stSliderThumbValue"],
    [data-testid="stSlider"] [data-testid="stTickBarMin"],
    [data-testid="stSlider"] [data-testid="stTickBarMax"] {{ font-family: {FONT_MONO}; color: {TEXT} !important; }}

    @media (max-width: 640px) {{
        .fxmd-hero {{ padding: 20px 16px; }}
        .stApp .fxmd-hero p {{ font-size: 16px; }}
        .stApp a.fxmd-btn {{ width: 100%; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
    </style>
    """
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    logo_uri = _logo_data_uri()
    logo_html = (
        f'<img class="fxmd-logo" src="{logo_uri}" alt="FXMacroData">' if logo_uri else "FXMacroData"
    )
    _html(
        f"""
        <a href="{SITE_URL}" target="_blank" rel="noopener" aria-label="FXMacroData">{logo_html}</a>
        <p class="fxmd-side-note">Macro and FX data API, sourced from central banks and
        official statistical agencies.</p>
        """
    )
    st.divider()

    # A key configured by the app owner stays server-side: it is never placed in
    # the input box, where any visitor could reveal it.
    try:
        owner_key = str(st.secrets.get("FXMACRODATA_API_KEY", "") or "")
    except Exception:  # no secrets file configured
        owner_key = ""
    owner_key = (owner_key or os.getenv("FXMACRODATA_API_KEY", "")).strip()
    if owner_key and _is_placeholder(owner_key):
        owner_key = ""

    _html('<span class="fxmd-label">API key</span>')
    api_key_input = st.text_input(
        "API key",
        type="password",
        placeholder="Paste your API key",
        label_visibility="collapsed",
        help="USD data needs no key. A key unlocks the other 21 currencies.",
    )
    api_key_candidate = api_key_input.strip() or owner_key
    api_key: Optional[str] = None

    if not api_key_candidate:
        _alert(
            "info",
            f"USD data needs no key. {_link('Get an API key', API_KEYS_URL)} to compare "
            "the other 21 currencies.",
        )
    else:
        status = validate_api_key(api_key_candidate)
        if status == "valid":
            api_key = api_key_candidate
            _alert("success", "<strong>Key accepted.</strong> All 22 currencies unlocked.")
        elif status == "placeholder":
            _alert("warning", "That looks like placeholder text, not an API key.")
        elif status == "invalid":
            _alert(
                "danger",
                f"This key was not accepted. Check it under {_link('API Management', API_KEYS_URL)}.",
            )
        else:
            api_key = api_key_candidate
            _alert("info", "Key entered. It could not be checked just now.")

    st.divider()
    _html('<span class="fxmd-label">History</span>')
    if api_key:
        years_back = st.slider("Years of history", min_value=1, max_value=10, value=5)
    else:
        years_back = 1
        _html(
            '<p class="fxmd-side-note">Without a key the API returns the most recent '
            "90 days. Add a key to chart up to 10 years.</p>"
        )
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=years_back * 365)

    st.divider()
    _html(
        f"""
        <div class="fxmd-side-links">
        {_link('API Documentation', DOCS_URL)}
        {_link('Get API Key', API_KEYS_URL)}
        {_link('Plans and Pricing', SUBSCRIBE_URL)}
        {_link('App Source on GitHub', SOURCE_URL)}
        </div>
        """
    )

start_iso, end_iso = start_date.isoformat(), end_date.isoformat()

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

_html(
    f"""
    <section class="fxmd-hero">
    <span class="fxmd-label">FXMacroData example app</span>
    <h1>Central Bank Rate Monitor</h1>
    <p>Policy rates, inflation, labour and growth data for 22 currencies, read straight
    from the FXMacroData API. USD is open to everyone; an API key adds the rest.</p>
    <div class="fxmd-row">
    <span class="fxmd-chip fxmd-chip--live"><span class="fxmd-dot"></span>USD data free</span>
    <span class="fxmd-chip">22 currencies with a key</span>
    <span class="fxmd-chip fxmd-chip--amber">Official sources only</span>
    </div>
    <div class="fxmd-row">
    <a class="fxmd-btn fxmd-btn--primary" href="{API_KEYS_URL}" target="_blank" rel="noopener">Get API Key</a>
    <a class="fxmd-btn" href="{DOCS_URL}" target="_blank" rel="noopener">Read the Docs</a>
    </div>
    </section>
    """
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_usd, tab_multi, tab_about = st.tabs(["USD Dashboard", "Multi-Currency", "About"])

# ── Tab 1: USD Dashboard (free) ──────────────────────────────────────────────

with tab_usd:
    usd_keys = [
        "policy_rate", "inflation", "unemployment", "non_farm_payrolls",
        "core_inflation", "gdp", "retail_sales", "trade_balance",
    ]
    usd: dict[str, Optional[pd.DataFrame]] = {}
    usd_errors: dict[str, str] = {}
    with st.spinner("Loading USD indicators…"):
        for key in usd_keys:
            usd[key], err = fetch_indicator("USD", key, api_key, start_iso, end_iso)
            if err:
                usd_errors[key] = err

    access_note = (
        "Full history with your API key."
        if api_key
        else "No API key needed. Keyless requests return the most recent 90 days, "
        "15 minutes after publication."
    )
    _html(
        f"""
        <div class="fxmd-section">
        <span class="fxmd-label">United States</span>
        <h2>Latest readings</h2>
        <p>Federal Reserve, BLS, BEA and Census Bureau releases. {access_note}</p>
        </div>
        """
    )
    headline = ["policy_rate", "inflation", "unemployment", "non_farm_payrolls"]
    _html('<div class="fxmd-stats">' + "".join(_stat_card(k, usd[k]) for k in headline) + "</div>")

    if api_key:
        chart_colors = {
            "policy_rate": SERIES[0], "inflation": SERIES[3], "unemployment": SERIES[5],
            "non_farm_payrolls": SERIES[1], "core_inflation": SERIES[4], "gdp": SERIES[6],
            "retail_sales": SERIES[1], "trade_balance": SERIES[1],
        }
        _html(
            f"""
            <div class="fxmd-section">
            <span class="fxmd-label">History</span>
            <h2>{years_back}-year view</h2>
            </div>
            """
        )
        for left, right in zip(usd_keys[0::2], usd_keys[1::2]):
            row = st.columns(2)
            for col, key in zip(row, (left, right)):
                with col:
                    if usd[key] is None:
                        _alert(
                            "warning",
                            f"<strong>{INDICATORS[key]['label']}</strong>: {usd_errors[key]}",
                        )
                    else:
                        _chart(_plot_series(usd[key], key, chart_colors[key]))
    else:
        body = []
        for key in usd_keys:
            df = usd[key]
            if df is None:
                continue
            spec = INDICATORS[key]
            latest = df.iloc[-1]
            prior, change, change_cls = "–", "–", "num"
            if len(df) > 1:
                prior = _fmt(df.iloc[-2]["value"], spec)
                diff = latest["value"] - df.iloc[-2]["value"]
                change = _fmt(diff, spec, signed=True) if diff else "unch"
                change_cls = "num up" if diff > 0 else "num down" if diff < 0 else "num"
            released = (
                latest["released"].strftime("%d %b %Y %H:%M")
                if pd.notna(latest["released"])
                else "–"
            )
            source = (
                _link("Source", html.escape(str(latest["source_url"]), quote=True))
                if latest["source_url"]
                else ""
            )
            body.append(
                f'<tr><td>{spec["label"]} <span class="unit">{spec["unit"]}</span></td>'
                f'<td class="mono">{_period(latest["date"])}</td>'
                f'<td class="num">{_fmt(latest["value"], spec)}</td>'
                f'<td class="num muted">{prior}</td>'
                f'<td class="{change_cls}">{change}</td>'
                f'<td class="mono">{released}</td><td>{source}</td></tr>'
            )
        _html(
            """
            <div class="fxmd-section">
            <span class="fxmd-label">Announcements</span>
            <h2>Recent USD releases</h2>
            <p>The latest published figure for each indicator, with its release time in UTC
            and a link to the publishing agency.</p>
            </div>
            <div class="fxmd-table-wrap"><table class="fxmd-table"><thead><tr>
            <th>Indicator</th><th>Period</th><th class="num">Latest</th>
            <th class="num">Prior</th><th class="num">Change</th>
            <th>Released (UTC)</th><th>Publisher</th>
            </tr></thead><tbody>"""
            + "".join(body)
            + "</tbody></table></div>"
        )
        _html(
            f"""
            <div class="fxmd-panel fxmd-cta-panel">
            <div>
            <span class="fxmd-label">Full history</span>
            <h3>Chart every release, not just the last 90 days</h3>
            <p>Keyless access covers the most recent 90 days. With an API key this tab
            charts up to 10 years of each indicator, and the Multi-Currency tab opens
            the other 21 currencies. The Individual plan is USD 50/month with a 14-day
            free trial.</p>
            </div>
            <div class="fxmd-row">
            <a class="fxmd-btn fxmd-btn--primary" href="{SUBSCRIBE_URL}" target="_blank" rel="noopener">Start Free Trial</a>
            <a class="fxmd-btn" href="{API_KEYS_URL}" target="_blank" rel="noopener">Get API Key</a>
            </div>
            </div>
            """
        )

    _html(
        """
        <div class="fxmd-section">
        <span class="fxmd-label">Release calendar</span>
        <h2>Upcoming USD releases</h2>
        <p>Scheduled times from the official release calendars, shown in UTC.</p>
        </div>
        """
    )
    with st.spinner("Loading USD release calendar…"):
        calendar_df, calendar_err = fetch_calendar("USD", None)

    if calendar_err or calendar_df is None:
        _alert("info", calendar_err or "No upcoming releases returned.")
    else:
        body = []
        for _, event in calendar_df.head(10).iterrows():
            name = event.get("name") or str(event.get("release", "")).replace("_", " ").title()
            importance = str(event.get("event_importance") or "").lower()
            tag_cls = "fxmd-tag fxmd-tag--high" if importance == "high" else "fxmd-tag"
            tag = f'<span class="{tag_cls}">{html.escape(importance)}</span>' if importance else ""
            body.append(
                f'<tr><td class="mono cyan">{event["when"].strftime("%a %d %b %Y")}</td>'
                f'<td class="mono">{event["when"].strftime("%H:%M")}</td>'
                f"<td>{html.escape(str(name))}</td>"
                f'<td class="mono">{html.escape(str(event.get("release", "")))}</td>'
                f"<td>{tag}</td></tr>"
            )
        _html(
            '<div class="fxmd-table-wrap"><table class="fxmd-table"><thead><tr>'
            "<th>Date</th><th>UTC</th><th>Release</th><th>Indicator</th><th>Importance</th>"
            "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
        )

# ── Tab 2: Multi-Currency (API key) ──────────────────────────────────────────

with tab_multi:
    if not api_key:
        _html(
            f"""
            <div class="fxmd-section">
            <span class="fxmd-label">API key required</span>
            <h2>Compare 22 central banks side by side</h2>
            <p>Paste an API key in the sidebar to chart policy rates, inflation and
            unemployment across every covered currency.</p>
            </div>
            <div class="fxmd-row" style="margin:0 0 20px">
            <a class="fxmd-btn fxmd-btn--primary" href="{SUBSCRIBE_URL}" target="_blank" rel="noopener">Start Free Trial</a>
            <a class="fxmd-btn" href="{API_KEYS_URL}" target="_blank" rel="noopener">Get API Key</a>
            </div>
            <div class="fxmd-banks">
            """
            + "".join(
                f'<div class="fxmd-bank"><b>{code}</b><span>{html.escape(bank)}</span></div>'
                for code, bank in PRO_CURRENCIES.items()
            )
            + "</div>"
        )
    else:
        _html(
            """
            <div class="fxmd-section">
            <span class="fxmd-label">Cross-currency</span>
            <h2>Multi-currency comparison</h2>
            </div>
            """
        )
        col1, col2 = st.columns([3, 2])
        with col1:
            selected_currencies = st.multiselect(
                "Currencies",
                options=["USD", *PRO_CURRENCIES],
                default=["USD", "EUR", "GBP", "AUD"],
                max_selections=len(SERIES),
            )
        with col2:
            selected_indicator = st.selectbox(
                "Indicator",
                options=COMPARABLE_INDICATORS,
                format_func=lambda k: INDICATORS[k]["label"],
            )

        if not selected_currencies:
            _alert("warning", "Select at least one currency.")
        else:
            spec = INDICATORS[selected_indicator]
            fetched: dict[str, pd.DataFrame] = {}
            with st.spinner(f"Loading {spec['label']}…"):
                for currency in selected_currencies:
                    df, err = fetch_indicator(
                        currency,
                        selected_indicator,
                        None if currency == "USD" else api_key,
                        start_iso,
                        end_iso,
                    )
                    if err:
                        _alert("warning", f"<strong>{currency}</strong>: {err}")
                    else:
                        fetched[currency] = df

            if fetched:
                fig = go.Figure()
                for i, (currency, df) in enumerate(fetched.items()):
                    fig.add_trace(
                        go.Scatter(
                            x=df["date"], y=df["value"], mode="lines", name=currency,
                            line=dict(
                                color=SERIES[i % len(SERIES)], width=2,
                                shape="hv" if spec["kind"] == "step" else "linear",
                            ),
                            hovertemplate=f"%{{y:,.{spec['decimals']}f}}",
                        )
                    )
                fig.update_layout(**_base_layout(spec["label"], spec["unit"], 460))
                fig.update_layout(
                    showlegend=True,
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                        font=dict(family=FONT_MONO, size=12, color=TEXT),
                    ),
                )
                fig.update_xaxes(hoverformat="%b %Y")
                _chart(fig)

                ranked = sorted(
                    fetched.items(), key=lambda item: item[1].iloc[-1]["value"], reverse=True
                )
                body = []
                for currency, df in ranked:
                    latest = df.iloc[-1]
                    change = (
                        _fmt(latest["value"] - df.iloc[-2]["value"], spec, signed=True)
                        if len(df) > 1
                        else "–"
                    )
                    bank = "Federal Reserve" if currency == "USD" else PRO_CURRENCIES[currency]
                    body.append(
                        f'<tr><td class="mono cyan">{currency}</td><td>{html.escape(bank)}</td>'
                        f'<td class="mono">{_period(latest["date"])}</td>'
                        f'<td class="num">{_fmt(latest["value"], spec)}</td>'
                        f'<td class="num">{change}</td></tr>'
                    )
                _html(
                    f"""
                    <div class="fxmd-section">
                    <span class="fxmd-label">Ranked high to low</span>
                    <h2>Latest values</h2>
                    </div>
                    <div class="fxmd-table-wrap"><table class="fxmd-table"><thead><tr>
                    <th>Currency</th><th>Central bank</th><th>Period</th>
                    <th class="num">{spec['label']} ({spec['unit']})</th>
                    <th class="num">Change</th>
                    </tr></thead><tbody>{''.join(body)}</tbody></table></div>
                    """
                )

# ── Tab 3: About ─────────────────────────────────────────────────────────────

with tab_about:
    yes, no = '<span class="yes">Included</span>', '<span class="no">Not included</span>'
    _html(
        f"""
        <div class="fxmd-section">
        <span class="fxmd-label">About</span>
        <h2>Built on the FXMacroData API</h2>
        <p>{_link('FXMacroData', SITE_URL)} serves macroeconomic releases, policy rates,
        release calendars, FX rates, COT positioning and commodity prices for 22 currencies,
        each row traced to the central bank or statistical agency that published it.</p>
        </div>
        <div class="fxmd-table-wrap"><table class="fxmd-table"><thead><tr>
        <th>Feature</th><th>Free</th><th>Individual</th>
        </tr></thead><tbody>
        <tr><td>USD indicators and release calendar</td><td>{yes}</td><td>{yes}</td></tr>
        <tr><td>History</td><td>Latest 90 days</td><td>Full history</td></tr>
        <tr><td>Releases without the 15-minute delay</td><td>{no}</td><td>{yes}</td></tr>
        <tr><td>Indicators for all 22 currencies</td><td>{no}</td><td>{yes}</td></tr>
        <tr><td>FX rates, COT positioning, commodities</td><td>{no}</td><td>{yes}</td></tr>
        <tr><td>Price</td><td class="mono">USD 0</td><td class="mono">USD 50/month</td></tr>
        </tbody></table></div>
        <div class="fxmd-row" style="margin-bottom:22px">
        <a class="fxmd-btn fxmd-btn--primary" href="{SUBSCRIBE_URL}" target="_blank" rel="noopener">Start Free Trial</a>
        <a class="fxmd-btn" href="{DOCS_URL}" target="_blank" rel="noopener">Read the Docs</a>
        <a class="fxmd-btn" href="{SOURCE_URL}" target="_blank" rel="noopener">View App Source</a>
        </div>
        <div class="fxmd-panel">
        <span class="fxmd-label">Run it yourself</span>
        <p style="margin:10px 0 0;color:{TEXT}">This app is open source. Fork it, change the
        indicators, and deploy it on Streamlit Community Cloud. Every figure on the USD tab is
        one keyless GET request to <code>api.fxmacrodata.com/v1/announcements/usd/&lt;indicator&gt;</code>.</p>
        </div>
        """
    )
