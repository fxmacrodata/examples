"""
FXMacroData - Conversational Dash MCP Monitor
=============================================

Dash 4.3+ example that exposes a small FX dashboard through Dash MCP.

Run locally:
    pip install -r requirements.txt
    set FXMACRODATA_API_KEY=YOUR_API_KEY
    python app.py

Then open http://127.0.0.1:8050 and connect MCP clients to
http://127.0.0.1:8050/_mcp.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, dcc, html
from dash.mcp import configure_mcp_server, mcp_enabled

API_BASE = (
    os.getenv("PUBLIC_DASH_API_BASE_URL", "").strip()
    or "https://api.fxmacrodata.com/v1"
)
DOCS_URL = "https://fxmacrodata.com/documentation"
SUBSCRIBE_URL = "https://fxmacrodata.com/subscribe"
PUBLIC_MONITOR_URL = "https://fxmacrodata.com/app-gallery/dash/public-macro-monitor"

PAIR_CODES = {
    "EUR_USD": ("EUR", "USD"),
    "GBP_USD": ("GBP", "USD"),
    "USD_JPY": ("USD", "JPY"),
    "AUD_USD": ("AUD", "USD"),
    "USD_CAD": ("USD", "CAD"),
}
PAIR_OPTIONS = [
    {"label": code.replace("_", "/"), "value": code}
    for code in PAIR_CODES
]

WINDOW_DAYS = {"3m": 90, "6m": 180, "1y": 365}
WINDOW_OPTIONS = [
    {"label": label, "value": key}
    for label, key in [("3M", "3m"), ("6M", "6m"), ("1Y", "1y")]
]
DEFAULT_COMPARE = ["GBP_USD", "USD_JPY"]


def api_key() -> str:
    """Return the configured FXMacroData API key without exposing it to Dash state."""
    return (
        os.getenv("FXMACRODATA_API_KEY", "").strip()
        or os.getenv("FXMD_API_KEY", "").strip()
    )


def build_api_params(params: dict[str, Any]) -> dict[str, Any]:
    clean = {key: value for key, value in params.items() if value is not None}
    key = api_key()
    if key:
        clean["api_key"] = key
    return clean


def fetch_json(path: str, **params: Any) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            params=build_api_params(params),
            headers={"accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException:
        return {}

    if not response.ok:
        return {}
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def load_forex_series(pair: str, window_key: str) -> list[dict[str, Any]]:
    base, quote = PAIR_CODES.get(pair, PAIR_CODES["EUR_USD"])
    days = WINDOW_DAYS.get(window_key, 90)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    rows: list[dict[str, Any]] = []

    for offset in range(0, 300, 100):
        payload = fetch_json(
            f"/forex/{base.lower()}/{quote.lower()}",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=100,
            offset=offset,
        )
        data = payload.get("data", [])
        if not data:
            break

        for row in data:
            try:
                rows.append({"date": row["date"], "val": float(row["val"])})
            except (KeyError, TypeError, ValueError):
                continue
        if len(data) < 100:
            break

    return sorted(rows, key=lambda item: item["date"])


def return_series(rows: list[dict[str, Any]]) -> pd.Series:
    if len(rows) < 2:
        return pd.Series(dtype="float64")
    frame = pd.DataFrame(rows).dropna()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").drop_duplicates("date")
    frame["return"] = frame["val"].pct_change()
    clean = frame.dropna(subset=["return"])
    return clean.set_index("date")["return"]


def build_context_metrics(
    pair: str,
    compare_pairs: list[str],
    window_key: str,
) -> dict[str, Any]:
    rows = load_forex_series(pair, window_key)
    returns = return_series(rows)
    latest = rows[-1]["val"] if rows else None
    first = rows[0]["val"] if rows else None
    total_return = (latest / first - 1) if latest and first else None
    avg_abs_return = returns.abs().tail(20).mean() if not returns.empty else None
    risk = "elevated" if avg_abs_return and avg_abs_return > 0.006 else "normal"
    return {
        "pair": pair,
        "window": window_key,
        "latest": round(latest, 5) if latest is not None else None,
        "return_pct": round(total_return * 100, 2) if total_return else None,
        "observations": len(rows),
        "compare_pairs": compare_pairs,
        "risk_regime": risk,
        "api_key_configured": bool(api_key()),
    }


def empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 15, "color": "#475569"},
    )
    fig.update_layout(
        title=title,
        height=420,
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin={"l": 40, "r": 24, "t": 58, "b": 40},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def build_spot_figure(rows: list[dict[str, Any]], pair: str) -> go.Figure:
    title = f"{pair.replace('_', '/')} Spot"
    if not rows:
        return empty_figure(
            title,
            "No FX spot data is available. Add FXMACRODATA_API_KEY to load protected FX history.",
        )
    frame = pd.DataFrame(rows)
    fig = go.Figure(
        go.Scatter(
            x=frame["date"],
            y=frame["val"],
            mode="lines",
            line={"color": "#0ea5e9", "width": 3},
            name=pair.replace("_", "/"),
        )
    )
    fig.update_layout(
        title=title,
        height=420,
        template="plotly_white",
        margin={"l": 56, "r": 24, "t": 58, "b": 44},
        xaxis_title="Date",
        yaxis_title="Spot rate",
    )
    return fig


def build_correlation_figure(
    pair: str,
    compare_pairs: list[str],
    window_key: str,
) -> go.Figure:
    selected = [pair] + [code for code in compare_pairs if code != pair]
    series_map: dict[str, pd.Series] = {}
    for code in selected:
        series = return_series(load_forex_series(code, window_key))
        if not series.empty:
            series_map[code.replace("_", "/")] = series
    if len(series_map) < 2:
        return empty_figure(
            "Cross-Pair Correlation Matrix",
            "Not enough return data is available for correlation.",
        )

    corr = pd.DataFrame(series_map).corr()
    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=corr.round(2).values,
            texttemplate="%{text:.2f}",
            colorbar={"title": "Correlation"},
        )
    )
    fig.update_layout(
        title="Cross-Pair Correlation Matrix",
        height=420,
        template="plotly_white",
        margin={"l": 88, "r": 40, "t": 58, "b": 64},
    )
    return fig


def build_risk_figure(rows: list[dict[str, Any]], pair: str) -> go.Figure:
    returns = return_series(rows)
    title = f"{pair.replace('_', '/')} Risk Regime"
    if returns.empty:
        return empty_figure(title, "Not enough return data for risk.")
    rolling_vol = returns.rolling(20).std().dropna() * (252**0.5)
    if rolling_vol.empty:
        return empty_figure(title, "Need at least 20 return observations.")

    fig = go.Figure(
        go.Scatter(
            x=rolling_vol.index,
            y=rolling_vol.values,
            mode="lines",
            fill="tozeroy",
            line={"color": "#f97316", "width": 3},
            fillcolor="rgba(249, 115, 22, 0.16)",
            name="20-day annualized volatility",
        )
    )
    fig.update_layout(
        title=title,
        height=420,
        template="plotly_white",
        margin={"l": 56, "r": 24, "t": 58, "b": 44},
        xaxis_title="Date",
        yaxis_title="Annualized volatility",
    )
    return fig


def serve_layout() -> html.Main:
    return html.Main(
        [
            html.Header(
                [
                    html.P("FXMacroData + Plotly Dash MCP", className="eyebrow"),
                    html.H1("Conversational FX Macro Monitor"),
                    html.P(
                        "Explore FX spot history, cross-pair correlations, and risk regimes through Dash controls or an MCP-compatible assistant.",
                        className="lede",
                    ),
                    html.Div(
                        [
                            html.A("API docs", href=DOCS_URL, target="_blank"),
                            html.A("Subscribe", href=SUBSCRIBE_URL, target="_blank"),
                            html.A("Full public monitor", href=PUBLIC_MONITOR_URL, target="_blank"),
                        ],
                        className="link-row",
                    ),
                ],
                className="hero",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.Label("FX pair", htmlFor="pair-select"),
                            dcc.Dropdown(
                                id="pair-select",
                                options=PAIR_OPTIONS,
                                value="EUR_USD",
                                clearable=False,
                            ),
                        ],
                        className="control",
                    ),
                    html.Div(
                        [
                            html.Label("Compare with", htmlFor="compare-select"),
                            dcc.Dropdown(
                                id="compare-select",
                                options=PAIR_OPTIONS,
                                value=DEFAULT_COMPARE,
                                multi=True,
                            ),
                        ],
                        className="control",
                    ),
                    html.Div(
                        [
                            html.Label("Window", htmlFor="window-select"),
                            dcc.RadioItems(
                                id="window-select",
                                options=WINDOW_OPTIONS,
                                value="3m",
                                inline=True,
                                className="radio-row",
                            ),
                        ],
                        className="control",
                    ),
                ],
                className="controls",
            ),
            html.Section(id="kpi-row", className="kpis"),
            dcc.Graph(id="spot-graph"),
            dcc.Graph(id="correlation-graph"),
            dcc.Graph(id="risk-regime-graph"),
            dcc.Store(id="monitor-state-store"),
            html.Footer(
                [
                    "MCP endpoint for a local run: ",
                    html.Code("/_mcp"),
                    ". Keep API keys on the server.",
                ],
                className="footer",
            ),
        ],
        className="page",
    )


app = Dash(
    __name__,
    title="FXMacroData Dash MCP Monitor",
    enable_mcp=True,
    suppress_callback_exceptions=True,
)
server = app.server

configure_mcp_server(
    include_callbacks=False,
    expose_callback_docstrings=False,
)
app.layout = serve_layout

app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      body { margin: 0; background: #f8fafc; color: #0f172a; font-family: Inter, Segoe UI, Arial, sans-serif; }
      .page { max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }
      .hero { border-bottom: 1px solid #e2e8f0; margin-bottom: 22px; padding-bottom: 22px; }
      .eyebrow { margin: 0 0 8px; color: #0369a1; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
      h1 { margin: 0 0 10px; font-size: clamp(30px, 5vw, 54px); line-height: 1.02; letter-spacing: 0; }
      .lede { max-width: 780px; color: #475569; font-size: 18px; line-height: 1.55; margin: 0 0 18px; }
      .link-row { display: flex; flex-wrap: wrap; gap: 10px; }
      .link-row a { color: #075985; font-weight: 700; text-decoration: none; border: 1px solid #bae6fd; background: #e0f2fe; padding: 8px 10px; border-radius: 8px; }
      .controls { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(240px, 1.5fr) minmax(160px, .8fr); gap: 14px; margin: 22px 0; align-items: end; }
      .control { min-width: 0; }
      label { display: block; font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 6px; }
      .radio-row label { margin-right: 12px; font-weight: 600; }
      .kpis { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 0 0 14px; }
      .kpi { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
      .kpi span { display: block; color: #64748b; font-size: 12px; font-weight: 700; margin-bottom: 5px; }
      .kpi strong { font-size: 20px; }
      .footer { margin-top: 20px; color: #64748b; font-size: 14px; }
      code { background: #e2e8f0; padding: 2px 5px; border-radius: 5px; }
      @media (max-width: 760px) {
        .controls, .kpis { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""


def kpi_cards(metrics: dict[str, Any]) -> list[html.Div]:
    latest = metrics.get("latest")
    return_pct = metrics.get("return_pct")
    return [
        html.Div(
            [html.Span("Selected pair"), html.Strong(metrics["pair"].replace("_", "/"))],
            className="kpi",
        ),
        html.Div(
            [html.Span("Latest"), html.Strong("n/a" if latest is None else f"{latest:.5f}")],
            className="kpi",
        ),
        html.Div(
            [html.Span("Window return"), html.Strong("n/a" if return_pct is None else f"{return_pct:+.2f}%")],
            className="kpi",
        ),
        html.Div(
            [html.Span("Risk regime"), html.Strong(metrics["risk_regime"].title())],
            className="kpi",
        ),
    ]


@app.callback(
    Output("spot-graph", "figure"),
    Output("correlation-graph", "figure"),
    Output("risk-regime-graph", "figure"),
    Output("monitor-state-store", "data"),
    Output("kpi-row", "children"),
    Input("pair-select", "value"),
    Input("compare-select", "value"),
    Input("window-select", "value"),
    mcp_enabled=True,
    mcp_expose_docstring=True,
)
def update_figures(
    pair: str,
    compare_pairs: list[str] | None,
    window_key: str,
) -> tuple[go.Figure, go.Figure, go.Figure, dict[str, Any], list[html.Div]]:
    """Render selected FX charts and dashboard state for an MCP assistant."""
    safe_pair = pair if pair in PAIR_CODES else "EUR_USD"
    safe_compare = [code for code in (compare_pairs or []) if code in PAIR_CODES]
    safe_compare = safe_compare or DEFAULT_COMPARE
    safe_window = window_key if window_key in WINDOW_DAYS else "3m"
    rows = load_forex_series(safe_pair, safe_window)
    metrics = build_context_metrics(safe_pair, safe_compare, safe_window)
    return (
        build_spot_figure(rows, safe_pair),
        build_correlation_figure(safe_pair, safe_compare, safe_window),
        build_risk_figure(rows, safe_pair),
        metrics,
        kpi_cards(metrics),
    )


@mcp_enabled(name="get_public_macro_monitor_snapshot", expose_docstring=True)
def get_public_macro_monitor_snapshot(
    pair: str = "EUR_USD",
    window_key: str = "3m",
    compare_pair: str | None = "GBP_USD",
) -> dict[str, Any]:
    """Return a compact FX spot, risk, and comparison summary."""
    safe_pair = pair if pair in PAIR_CODES else "EUR_USD"
    safe_window = window_key if window_key in WINDOW_DAYS else "3m"
    safe_compare = compare_pair if compare_pair in PAIR_CODES else "GBP_USD"
    return build_context_metrics(safe_pair, [safe_compare], safe_window)


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8050")),
    )
