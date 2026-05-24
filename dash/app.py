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
DEFAULT_B = "EUR"
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
        template="plotly_white",
        height=360,
        margin=dict(l=30, r=20, t=58, b=34),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8fafc",
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
                font=dict(size=14, color="#64748b"),
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
            line=dict(color="#0369a1", width=3),
            marker=dict(size=6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["val_b"],
            mode="lines+markers",
            name=label_b,
            line=dict(color="#0f766e", width=3),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        title=f"{indicator_label}: {label_a} vs {label_b}",
        template="plotly_white",
        height=380,
        margin=dict(l=40, r=24, t=58, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8fafc",
        legend=dict(orientation="h", y=1.09, x=0),
        xaxis=dict(title="Date", gridcolor="#e2e8f0"),
        yaxis=dict(title=f"Value ({unit})" if unit else "Value", gridcolor="#e2e8f0"),
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
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=24, t=58, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f8fafc",
        xaxis=dict(title="Date", gridcolor="#e2e8f0"),
        yaxis=dict(title="Spread", gridcolor="#e2e8f0"),
    )
    return fig


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
    external_stylesheets=[dbc.themes.BOOTSTRAP],
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
        "background": "radial-gradient(circle at 12% 8%, #dbeafe 0%, #f8fafc 35%, #ecfeff 100%)",
        "padding": "20px 16px 40px",
        "fontFamily": "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    },
    children=[
        dbc.Container(
            style={"maxWidth": "1240px"},
            children=[
                html.Div(
                    style={
                        "background": "linear-gradient(120deg, #0f172a 0%, #0c4a6e 55%, #115e59 100%)",
                        "borderRadius": "22px",
                        "padding": "26px 24px",
                        "color": "#f8fafc",
                        "boxShadow": "0 18px 46px rgba(15, 23, 42, 0.32)",
                        "marginBottom": "18px",
                    },
                    children=[
                        html.P("FXMacroData Dash Example", style={"opacity": 0.85, "marginBottom": "6px", "letterSpacing": "0.08em", "textTransform": "uppercase", "fontSize": "12px", "fontWeight": 700}),
                        html.H1("Policy Divergence Studio", style={"margin": "0 0 8px", "fontSize": "2.1rem", "fontWeight": 800}),
                        html.P(
                            "Compare two countries on one macro indicator, track spread momentum, and generate a fast regime narrative.",
                            style={"margin": 0, "fontSize": "1.02rem", "maxWidth": "880px", "opacity": 0.94},
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
                                        html.Label("Country A", className="fw-semibold mb-1"),
                                        dcc.Dropdown(ALL_CURRENCIES, DEFAULT_A, id="currency-a", clearable=False),
                                    ]
                                ),
                                style={"border": "1px solid #cbd5e1", "borderRadius": "14px", "height": "100%"},
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Country B", className="fw-semibold mb-1"),
                                        dcc.Dropdown(ALL_CURRENCIES, DEFAULT_B, id="currency-b", clearable=False),
                                    ]
                                ),
                                style={"border": "1px solid #cbd5e1", "borderRadius": "14px", "height": "100%"},
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Indicator", className="fw-semibold mb-1"),
                                        dcc.Dropdown(
                                            [{"label": label, "value": key} for key, label, _ in INDICATORS],
                                            DEFAULT_INDICATOR,
                                            id="indicator",
                                            clearable=False,
                                        ),
                                    ]
                                ),
                                style={"border": "1px solid #cbd5e1", "borderRadius": "14px", "height": "100%"},
                            ),
                        ),
                        dbc.Col(
                            md=3,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.Label("Lookback", className="fw-semibold mb-1"),
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
                                        ),
                                    ]
                                ),
                                style={"border": "1px solid #cbd5e1", "borderRadius": "14px", "height": "100%"},
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
                                            html.Label("Professional API key (optional for USD)", className="fw-semibold mb-0"),
                                            html.A("Get key", href=API_MANAGEMENT_URL, target="_blank", style={"fontSize": "0.88rem"}),
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
                                                "border": "1px solid #94a3b8",
                                                "fontFamily": "monospace",
                                            },
                                        ),
                                    ]
                                ),
                                style={"border": "1px solid #cbd5e1", "borderRadius": "14px"},
                            ),
                        ),
                        dbc.Col(
                            md=4,
                            children=dbc.Button(
                                "Run Divergence Analysis",
                                id="run-btn",
                                n_clicks=0,
                                className="w-100",
                                style={
                                    "height": "54px",
                                    "fontWeight": 700,
                                    "borderRadius": "12px",
                                    "border": "none",
                                    "background": "linear-gradient(90deg, #0284c7 0%, #0f766e 100%)",
                                },
                            ),
                        ),
                    ],
                ),
                html.Div(id="status-box", style={"marginTop": "14px"}),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("Current spread", className="text-uppercase text-secondary", style={"fontSize": "11px", "letterSpacing": "0.08em"}), html.H3("-", id="metric-spread", className="mb-0")]), style={"borderRadius": "14px", "border": "1px solid #cbd5e1"})),
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("3-point trend", className="text-uppercase text-secondary", style={"fontSize": "11px", "letterSpacing": "0.08em"}), html.H3("-", id="metric-trend", className="mb-0")]), style={"borderRadius": "14px", "border": "1px solid #cbd5e1"})),
                        dbc.Col(md=4, children=dbc.Card(dbc.CardBody([html.Div("Spread volatility", className="text-uppercase text-secondary", style={"fontSize": "11px", "letterSpacing": "0.08em"}), html.H3("-", id="metric-vol", className="mb-0")]), style={"borderRadius": "14px", "border": "1px solid #cbd5e1"})),
                    ],
                ),
                dbc.Row(
                    className="g-3 mt-1",
                    children=[
                        dbc.Col(md=7, children=dbc.Card(dbc.CardBody(dcc.Graph(id="series-chart", figure=blank_figure("Country comparison"), config={"displayModeBar": False})), style={"borderRadius": "14px", "border": "1px solid #cbd5e1"})),
                        dbc.Col(md=5, children=dbc.Card(dbc.CardBody(dcc.Graph(id="spread-chart", figure=blank_figure("Spread trend"), config={"displayModeBar": False})), style={"borderRadius": "14px", "border": "1px solid #cbd5e1"})),
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
                                        html.H5("Cross-Indicator Scoreboard", className="mb-3"),
                                        dash_table.DataTable(
                                            id="scoreboard",
                                            columns=[],
                                            data=[],
                                            style_header={
                                                "backgroundColor": "#0f172a",
                                                "color": "white",
                                                "fontWeight": "700",
                                            },
                                            style_cell={
                                                "padding": "9px",
                                                "fontSize": "13px",
                                                "border": "1px solid #e2e8f0",
                                            },
                                            style_data={"backgroundColor": "#f8fafc", "color": "#1e293b"},
                                        ),
                                    ]
                                ),
                                style={"borderRadius": "14px", "border": "1px solid #cbd5e1"},
                            ),
                        ),
                        dbc.Col(
                            md=4,
                            children=dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.H5("Narrative", className="mb-3"),
                                        html.Div(id="narrative", style={"lineHeight": "1.6", "color": "#334155"}),
                                        html.Hr(),
                                        html.P("Documentation", className="mb-1 fw-semibold"),
                                        html.A("API docs", href=DOCS_URL, target="_blank"),
                                    ]
                                ),
                                style={"borderRadius": "14px", "border": "1px solid #cbd5e1", "height": "100%"},
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
    State("currency-a", "value"),
    State("currency-b", "value"),
    State("indicator", "value"),
    State("lookback-years", "value"),
    State("api-key", "value"),
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

    return (
        alert,
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