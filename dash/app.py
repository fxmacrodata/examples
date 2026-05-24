"""
FXMacroData – FX Macro Heatmap
===============================
A Plotly Dash example app that visualises macroeconomic indicator momentum
across currencies as a colour-coded heatmap, powered by the FXMacroData
REST API.

Free tier  : USD row — no API key required.
Pro tier   : Full 18-currency grid — requires a Professional API key.
             Get yours at https://fxmacrodata.com/api-management

Run locally
-----------
    pip install -r requirements.txt
    python app.py
    # then open http://localhost:8050

Deploy to Render (free tier)
-----------------------------
    # Start command: gunicorn app:server
    # See README.md for full deploy steps.
"""

import datetime
import os
import time
from typing import Optional

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, State, dcc, html, no_update

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

# (key, display label, unit suffix)
INDICATORS = [
    ("policy_rate", "Policy Rate", "%"),
    ("inflation", "Inflation", "% YoY"),
    ("gdp", "GDP", "% YoY"),
    ("unemployment", "Unemployment", "%"),
    ("pmi", "PMI", ""),
    ("retail_sales", "Retail Sales", "% MoM"),
    ("trade_balance", "Trade Balance", ""),
]

# Indicators where a lower reading is better (inverts green/red)
LOWER_BETTER = {"unemployment"}

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

_CACHE_TTL = 300  # seconds — 5-minute server-side in-memory cache

# ─── In-memory request cache ──────────────────────────────────────────────────

_cache: dict = {}


def _cache_get(key: str) -> Optional[tuple]:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
        return entry[1], entry[2]
    return None


def _cache_put(key: str, df: Optional[pd.DataFrame], status: str) -> None:
    _cache[key] = (time.monotonic(), df, status)


# ─── API helpers ──────────────────────────────────────────────────────────────


def fetch_indicator(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], str]:
    """Fetch indicator time-series data from the FXMacroData REST API.

    Returns ``(df, status)`` where ``status`` is ``"ok"`` on success or one
    of ``"auth_required"``, ``"invalid_key"``, ``"no_data"``, ``"api_error"``,
    or ``"network_error"`` on failure.
    """
    cache_key = f"{currency}|{indicator}|{api_key or ''}|{start_date}|{end_date}"
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
            timeout=8,
        )
    except requests.exceptions.RequestException:
        return None, "network_error"

    if resp.status_code == 401:
        _cache_put(cache_key, None, "auth_required")
        return None, "auth_required"
    if resp.status_code == 403:
        return None, "invalid_key"
    if resp.status_code == 404:
        _cache_put(cache_key, None, "no_data")
        return None, "no_data"
    if not resp.ok:
        return None, "api_error"

    rows = resp.json().get("data", [])
    if not rows:
        _cache_put(cache_key, None, "no_data")
        return None, "no_data"

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    _cache_put(cache_key, df, "ok")
    return df, "ok"


def momentum_score(df: pd.DataFrame, indicator_key: str) -> Optional[float]:
    """Return a momentum score in ``[-1, +1]``.

    Compares the most recent reading to the previous one, normalised to a
    ``-1..+1`` scale.  Positive values mean the indicator is improving;
    negative values mean it is deteriorating.  Unemployment is inverted
    (a fall in unemployment is positive for the economy).
    """
    clean = df.dropna(subset=["val"])
    if len(clean) < 2:
        return None
    last = float(clean.iloc[-1]["val"])
    prev = float(clean.iloc[-2]["val"])
    delta = last - prev
    scale = max(abs(last), abs(prev), 0.01)  # 0.01 floor prevents instability near zero
    score = delta / scale
    if indicator_key in LOWER_BETTER:
        score = -score
    return max(-1.0, min(1.0, score))


def _date_range(years: int) -> tuple[str, str]:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=years * 365)
    return start.isoformat(), end.isoformat()


# ─── App setup ────────────────────────────────────────────────────────────────

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="FX Macro Heatmap – FXMacroData",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
)
server = app.server  # WSGI entry-point for gunicorn / Render

# ─── Layout ───────────────────────────────────────────────────────────────────

_NAVBAR = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                dbc.NavbarBrand(
                    [
                        html.Img(
                            src="https://fxmacrodata.com/static/logos/logo-fxmacrodata.png",
                            height="32px",
                            className="me-2",
                        ),
                        "FX Macro Heatmap",
                    ],
                    className="fw-bold text-white",
                ),
                href=SITE_URL,
                target="_blank",
                className="text-decoration-none",
            ),
            dbc.Nav(
                [
                    dbc.NavItem(
                        dbc.NavLink(
                            "📖 Docs",
                            href=DOCS_URL,
                            target="_blank",
                            className="text-white-50",
                        )
                    ),
                    dbc.NavItem(
                        dbc.NavLink(
                            "🔑 API Key",
                            href=API_KEYS_URL,
                            target="_blank",
                            className="text-white-50",
                        )
                    ),
                ],
                navbar=True,
                className="ms-auto",
            ),
        ],
        fluid=True,
    ),
    color="dark",
    dark=True,
    className="mb-4",
)

_API_KEY_ROW = dbc.Card(
    dbc.CardBody(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Span("🔑 ", className="fs-5"),
                        html.Strong("API Key"),
                        html.Span(
                            " — USD data is always free",
                            className="text-muted ms-1 small",
                        ),
                    ],
                    width="auto",
                    className="d-flex align-items-center",
                ),
                dbc.Col(
                    dbc.Input(
                        id="api-key-input",
                        type="password",
                        placeholder="Paste your Professional API key to unlock protected non-USD announcements…",
                        debounce=True,
                        size="sm",
                    ),
                ),
                dbc.Col(
                    dbc.Button(
                        "Apply", id="apply-btn", color="primary", size="sm", n_clicks=0
                    ),
                    width="auto",
                ),
                dbc.Col(
                    html.Div(id="api-key-badge"),
                    width="auto",
                    className="d-flex align-items-center",
                ),
            ],
            align="center",
            className="g-2",
        ),
    ),
    className="mb-4 shadow-sm",
)

_SETTINGS_ROW = dbc.Row(
    [
        dbc.Col(
            [
                html.Label("History (years)", className="fw-semibold mb-1 small"),
                dcc.Slider(
                    id="years-slider",
                    min=1,
                    max=10,
                    step=1,
                    value=5,
                    marks={i: str(i) for i in range(1, 11)},
                    tooltip={"placement": "bottom"},
                ),
            ],
            md=6,
        ),
        dbc.Col(
            dbc.Button(
                "🔄 Refresh",
                id="refresh-btn",
                color="secondary",
                outline=True,
                size="sm",
                n_clicks=0,
            ),
            md=6,
            className="d-flex align-items-end justify-content-end pb-1",
        ),
    ],
    className="mb-4",
)

_ABOUT_CONTENT = dbc.Row(
    dbc.Col(
        [
            html.H5("About FXMacroData"),
            html.P(
                [
                    html.A("FXMacroData", href=SITE_URL, target="_blank"),
                    " is a professional macroeconomic data API built for FX traders, "
                    "quantitative analysts, and systematic trading teams.",
                ]
            ),
            html.H6("What's included"),
            dbc.ListGroup(
                [
                    dbc.ListGroupItem(
                        "📊 40+ indicators per currency — inflation, GDP, unemployment, policy rates, PMI, retail sales, and more"
                    ),
                    dbc.ListGroupItem(
                        "🏦 18 currencies — USD, EUR, GBP, AUD, JPY, CAD, CHF, NZD, CNY, HKD, SGD, KRW, NOK, SEK, DKK, PLN, BRL, MXN"
                    ),
                    dbc.ListGroupItem(
                        "⚡ Low-latency REST API — clean JSON, no pre-processing required"
                    ),
                    dbc.ListGroupItem(
                        "🗓️ Release calendars — know exactly when the next data drop lands"
                    ),
                    dbc.ListGroupItem(
                        "📈 COT positioning — CFTC Commitment of Traders for FX futures"
                    ),
                    dbc.ListGroupItem(
                        "💎 Precious metals — daily gold, silver, and platinum spot prices"
                    ),
                ],
                flush=True,
                className="mb-4",
            ),
            html.H6("Free vs Professional"),
            dbc.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Feature"),
                                html.Th("Free"),
                                html.Th("Professional"),
                            ]
                        )
                    ),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td("USD macro indicators"),
                                    html.Td("✅"),
                                    html.Td("✅"),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("All 18 currency indicators"),
                                    html.Td("❌"),
                                    html.Td("✅"),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("COT positioning data"),
                                    html.Td("❌"),
                                    html.Td("✅"),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Release calendars"),
                                    html.Td("❌"),
                                    html.Td("✅"),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Commercial use"),
                                    html.Td("❌"),
                                    html.Td("✅"),
                                ]
                            ),
                            html.Tr(
                                [html.Td("Price"), html.Td("$0"), html.Td("$25/month")]
                            ),
                        ]
                    ),
                ],
                bordered=True,
                striped=True,
                size="sm",
                className="mb-4",
            ),
            html.H6("Links"),
            html.Ul(
                [
                    html.Li(
                        html.A("🌐 FXMacroData Website", href=SITE_URL, target="_blank")
                    ),
                    html.Li(
                        html.A("📖 API Documentation", href=DOCS_URL, target="_blank")
                    ),
                    html.Li(
                        html.A(
                            "🔑 Get your API key", href=API_KEYS_URL, target="_blank"
                        )
                    ),
                ]
            ),
            html.P(
                html.Em(
                    "This example app is open-source — fork it and deploy it on "
                    "Render for free. See the README for deploy steps."
                ),
                className="text-muted small",
            ),
        ],
        md=8,
    ),
)

app.layout = dbc.Container(
    [
        _NAVBAR,
        _API_KEY_ROW,
        _SETTINGS_ROW,
        # ── Tabs ──────────────────────────────────────────────────────────────
        dbc.Tabs(
            [
                # Tab 1 – Macro Heatmap
                dbc.Tab(
                    [
                        html.H5("Macro Momentum Heatmap", className="mb-1 mt-3"),
                        html.P(
                            [
                                "Each cell shows the latest reading and colour-codes the recent trend ",
                                html.Strong("(green = improving, red = deteriorating)"),
                                ". Click any cell to see the full time series below.",
                            ],
                            className="text-muted small mb-3",
                        ),
                        html.Div(id="heatmap-alert"),
                        dcc.Loading(
                            dcc.Graph(
                                id="heatmap-graph",
                                config={"displayModeBar": False},
                                style={"minHeight": "280px"},
                            ),
                            type="circle",
                        ),
                        html.Div(id="heatmap-detail", className="mt-3"),
                    ],
                    label="🌡️ Macro Heatmap",
                    tab_id="heatmap",
                ),
                # Tab 2 – Deep Dive
                dbc.Tab(
                    [
                        html.H5("Deep Dive", className="mb-2 mt-3"),
                        html.P(
                            "Select a currency to see all its macro indicators laid out in a grid.",
                            className="text-muted small mb-3",
                        ),
                        dbc.Row(
                            dbc.Col(
                                dcc.Dropdown(
                                    id="deepdive-currency",
                                    options=[
                                        {
                                            "label": f"{CURRENCY_FLAGS.get(c, '')} {c}",
                                            "value": c,
                                        }
                                        for c in ALL_CURRENCIES
                                    ],
                                    value=FREE_CURRENCY,
                                    clearable=False,
                                ),
                                md=4,
                            ),
                            className="mb-4",
                        ),
                        dcc.Loading(
                            html.Div(id="deepdive-charts"),
                            type="circle",
                        ),
                    ],
                    label="📊 Deep Dive",
                    tab_id="deepdive",
                ),
                # Tab 3 – About (static)
                dbc.Tab(
                    _ABOUT_CONTENT,
                    label="ℹ️ About",
                    tab_id="about",
                    className="mt-3",
                ),
            ],
            id="tabs",
            active_tab="heatmap",
        ),
        # Stores
        # Seed the store from the FXMACRODATA_API_KEY env var (useful for Render/HF Spaces)
        dcc.Store(id="api-key-store", data=os.getenv("FXMACRODATA_API_KEY") or None),
    ],
    fluid=True,
)

# ─── Callbacks ────────────────────────────────────────────────────────────────


@app.callback(
    Output("api-key-store", "data"),
    Output("api-key-badge", "children"),
    Input("apply-btn", "n_clicks"),
    Input("api-key-input", "n_submit"),
    State("api-key-input", "value"),
    prevent_initial_call=True,
)
def store_api_key(_n_clicks, _n_submit, value: Optional[str]):
    """Save the API key in a session store and show a status badge."""
    key = (value or "").strip() or None
    badge = (
        dbc.Badge("✅ Key applied", color="success")
        if key
        else dbc.Badge("No key — USD only", color="secondary")
    )
    return key, badge


@app.callback(
    Output("heatmap-graph", "figure"),
    Output("heatmap-alert", "children"),
    Input("api-key-store", "data"),
    Input("years-slider", "value"),
    Input("refresh-btn", "n_clicks"),
)
def update_heatmap(api_key: Optional[str], years: int, _refresh: int):
    """Rebuild the macro momentum heatmap whenever the API key or date range changes."""
    currencies = ALL_CURRENCIES if api_key else [FREE_CURRENCY]
    start, end = _date_range(years)

    ind_labels = [label for _, label, _ in INDICATORS]
    z_data: list = []
    text_data: list = []

    for currency in currencies:
        curr_key = None if currency == FREE_CURRENCY else api_key
        z_row: list = []
        text_row: list = []

        for ind_key, _, ind_unit in INDICATORS:
            df, status = fetch_indicator(currency, ind_key, curr_key, start, end)

            if status == "ok" and df is not None:
                score = momentum_score(df, ind_key)
                clean = df.dropna(subset=["val"])
                latest = float(clean.iloc[-1]["val"]) if not clean.empty else None

                z_row.append(score if score is not None else 0.0)
                if latest is not None:
                    suffix = f" {ind_unit}" if ind_unit else ""
                    text_row.append(f"{latest:.2f}{suffix}")
                else:
                    text_row.append("—")

            elif status == "auth_required":
                z_row.append(None)
                text_row.append("🔒")

            else:
                z_row.append(None)
                text_row.append("—")

        z_data.append(z_row)
        text_data.append(text_row)

    y_labels = [f"{CURRENCY_FLAGS.get(c, '')} {c}" for c in currencies]

    fig = go.Figure(
        go.Heatmap(
            z=z_data,
            x=ind_labels,
            y=y_labels,
            text=text_data,
            texttemplate="<b>%{text}</b>",
            colorscale=[
                [0.00, "#dc2626"],
                [0.35, "#fca5a5"],
                [0.50, "#f9fafb"],
                [0.65, "#86efac"],
                [1.00, "#16a34a"],
            ],
            zmid=0,
            zmin=-1,
            zmax=1,
            colorbar=dict(
                title=dict(text="Momentum", side="right"),
                tickvals=[-1, 0, 1],
                ticktext=["Falling", "Stable", "Rising"],
                lenmode="fraction",
                len=0.8,
            ),
            hovertemplate=("<b>%{y}</b> — %{x}<br>" "Latest: %{text}<extra></extra>"),
        )
    )

    fig.update_layout(
        height=max(350, 64 * len(currencies) + 140),
        xaxis=dict(side="top", tickfont=dict(size=11)),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        margin=dict(l=90, r=110, t=90, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    alert = None
    if not api_key:
        alert = dbc.Alert(
            [
                "🔒 ",
                html.Strong("Showing USD only. "),
                "Enter a ",
                html.A("Professional API key", href=API_KEYS_URL, target="_blank"),
                " above to load data for all 18 currencies.",
            ],
            color="info",
            className="mb-3",
        )

    return fig, alert


@app.callback(
    Output("heatmap-detail", "children"),
    Input("heatmap-graph", "clickData"),
    State("api-key-store", "data"),
    State("years-slider", "value"),
    prevent_initial_call=True,
)
def on_heatmap_click(click_data, api_key: Optional[str], years: int):
    """Show a time-series chart for whichever heatmap cell the user clicked."""
    if not click_data:
        return no_update

    point = click_data["points"][0]
    y_label = point.get("y", "")  # e.g. "🇺🇸 USD"
    x_label = point.get("x", "")  # e.g. "Inflation"

    # Extract the 3-letter currency code from the y label
    currency = y_label.split()[-1] if y_label else None

    # Map display label back to API key
    indicator_key = None
    indicator_unit = ""
    for k, label, unit in INDICATORS:
        if label == x_label:
            indicator_key = k
            indicator_unit = unit
            break

    if not currency or not indicator_key:
        return no_update

    start, end = _date_range(years)
    curr_key = None if currency == FREE_CURRENCY else api_key
    df, status = fetch_indicator(currency, indicator_key, curr_key, start, end)

    if status != "ok" or df is None:
        msg = {
            "auth_required": f"A Professional API key is needed to view {currency} data.",
            "no_data": f"No data available for {currency} — {x_label}.",
            "invalid_key": "Invalid API key. Please check and try again.",
        }.get(status, f"Could not load {currency} — {x_label}.")
        return dbc.Alert(msg, color="warning", dismissable=True)

    clean = df.dropna(subset=["val"])
    flag = CURRENCY_FLAGS.get(currency, "")

    fig = go.Figure(
        go.Scatter(
            x=clean["date"],
            y=clean["val"],
            mode="lines+markers",
            line=dict(color="#0891b2", width=2),
            marker=dict(size=5),
            name=f"{currency} {x_label}",
            hovertemplate="%{x|%b %Y}: <b>%{y}</b><extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{flag} {currency} — {x_label}",
        xaxis_title="Date",
        yaxis_title=indicator_unit or x_label,
        template="plotly_white",
        hovermode="x unified",
        height=320,
        margin=dict(l=60, r=20, t=50, b=40),
    )

    return html.Div(
        [
            html.Hr(),
            html.H6(f"Time Series: {flag} {currency} — {x_label}", className="mb-2"),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ]
    )


@app.callback(
    Output("deepdive-charts", "children"),
    Input("deepdive-currency", "value"),
    Input("api-key-store", "data"),
    Input("years-slider", "value"),
    Input("refresh-btn", "n_clicks"),
)
def update_deepdive(
    currency: Optional[str], api_key: Optional[str], years: int, _refresh: int
):
    """Render a 2-column sparkline grid for every indicator of the selected currency."""
    if not currency:
        return dbc.Alert("Please select a currency.", color="info")

    start, end = _date_range(years)
    curr_key = None if currency == FREE_CURRENCY else api_key
    flag = CURRENCY_FLAGS.get(currency, "")
    rows = []

    for i in range(0, len(INDICATORS), 2):
        pair = INDICATORS[i : i + 2]
        cols = []

        for ind_key, ind_label, ind_unit in pair:
            df, status = fetch_indicator(currency, ind_key, curr_key, start, end)

            if status == "ok" and df is not None:
                clean = df.dropna(subset=["val"])
                title = ind_label + (f" ({ind_unit})" if ind_unit else "")
                fig = go.Figure(
                    go.Scatter(
                        x=clean["date"],
                        y=clean["val"],
                        mode="lines",
                        fill="tozeroy",
                        line=dict(color="#0891b2", width=1.5),
                        fillcolor="rgba(8, 145, 178, 0.1)",
                        hovertemplate="%{x|%b %Y}: <b>%{y}</b><extra></extra>",
                    )
                )
                fig.update_layout(
                    title=title,
                    template="plotly_white",
                    hovermode="x unified",
                    height=240,
                    margin=dict(l=50, r=10, t=40, b=30),
                    showlegend=False,
                )
                cols.append(
                    dbc.Col(
                        dcc.Graph(figure=fig, config={"displayModeBar": False}), md=6
                    )
                )

            elif status == "auth_required":
                cols.append(
                    dbc.Col(
                        dbc.Alert(
                            [
                                "🔒 ",
                                html.A(
                                    "Professional key required",
                                    href=API_KEYS_URL,
                                    target="_blank",
                                ),
                                f" to view {flag} {currency} — {ind_label}.",
                            ],
                            color="secondary",
                            className="h-100",
                        ),
                        md=6,
                    )
                )

            else:
                cols.append(
                    dbc.Col(
                        dbc.Alert(f"No data available for {ind_label}.", color="light"),
                        md=6,
                    )
                )

        rows.append(dbc.Row(cols, className="mb-3"))

    return html.Div(rows)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
