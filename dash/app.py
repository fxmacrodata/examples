"""
FXMacroData - Policy Divergence Studio (Dash)
==============================================

This Dash example focuses on one practical workflow:
compare macro policy divergence between two countries and map the trend.

Purpose (distinct from heatmap tools):
- Build a two-country macro spread dashboard
- Track regime shifts with spread trend and volatility
- Generate a short human-readable narrative from live data
"""

from __future__ import annotations

import datetime as dt
import os
import time
from typing import Optional

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, State, dash_table, dcc, html

API_BASE = "https://fxmacrodata.com/api/v1"
API_MANAGEMENT_URL = "https://fxmacrodata.com/api-management"
DOCS_URL = "https://fxmacrodata.com/documentation"

FREE_CURRENCY = "USD"
FREE_PAIR_DEFAULT = "USD / USD"
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

INDICATORS = [
    ("policy_rate", "Policy Rate", "%"),
    ("inflation", "Inflation", "% YoY"),
    ("unemployment", "Unemployment", "%"),
    ("pmi", "PMI", ""),
]

LOWER_BETTER = {"unemployment"}

DEFAULT_A = "USD"
DEFAULT_B = "USD"
DEFAULT_INDICATOR = "policy_rate"
DEFAULT_YEARS = 5

_CACHE_TTL_SECONDS = 300
_cache: dict[str, tuple[float, Optional[pd.DataFrame], str]] = {}


def _cache_get(key: str) -> Optional[tuple[Optional[pd.DataFrame], str]]:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1], entry[2]
    return None


def _cache_put(key: str, df: Optional[pd.DataFrame], status: str) -> None:
    _cache[key] = (time.monotonic(), df, status)


def _date_range(years: int) -> tuple[str, str]:
    end = dt.date.today()
    start = end - dt.timedelta(days=365 * years)
    return start.isoformat(), end.isoformat()


def _status_message(currency: str, status: str) -> str:
    if status == "auth_required":
        return (
            f"{currency} data requires a Professional API key. "
            f"Add one here: {API_MANAGEMENT_URL}"
        )
    if status == "invalid_key":
        return f"Invalid API key for {currency}."
    if status == "no_data":
        return f"No data returned for {currency} in the selected range."
    if status == "network_error":
        return "Network error while contacting FXMacroData API."
    if status == "api_error":
        return "Unexpected API error."
    return "Unknown error."


def fetch_series(
    currency: str,
    indicator: str,
    api_key: Optional[str],
    start_date: str,
    end_date: str,
) -> tuple[Optional[pd.DataFrame], str]:
    cache_key = f"{currency}|{indicator}|{api_key or ''}|{start_date}|{end_date}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params: dict[str, str] = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    try:
        response = requests.get(
            f"{API_BASE}/announcements/{currency.lower()}/{indicator}",
            params=params,
            timeout=10,
        )
    except requests.exceptions.RequestException:
        return None, "network_error"

    if response.status_code == 401:
        _cache_put(cache_key, None, "auth_required")
        return None, "auth_required"
    if response.status_code == 403:
        return None, "invalid_key"
    if response.status_code == 404:
        _cache_put(cache_key, None, "no_data")
        return None, "no_data"
    if not response.ok:
        return None, "api_error"

    records = response.json().get("data", [])
    if not records:
        _cache_put(cache_key, None, "no_data")
        return None, "no_data"

    frame = pd.DataFrame(records)
    if "date" not in frame.columns or "val" not in frame.columns:
        return None, "api_error"

    frame["date"] = pd.to_datetime(frame["date"])
    frame["val"] = pd.to_numeric(frame["val"], errors="coerce")
    frame = frame.dropna(subset=["val"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        _cache_put(cache_key, None, "no_data")
        return None, "no_data"

    _cache_put(cache_key, frame, "ok")
    return frame, "ok"


def build_spread_frame(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(df_a[["date", "val"]], df_b[["date", "val"]], on="date", how="inner", suffixes=("_a", "_b"))
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["spread"] = merged["val_a"] - merged["val_b"]
    return merged


def format_metric(value: float, unit: str) -> str:
    if unit:
        return f"{value:.2f} {unit}"
    return f"{value:.2f}"


def blank_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=360,
        margin=dict(l=30, r=20, t=58, b=34),
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="Run analysis to generate this chart",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14, color="#cbd5e1"),
            )
        ],
    )
    return fig


def series_figure(df: pd.DataFrame, label_a: str, label_b: str, indicator_label: str, unit: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val_a"],
            mode="lines+markers",
            name=label_a,
            line=dict(color="#38bdf8", width=3.5),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(56, 189, 248, 0.08)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val_b"],
            mode="lines+markers",
            name=label_b,
            line=dict(color="#34d399", width=3.5),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(52, 211, 153, 0.08)",
        )
    )
    fig.update_layout(
        title=f"{indicator_label}: {label_a} vs {label_b}",
        template="plotly_dark",
        height=380,
        margin=dict(l=40, r=24, t=58, b=40),
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        legend=dict(orientation="h", y=1.09, x=0, bgcolor="rgba(7,17,31,0.1)"),
        xaxis=dict(title="Date", gridcolor="rgba(148,163,184,0.14)", zeroline=False),
        yaxis=dict(title=f"Value ({unit})" if unit else "Value", gridcolor="rgba(148,163,184,0.14)", zeroline=False),
    )
    return fig


def spread_figure(df: pd.DataFrame, label_a: str, label_b: str, indicator_label: str) -> go.Figure:
    spread_color = "#f59e0b"
    fig = go.Figure(
        data=[
            go.Scatter(
                x=df["date"],
                y=df["spread"],
                mode="lines",
                name=f"{label_a} - {label_b}",
                line=dict(color=spread_color, width=3),
                fill="tozeroy",
                fillcolor="rgba(245, 158, 11, 0.18)",
            )
        ]
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#334155", line_width=1.2)
    fig.update_layout(
        title=f"Spread Trend ({indicator_label})",
        template="plotly_dark",
        height=340,
        margin=dict(l=40, r=24, t=58, b=40),
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        xaxis=dict(title="Date", gridcolor="rgba(148,163,184,0.14)", zeroline=False),
        yaxis=dict(title="Spread", gridcolor="rgba(148,163,184,0.14)", zeroline=False),
    )
    return fig


def auto_prompt(currency_a: str, currency_b: str, indicator: str) -> str:
    if currency_a == FREE_CURRENCY and currency_b == FREE_CURRENCY:
        return "Auto-loaded in free mode. Select a Professional key and switch Country B to compare non-USD indicators."
    if currency_a == currency_b:
        return "Both sides are set to the same currency, so the spread is zero. Choose a different Country B to compare divergence."
    indicator_label = next((label for key, label, _ in INDICATORS if key == indicator), indicator)
    return f"Auto-loaded with {indicator_label} for {currency_a} vs {currency_b}."


def build_scoreboard(currency_a: str, currency_b: str, api_key: Optional[str], years: int) -> list[dict]:
    start, end = _date_range(years)
    rows: list[dict] = []
    for indicator_key, indicator_label, _unit in INDICATORS:
        key_a = api_key if currency_a != FREE_CURRENCY else None
        key_b = api_key if currency_b != FREE_CURRENCY else None
        df_a, status_a = fetch_series(currency_a, indicator_key, key_a, start, end)
        df_b, status_b = fetch_series(currency_b, indicator_key, key_b, start, end)

        if status_a != "ok" or status_b != "ok" or df_a is None or df_b is None:
            rows.append(
                {
                    "indicator": indicator_label,
                    f"{currency_a}": "-",
                    f"{currency_b}": "-",
                    "spread": "n/a",
                    "signal": "Data unavailable",
                }
            )
            continue

        last_a = float(df_a.iloc[-1]["val"])
        last_b = float(df_b.iloc[-1]["val"])
        spread = last_a - last_b

        if indicator_key in LOWER_BETTER:
            signal = f"{currency_a} stronger" if spread < 0 else f"{currency_b} stronger"
        else:
            signal = f"{currency_a} stronger" if spread > 0 else f"{currency_b} stronger"

        rows.append(
            {
                "indicator": indicator_label,
                f"{currency_a}": f"{last_a:.2f}",
                f"{currency_b}": f"{last_b:.2f}",
                "spread": f"{spread:+.2f}",
                "signal": signal,
            }
        )

    return rows


app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="FXMacroData Policy Divergence Studio",
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {
            "name": "description",
            "content": (
                "Policy Divergence Studio for comparing macro paths between two countries "
                "using FXMacroData indicator endpoints."
            ),
        },
        {"name": "robots", "content": "index,follow"},
    ],
)
server = app.server

seed_api_key = os.getenv("FXMACRODATA_API_KEY", "").strip()

app.layout = dbc.Container(
    fluid=True,
    style={
        "minHeight": "100vh",
        "background": "radial-gradient(circle at 12% 8%, #07111f 0%, #050b14 46%, #03060c 100%)",
        "padding": "20px 16px 40px",
        "fontFamily": "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
        "color": "#e5eefb",
    },
    children=[
        html.Style(
            """
            .dash-card {
                border: 1px solid rgba(148,163,184,0.16) !important;
                border-radius: 18px !important;
                background: linear-gradient(180deg, rgba(15,23,42,0.88) 0%, rgba(8,15,28,0.92) 100%) !important;
                box-shadow: 0 18px 44px rgba(0,0,0,0.28) !important;
            }
            .dash-section-title {
                margin: 0;
                font-size: 0.78rem;
                letter-spacing: 0.16em;
                text-transform: uppercase;
                color: #86b8ff;
                font-weight: 700;
            }
            .dash-section-copy {
                margin: 6px 0 0;
                color: #cbd5e1;
                font-size: 0.96rem;
            }
            .dash-chip {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: #d7e7ff;
                background: rgba(59,130,246,0.12);
                border: 1px solid rgba(59,130,246,0.24);
            }
            .dash-chip-green {
                background: rgba(16,185,129,0.12);
                border-color: rgba(16,185,129,0.25);
                color: #c6f6e5;
            }
            .dash-chip-amber {
                background: rgba(245,158,11,0.12);
                border-color: rgba(245,158,11,0.25);
                color: #fde68a;
            }
            .summary-card {
                border-radius: 18px !important;
                background: linear-gradient(180deg, rgba(14,23,39,0.92) 0%, rgba(10,17,31,0.96) 100%) !important;
                border: 1px solid rgba(148,163,184,0.14) !important;
                box-shadow: 0 14px 30px rgba(0,0,0,0.18) !important;
            }
            .summary-label {
                font-size: 0.72rem;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: #8ea6c7;
                margin-bottom: 6px;
            }
            .summary-value {
                margin: 0;
                color: #f8fafc;
                font-size: 1.45rem;
                font-weight: 800;
            }
            .summary-note {
                margin-top: 5px;
                color: #93c5fd;
                font-size: 0.84rem;
            }
            .control-label {
                color: #dbe8ff;
                font-weight: 700;
                letter-spacing: 0.02em;
            }
            .dash-table .dash-spreadsheet-container .dash-spreadsheet-inner table {
                border-radius: 16px;
                overflow: hidden;
            }
            """
        ),
        dbc.Container(
            style={"maxWidth": "1240px"},
            children=[
                html.Div(
                    style={
                        "background": "linear-gradient(120deg, #08111f 0%, #112b4d 48%, #0e5a63 100%)",
                        "borderRadius": "22px",
                        "padding": "26px 24px",
                        "color": "#f8fafc",
                        "boxShadow": "0 22px 52px rgba(2, 6, 23, 0.48)",
                        "marginBottom": "18px",
                    },
                    children=[
                        html.Div(
                            [
                                html.Span("FXMacroData Dash Example", className="dash-chip dash-chip-green"),
                                html.Span("Auto-loaded", className="dash-chip"),
                                html.Span("USD free mode", className="dash-chip dash-chip-amber"),
                            ],
                            style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "14px"},
                        ),
                        html.H1(
                            "Policy Divergence Studio",
                            style={"margin": "0 0 8px", "fontSize": "clamp(2rem, 4vw, 3rem)", "fontWeight": 900, "letterSpacing": "-0.03em"},
                        ),
                        html.P(
                            "A trading-desk view of macro divergence. Compare two countries, trace spread momentum, and read the regime in one glance.",
                            style={"margin": 0, "fontSize": "1.04rem", "maxWidth": "920px", "opacity": 0.92, "color": "#d8e6ff"},
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3 mb-3",
                    children=[
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody([
                                    html.Div("Live mode", className="summary-label"),
                                    html.H3("Auto-refresh", className="summary-value"),
                                    html.Div("Charts render on load and on every control change.", className="summary-note"),
                                ]),
                                className="summary-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody([
                                    html.Div("Coverage", className="summary-label"),
                                    html.H3("18 currencies", className="summary-value"),
                                    html.Div("USD free, non-USD with API key.", className="summary-note"),
                                ]),
                                className="summary-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody([
                                    html.Div("Workflow", className="summary-label"),
                                    html.H3("Spread + narrative", className="summary-value"),
                                    html.Div("Useful for quickly spotting divergence regimes.", className="summary-note"),
                                ]),
                                className="summary-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody([
                                    html.Div("Latency", className="summary-label"),
                                    html.H3("Cached 5 min", className="summary-value"),
                                    html.Div("Keeps the page responsive while you explore.", className="summary-note"),
                                ]),
                                className="summary-card",
                            ),
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3",
                    children=[
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Country A", className="control-label mb-1"),
                                        dcc.Dropdown(ALL_CURRENCIES, DEFAULT_A, id="currency-a", clearable=False, className="dash-control"),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Country B", className="control-label mb-1"),
                                        dcc.Dropdown(ALL_CURRENCIES, DEFAULT_B, id="currency-b", clearable=False, className="dash-control"),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Indicator", className="control-label mb-1"),
                                        dcc.Dropdown(
                                            [{"label": label, "value": key} for key, label, _ in INDICATORS],
                                            DEFAULT_INDICATOR,
                                            id="indicator",
                                            clearable=False,
                                            className="dash-control",
                                        ),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Lookback", className="control-label mb-1"),
                                        dcc.Dropdown(
                                            options=[
                                                {"label": "2 years", "value": 2},
                                                {"label": "3 years", "value": 3},
                                                {"label": "5 years", "value": 5},
                                                {"label": "10 years", "value": 10},
                                            ],
                                            value=DEFAULT_YEARS,
                                            id="lookback-years",
                                            clearable=False,
                                            className="dash-control",
                                        ),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                    ],
                ),
                dbc.Row(
                    className="g-3 mt-1 align-items-end",
                    children=[
                        dbc.Col(
                            md=8,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div(className="d-flex justify-content-between align-items-center mb-2", children=[
                                            html.Label("Professional API key (optional for USD)", className="control-label mb-0"),
                                            html.A("Get key", href=API_MANAGEMENT_URL, target="_blank", style={"fontSize": "0.88rem", "color": "#93c5fd"}),
                                        ]),
                                        dcc.Input(
                                            id="api-key",
                                            type="password",
                                            value=seed_api_key,
                                            placeholder="rnd_...",
                                            style={
                                                "width": "100%",
                                                "padding": "11px 12px",
                                                "borderRadius": "10px",
                                                "border": "1px solid rgba(148,163,184,0.32)",
                                                "background": "rgba(2,6,23,0.92)",
                                                "color": "#f8fafc",
                                                "fontFamily": "monospace",
                                            },
                                        ),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                        dbc.Col(
                            md=4,
                            children=dbc.Button(
                                "Refresh Analysis",
                                id="run-btn",
                                n_clicks=0,
                                className="w-100",
                                style={
                                    "height": "54px",
                                    "fontWeight": 700,
                                    "borderRadius": "12px",
                                    "border": "none",
                                    "background": "linear-gradient(90deg, #38bdf8 0%, #14b8a6 100%)",
                                    "color": "#04111f",
                                    "boxShadow": "0 14px 30px rgba(20,184,166,0.24)",
                                },
                            ),
                        ),
                    ],
                ),
                html.Div(id="status-box", style={"marginTop": "14px"}),
                html.Div(
                    auto_prompt(DEFAULT_A, DEFAULT_B, DEFAULT_INDICATOR),
                    style={
                        "marginTop": "10px",
                        "padding": "12px 14px",
                        "borderRadius": "12px",
                        "background": "rgba(8, 15, 28, 0.76)",
                        "border": "1px solid rgba(148,163,184,0.18)",
                        "color": "#dbeafe",
                        "fontSize": "0.93rem",
                    },
                ),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("Current spread", className="summary-label"), html.H3("-", id="metric-spread", className="summary-value"), html.Div("Latest spread across the overlap window.", className="summary-note")]), className="summary-card")),
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("3-point trend", className="summary-label"), html.H3("-", id="metric-trend", className="summary-value"), html.Div("Slope of the most recent spread samples.", className="summary-note")]), className="summary-card")),
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("Spread volatility", className="summary-label"), html.H3("-", id="metric-vol", className="summary-value"), html.Div("Std dev of the spread over the selected range.", className="summary-note")]), className="summary-card")),
                    ],
                ),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(md=7, children=dbc.Card(dbc.CardBody([html.Div([html.Div("Country comparison", className="dash-section-title"), html.P("Two-country series with shared time axis and a filled trend treatment.", className="dash-section-copy")], className="mb-2"), dcc.Graph(id="series-chart", figure=blank_figure("Country comparison"), config={"displayModeBar": False})]), className="dash-card")),
                        dbc.Col(md=5, children=dbc.Card(dbc.CardBody([html.Div([html.Div("Spread trend", className="dash-section-title"), html.P("The divergence line, shaded for quick regime scanning.", className="dash-section-copy")], className="mb-2"), dcc.Graph(id="spread-chart", figure=blank_figure("Spread trend"), config={"displayModeBar": False})]), className="dash-card")),
                    ],
                ),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(
                            md=8,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div([html.Div("Cross-Indicator Scoreboard", className="dash-section-title"), html.P("A terminal-style quick read across policy, inflation, unemployment, and PMI.", className="dash-section-copy")], className="mb-3"),
                                        dash_table.DataTable(
                                            id="scoreboard",
                                            columns=[],
                                            data=[],
                                            style_header={
                                                "backgroundColor": "#08111f",
                                                "color": "#e5eefb",
                                                "fontWeight": "700",
                                                "border": "1px solid rgba(148,163,184,0.16)",
                                            },
                                            style_cell={
                                                "padding": "9px",
                                                "fontSize": "13px",
                                                "border": "1px solid rgba(148,163,184,0.12)",
                                                "backgroundColor": "#0a1322",
                                                "color": "#dbeafe",
                                            },
                                            style_data={"backgroundColor": "#0a1322", "color": "#dbeafe"},
                                            style_table={"overflowX": "auto"},
                                            style_data_conditional=[
                                                {"if": {"filter_query": '{signal} contains "stronger"'}, "color": "#86efac", "fontWeight": "700"},
                                                {"if": {"filter_query": '{signal} contains "Data unavailable"'}, "color": "#fbbf24"},
                                            ],
                                        ),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                        dbc.Col(
                            md=4,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Div([html.Div("Narrative", className="dash-section-title"), html.P("One-line read for traders who want the gist fast.", className="dash-section-copy")], className="mb-3"),
                                        html.Div(id="narrative", style={"lineHeight": "1.6", "color": "#dbeafe", "fontSize": "0.98rem"}),
                                        html.Hr(),
                                        html.P("Documentation", className="mb-1 fw-semibold", style={"color": "#cbd5e1"}),
                                        html.A("API docs", href=DOCS_URL, target="_blank", style={"color": "#7dd3fc"}),
                                    ]
                                ),
                                className="dash-card",
                            ),
                        ),
                    ],
                ),
            ],
        )
    ],
)


@app.callback(
    Output("status-box", "children"),
    Output("metric-spread", "children"),
    Output("metric-trend", "children"),
    Output("metric-vol", "children"),
    Output("series-chart", "figure"),
    Output("spread-chart", "figure"),
    Output("scoreboard", "columns"),
    Output("scoreboard", "data"),
    Output("narrative", "children"),
    Input("run-btn", "n_clicks"),
    Input("currency-a", "value"),
    Input("currency-b", "value"),
    Input("indicator", "value"),
    Input("lookback-years", "value"),
    Input("api-key", "value"),
)
def run_analysis(
    _n_clicks: int,
    currency_a: str,
    currency_b: str,
    indicator: str,
    years: int,
    api_key: Optional[str],
):
    indicator_label, indicator_unit = next((label, unit) for key, label, unit in INDICATORS if key == indicator)
    start_date, end_date = _date_range(int(years))
    clean_key = (api_key or "").strip() or None

    key_a = clean_key if currency_a != FREE_CURRENCY else None
    key_b = clean_key if currency_b != FREE_CURRENCY else None

    df_a, status_a = fetch_series(currency_a, indicator, key_a, start_date, end_date)
    if status_a != "ok" or df_a is None:
        msg = _status_message(currency_a, status_a)
        alert = dbc.Alert(msg, color="warning", className="mb-0")
        return alert, "-", "-", "-", blank_figure("Country comparison"), blank_figure("Spread trend"), [], [], msg

    df_b, status_b = fetch_series(currency_b, indicator, key_b, start_date, end_date)
    if status_b != "ok" or df_b is None:
        msg = _status_message(currency_b, status_b)
        alert = dbc.Alert(msg, color="warning", className="mb-0")
        return alert, "-", "-", "-", blank_figure("Country comparison"), blank_figure("Spread trend"), [], [], msg

    spread_df = build_spread_frame(df_a, df_b)
    if spread_df.empty:
        msg = "No overlapping dates between the selected countries for this indicator."
        alert = dbc.Alert(msg, color="warning", className="mb-0")
        return alert, "-", "-", "-", blank_figure("Country comparison"), blank_figure("Spread trend"), [], [], msg

    last_spread = float(spread_df.iloc[-1]["spread"])
    last_n = spread_df.tail(3)
    trend = float(last_n.iloc[-1]["spread"] - last_n.iloc[0]["spread"]) if len(last_n) >= 2 else 0.0
    volatility = float(spread_df["spread"].std() or 0.0)

    series_fig = series_figure(spread_df, currency_a, currency_b, indicator_label, indicator_unit)
    spread_fig = spread_figure(spread_df, currency_a, currency_b, indicator_label)

    scoreboard_rows = build_scoreboard(currency_a, currency_b, clean_key, int(years))
    columns = [
        {"name": "Indicator", "id": "indicator"},
        {"name": currency_a, "id": currency_a},
        {"name": currency_b, "id": currency_b},
        {"name": "Spread", "id": "spread"},
        {"name": "Signal", "id": "signal"},
    ]

    direction = "widening" if trend > 0 else "narrowing"
    if indicator in LOWER_BETTER:
        leader = currency_a if last_spread < 0 else currency_b
    else:
        leader = currency_a if last_spread > 0 else currency_b

    narrative = (
        f"{indicator_label} spread currently favors {leader}. "
        f"The spread is {direction} over the most recent observations, "
        f"with volatility around {volatility:.2f}."
    )

    alert = dbc.Alert(
        f"Loaded {indicator_label} for {currency_a} and {currency_b} from {start_date} to {end_date}.",
        color="success",
        className="mb-0",
    )

    prompt_box = html.Div(
        auto_prompt(currency_a, currency_b, indicator),
        style={
            "marginBottom": "12px",
            "padding": "10px 12px",
            "borderRadius": "12px",
            "background": "linear-gradient(135deg, rgba(8,15,28,0.96) 0%, rgba(11,24,43,0.96) 100%)",
            "border": "1px solid rgba(125,211,252,0.16)",
            "color": "#dbeafe",
            "fontSize": "0.93rem",
            "boxShadow": "0 10px 24px rgba(0,0,0,0.16)",
        },
    )

    return (
        html.Div([prompt_box, alert]),
        format_metric(last_spread, indicator_unit),
        f"{trend:+.2f}",
        f"{volatility:.2f}",
        series_fig,
        spread_fig,
        columns,
        scoreboard_rows,
        narrative,
    )


if __name__ == "__main__":
    app.run(debug=True)