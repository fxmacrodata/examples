"""
FXMacroData - Conversational Dash MCP Monitor
=============================================

Dash 4.3+ example that exposes a compact FX dashboard through Dash MCP.

Run locally:
    pip install -r requirements.txt
    set FXMACRODATA_API_KEY=YOUR_API_KEY
    python app.py

Then open http://127.0.0.1:8050 and connect MCP clients to
http://127.0.0.1:8050/_mcp.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from inspect import signature
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
from dash import Dash, Input, Output, dcc, html

try:
    from dash.mcp import configure_mcp_server, mcp_enabled
except ImportError:  # Dash MCP is available in Dash 4.3+.
    configure_mcp_server = None

    def mcp_enabled(*decorator_args: Any, **_decorator_kwargs: Any) -> Any:
        if decorator_args and callable(decorator_args[0]):
            return decorator_args[0]

        def _identity(func: Any) -> Any:
            return func

        return _identity


API_BASE = (
    os.getenv("PUBLIC_DASH_API_BASE_URL", "").strip().rstrip("/")
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

DEFAULT_PAIR = "EUR_USD"
DEFAULT_COMPARE = ["GBP_USD", "USD_JPY"]
DEFAULT_WINDOW = "3m"
DEMO_FALLBACK_ENABLED = os.getenv("FXMACRODATA_DEMO_FALLBACK", "1").lower() not in {
    "0",
    "false",
    "no",
}

GRAPH_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
}

FIGURE_COLORS = {
    "text": "#0f172a",
    "muted": "#64748b",
    "grid": "rgba(148, 163, 184, 0.24)",
    "panel": "#ffffff",
    "plot": "#ffffff",
    "blue": "#2563eb",
    "cyan": "#0891b2",
    "teal": "#0f766e",
    "amber": "#d97706",
    "red": "#dc2626",
    "purple": "#7c3aed",
}

_DASH_SUPPORTS_MCP = "enable_mcp" in signature(Dash).parameters


def _dash_mcp_constructor_options() -> dict[str, bool]:
    return {"enable_mcp": True} if _DASH_SUPPORTS_MCP else {}


def _dash_mcp_callback_options() -> dict[str, bool]:
    if _DASH_SUPPORTS_MCP and configure_mcp_server is not None:
        return {"mcp_enabled": True, "mcp_expose_docstring": True}
    return {}


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


def fetch_json(path: str, **params: Any) -> tuple[dict[str, Any], str]:
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            params=build_api_params(params),
            headers={"accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException:
        return {}, "network_error"

    if response.status_code in {401, 403}:
        return {}, "auth_required"
    if response.status_code == 404:
        return {}, "no_data"
    if not response.ok:
        return {}, "api_error"

    try:
        payload = response.json()
    except ValueError:
        return {}, "api_error"
    return (payload, "ok") if isinstance(payload, dict) else ({}, "api_error")


def sanitize_pair(pair: str | None) -> str:
    return pair if pair in PAIR_CODES else DEFAULT_PAIR


def sanitize_window(window_key: str | None) -> str:
    return window_key if window_key in WINDOW_DAYS else DEFAULT_WINDOW


def sanitize_compare_pairs(
    selected_pair: str,
    compare_pairs: list[str] | str | None,
) -> list[str]:
    if isinstance(compare_pairs, str):
        compare_values = [compare_pairs]
    else:
        compare_values = list(compare_pairs or [])

    safe: list[str] = []
    for code in compare_values:
        if code in PAIR_CODES and code != selected_pair and code not in safe:
            safe.append(code)

    if not safe:
        safe = [code for code in DEFAULT_COMPARE if code != selected_pair]
    return safe[:4]


def format_pair(pair: str) -> str:
    return pair.replace("_", "/")


def format_number(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):,.{digits}f}"


def format_percent(value: float | None, digits: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):+,.{digits}f}%"


def format_utc_timestamp(value: str | None) -> str:
    if not value:
        return "n/a"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def generate_demo_series(pair: str, window_key: str) -> list[dict[str, Any]]:
    """Create deterministic sample data so the example is useful without a key."""
    days = WINDOW_DAYS.get(window_key, WINDOW_DAYS[DEFAULT_WINDOW])
    base_level = {
        "EUR_USD": 1.08,
        "GBP_USD": 1.27,
        "USD_JPY": 154.0,
        "AUD_USD": 0.66,
        "USD_CAD": 1.36,
    }.get(pair, 1.0)
    pair_seed = sum(ord(char) for char in pair)
    end_date = datetime.now(timezone.utc).date()
    rows: list[dict[str, Any]] = []

    for idx in range(days + 1):
        ds = end_date - timedelta(days=days - idx)
        drift = 1 + ((idx / max(days, 1)) - 0.5) * ((pair_seed % 13) - 6) / 350
        cycle = 1 + math.sin((idx + pair_seed % 17) / 8.5) * 0.009
        shorter_cycle = 1 + math.sin((idx + pair_seed % 7) / 2.9) * 0.0025
        val = base_level * drift * cycle * shorter_cycle
        rows.append({"date": ds.isoformat(), "val": round(val, 5)})
    return rows


def load_forex_series(pair: str, window_key: str) -> tuple[list[dict[str, Any]], str]:
    safe_pair = sanitize_pair(pair)
    safe_window = sanitize_window(window_key)

    if not api_key() and DEMO_FALLBACK_ENABLED:
        return generate_demo_series(safe_pair, safe_window), "demo"

    base, quote = PAIR_CODES[safe_pair]
    days = WINDOW_DAYS[safe_window]
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    status = "no_data"

    for offset in range(0, 500, 100):
        payload, status = fetch_json(
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

    if rows:
        sorted_rows = sorted(rows, key=lambda item: item["date"])
        return sorted_rows, "live"

    if DEMO_FALLBACK_ENABLED:
        return generate_demo_series(safe_pair, safe_window), f"demo_{status}"
    return [], status


def frame_from_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["date", "val"])
    frame = pd.DataFrame(rows).dropna()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["val"] = pd.to_numeric(frame["val"], errors="coerce")
    return frame.dropna(subset=["date", "val"]).sort_values("date").drop_duplicates("date")


def return_series(rows: list[dict[str, Any]]) -> pd.Series:
    frame = frame_from_rows(rows)
    if len(frame) < 2:
        return pd.Series(dtype="float64")
    returns = frame.set_index("date")["val"].pct_change().dropna()
    return returns.astype("float64")


def indexed_series(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = frame_from_rows(rows)
    if frame.empty:
        return frame
    first = float(frame.iloc[0]["val"])
    if first == 0:
        frame["indexed"] = None
    else:
        frame["indexed"] = frame["val"] / first * 100
    return frame


def source_label(statuses: dict[str, str]) -> str:
    values = set(statuses.values())
    if values == {"live"}:
        return "Live FXMacroData API"
    if values and all(value == "demo" for value in values):
        return "Demo sample"
    if any(value.startswith("demo_") for value in values):
        return "Demo fallback"
    return "Mixed source"


def risk_regime(annualized_vol_pct: float | None) -> str:
    if annualized_vol_pct is None:
        return "insufficient"
    if annualized_vol_pct >= 12:
        return "elevated"
    if annualized_vol_pct >= 8:
        return "watch"
    return "normal"


def build_metrics(
    pair: str,
    compare_pairs: list[str],
    window_key: str,
    series_map: dict[str, list[dict[str, Any]]],
    statuses: dict[str, str],
) -> dict[str, Any]:
    rows = series_map.get(pair, [])
    frame = frame_from_rows(rows)
    returns = return_series(rows)

    metrics: dict[str, Any] = {
        "pair": pair,
        "pair_label": format_pair(pair),
        "compare_pairs": compare_pairs,
        "compare_labels": [format_pair(code) for code in compare_pairs],
        "window": window_key,
        "window_label": window_key.upper(),
        "source": source_label(statuses),
        "source_statuses": statuses,
        "api_key_configured": bool(api_key()),
        "observations": int(len(frame)),
        "status": "ok" if len(frame) >= 2 else "insufficient_data",
    }

    if len(frame) < 2 or returns.empty:
        metrics.update(
            {
                "latest": None,
                "latest_date": None,
                "first_date": None,
                "window_return_pct": None,
                "daily_vol_pct": None,
                "annualized_vol_pct": None,
                "momentum_20d_pct": None,
                "risk_regime": "insufficient",
            }
        )
        return metrics

    latest = float(frame.iloc[-1]["val"])
    first = float(frame.iloc[0]["val"])
    window_return_pct = ((latest / first) - 1) * 100 if first else None
    daily_vol_pct = float(returns.std() * 100) if len(returns) > 1 else None
    recent_returns = returns.tail(20)
    annualized_vol_pct = (
        float(recent_returns.std() * math.sqrt(252) * 100)
        if len(recent_returns) > 1
        else None
    )
    if len(frame) >= 21:
        base_20d = float(frame.iloc[-21]["val"])
        momentum_20d_pct = ((latest / base_20d) - 1) * 100 if base_20d else None
    else:
        momentum_20d_pct = window_return_pct

    metrics.update(
        {
            "latest": latest,
            "latest_date": str(frame.iloc[-1]["date"].date()),
            "first_date": str(frame.iloc[0]["date"].date()),
            "window_return_pct": window_return_pct,
            "daily_vol_pct": daily_vol_pct,
            "annualized_vol_pct": annualized_vol_pct,
            "momentum_20d_pct": momentum_20d_pct,
            "risk_regime": risk_regime(annualized_vol_pct),
        }
    )
    return metrics


def build_monitor_state(
    pair: str | None,
    compare_pairs: list[str] | str | None,
    window_key: str | None,
) -> dict[str, Any]:
    safe_pair = sanitize_pair(pair)
    safe_window = sanitize_window(window_key)
    safe_compare = sanitize_compare_pairs(safe_pair, compare_pairs)
    selected = [safe_pair] + safe_compare
    series_map: dict[str, list[dict[str, Any]]] = {}
    statuses: dict[str, str] = {}

    for code in selected:
        rows, status = load_forex_series(code, safe_window)
        series_map[code] = rows
        statuses[code] = status

    metrics = build_metrics(safe_pair, safe_compare, safe_window, series_map, statuses)
    state = {
        "pair": safe_pair,
        "compare_pairs": safe_compare,
        "window": safe_window,
        "series": series_map,
        "metrics": metrics,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    state["summary"] = build_market_note(metrics)
    return state


def chart_layout(title: str, subtitle: str | None = None, height: int = 420) -> dict[str, Any]:
    title_text = f"{title}<br><span style='font-size:13px;color:{FIGURE_COLORS['muted']}'>{subtitle}</span>" if subtitle else title
    return {
        "title": {"text": title_text, "x": 0.0, "xanchor": "left"},
        "height": height,
        "template": "plotly_white",
        "paper_bgcolor": FIGURE_COLORS["panel"],
        "plot_bgcolor": FIGURE_COLORS["plot"],
        "font": {"color": FIGURE_COLORS["text"], "family": "Inter, Segoe UI, Arial, sans-serif"},
        "margin": {"l": 58, "r": 24, "t": 72, "b": 48},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        "hovermode": "x unified",
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
        align="center",
        font={"size": 15, "color": FIGURE_COLORS["muted"]},
    )
    fig.update_layout(**chart_layout(title))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def style_axes(fig: go.Figure, y_title: str | None = None) -> go.Figure:
    fig.update_xaxes(
        gridcolor=FIGURE_COLORS["grid"],
        zeroline=False,
        showline=True,
        linecolor="rgba(148, 163, 184, 0.5)",
    )
    fig.update_yaxes(
        title=y_title,
        gridcolor=FIGURE_COLORS["grid"],
        zeroline=False,
        showline=True,
        linecolor="rgba(148, 163, 184, 0.5)",
    )
    return fig


def build_spot_figure(state: dict[str, Any]) -> go.Figure:
    pair = state.get("pair", DEFAULT_PAIR)
    rows = state.get("series", {}).get(pair, [])
    frame = frame_from_rows(rows)
    if frame.empty:
        return empty_figure(format_pair(pair), "No FX spot data is available.")

    frame["ma20"] = frame["val"].rolling(20).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["val"],
            mode="lines",
            line={"color": FIGURE_COLORS["blue"], "width": 3},
            name=format_pair(pair),
            hovertemplate="%{y:.5f}<extra></extra>",
        )
    )
    if frame["ma20"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame["ma20"],
                mode="lines",
                line={"color": FIGURE_COLORS["amber"], "width": 2, "dash": "dot"},
                name="20-day average",
                hovertemplate="%{y:.5f}<extra></extra>",
            )
        )

    metrics = state.get("metrics", {})
    subtitle = f"{metrics.get('source', 'Source unknown')} - {metrics.get('observations', 0)} observations"
    fig.update_layout(**chart_layout(f"{format_pair(pair)} Spot", subtitle))
    style_axes(fig, "Spot rate")
    return fig


def build_indexed_figure(state: dict[str, Any]) -> go.Figure:
    pair = state.get("pair", DEFAULT_PAIR)
    selected = [pair] + list(state.get("compare_pairs", []))
    series_map = state.get("series", {})
    colors = [
        FIGURE_COLORS["teal"],
        FIGURE_COLORS["purple"],
        FIGURE_COLORS["amber"],
        FIGURE_COLORS["red"],
        FIGURE_COLORS["cyan"],
    ]
    fig = go.Figure()

    for idx, code in enumerate(selected):
        frame = indexed_series(series_map.get(code, []))
        if frame.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame["indexed"],
                mode="lines",
                line={
                    "color": colors[idx % len(colors)],
                    "width": 3 if code == pair else 2,
                    "dash": "solid" if code == pair else "dash",
                },
                name=format_pair(code),
                hovertemplate="%{y:.2f}<extra></extra>",
            )
        )

    if not fig.data:
        return empty_figure("Indexed Performance", "Not enough data to compare pairs.")

    fig.add_hline(
        y=100,
        line_dash="dot",
        line_color="rgba(100, 116, 139, 0.7)",
        annotation_text="Start",
        annotation_position="bottom right",
    )
    fig.update_layout(
        **chart_layout(
            "Indexed Performance",
            "All selected pairs rebased to 100 at the start of the window.",
        )
    )
    style_axes(fig, "Index")
    return fig


def build_correlation_figure(state: dict[str, Any]) -> go.Figure:
    pair = state.get("pair", DEFAULT_PAIR)
    selected = [pair] + list(state.get("compare_pairs", []))
    series_map: dict[str, pd.Series] = {}
    for code in selected:
        series = return_series(state.get("series", {}).get(code, []))
        if not series.empty:
            series_map[format_pair(code)] = series

    if len(series_map) < 2:
        return empty_figure(
            "Cross-Pair Correlation",
            "At least two return series are needed for correlation.",
        )

    corr = pd.DataFrame(series_map).corr()
    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            zmin=-1,
            zmax=1,
            colorscale=[
                [0.0, FIGURE_COLORS["red"]],
                [0.5, "#f8fafc"],
                [1.0, FIGURE_COLORS["teal"]],
            ],
            text=corr.round(2).values,
            texttemplate="%{text:.2f}",
            hovertemplate="%{y} vs %{x}<br>Correlation %{z:.2f}<extra></extra>",
            colorbar={"title": "Corr", "len": 0.84},
        )
    )
    fig.update_layout(
        **chart_layout(
            "Cross-Pair Correlation",
            "Rolling-window daily return relationships.",
        )
    )
    fig.update_xaxes(side="bottom")
    return fig


def build_risk_figure(state: dict[str, Any]) -> go.Figure:
    pair = state.get("pair", DEFAULT_PAIR)
    returns = return_series(state.get("series", {}).get(pair, []))
    if returns.empty:
        return empty_figure("Risk Regime", "Not enough return data for risk analysis.")

    rolling_vol = returns.rolling(20).std().dropna() * math.sqrt(252) * 100
    if rolling_vol.empty:
        return empty_figure("Risk Regime", "Need at least 20 return observations.")

    fig = go.Figure(
        go.Scatter(
            x=rolling_vol.index,
            y=rolling_vol.values,
            mode="lines",
            fill="tozeroy",
            line={"color": FIGURE_COLORS["red"], "width": 3},
            fillcolor="rgba(220, 38, 38, 0.12)",
            name="20-day annualized volatility",
            hovertemplate="%{y:.2f}%<extra></extra>",
        )
    )
    fig.add_hline(
        y=8,
        line_dash="dot",
        line_color=FIGURE_COLORS["amber"],
        annotation_text="Watch",
        annotation_position="top left",
    )
    fig.add_hline(
        y=12,
        line_dash="dot",
        line_color=FIGURE_COLORS["red"],
        annotation_text="Elevated",
        annotation_position="top left",
    )
    fig.update_layout(
        **chart_layout(
            f"{format_pair(pair)} Risk Regime",
            "20-day realized volatility, annualized.",
        )
    )
    style_axes(fig, "Annualized volatility")
    fig.update_yaxes(ticksuffix="%")
    return fig


def build_market_note(metrics: dict[str, Any]) -> str:
    if metrics.get("status") != "ok":
        return "Not enough observations are available for this selection yet."

    source_note = ""
    source = str(metrics.get("source", ""))
    if source != "Live FXMacroData API":
        source_note = f" Source: {source.lower()}."

    compare = ", ".join(metrics.get("compare_labels") or ["none"])
    return (
        f"{metrics['pair_label']} is {format_percent(metrics.get('window_return_pct'))} "
        f"over the {metrics['window_label']} window. The latest value is "
        f"{format_number(metrics.get('latest'), 5)} as of {metrics.get('latest_date')}. "
        f"Recent annualized volatility is {format_percent(metrics.get('annualized_vol_pct'))}, "
        f"putting the pair in a {metrics.get('risk_regime', 'unknown')} risk regime. "
        f"Comparison set: {compare}.{source_note}"
    )


def status_strip(state: dict[str, Any]) -> html.Div:
    metrics = state.get("metrics", {})
    return html.Div(
        [
            html.Span(metrics.get("source", "Source unknown"), className="status-primary"),
            html.Span(f"Updated {format_utc_timestamp(state.get('updated_at'))}"),
            html.Span(f"{metrics.get('observations', 0)} observations"),
            html.Span(f"MCP /_mcp"),
        ],
        className="status-content",
    )


def kpi_cards(metrics: dict[str, Any]) -> list[html.Div]:
    return [
        html.Div(
            [html.Span("Pair"), html.Strong(metrics.get("pair_label", "n/a"))],
            className="kpi",
        ),
        html.Div(
            [html.Span("Latest"), html.Strong(format_number(metrics.get("latest"), 5))],
            className="kpi",
        ),
        html.Div(
            [
                html.Span("Window return"),
                html.Strong(format_percent(metrics.get("window_return_pct"))),
            ],
            className="kpi",
        ),
        html.Div(
            [
                html.Span("20-day vol"),
                html.Strong(format_percent(metrics.get("annualized_vol_pct"))),
            ],
            className="kpi",
        ),
        html.Div(
            [
                html.Span("Risk regime"),
                html.Strong(str(metrics.get("risk_regime", "n/a")).title()),
            ],
            className=f"kpi regime-{metrics.get('risk_regime', 'unknown')}",
        ),
    ]


def serve_layout() -> html.Main:
    return html.Main(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.P("FXMacroData + Plotly Dash MCP", className="eyebrow"),
                            html.H1("Conversational FX Macro Monitor"),
                            html.P(
                                "A Dash dashboard for FX spot moves, cross-pair relationships, and risk-regime context.",
                                className="lede",
                            ),
                            html.Div(
                                [
                                    html.A("API docs", href=DOCS_URL, target="_blank"),
                                    html.A("Subscribe", href=SUBSCRIBE_URL, target="_blank"),
                                    html.A(
                                        "Live public monitor",
                                        href=PUBLIC_MONITOR_URL,
                                        target="_blank",
                                    ),
                                ],
                                className="link-row",
                            ),
                        ],
                        className="hero-copy",
                    ),
                    html.Div(
                        [
                            html.Span("MCP endpoint", className="endpoint-label"),
                            html.Code("/_mcp"),
                            html.Small("Local HTTP transport"),
                        ],
                        className="endpoint-panel",
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
                                value=DEFAULT_PAIR,
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
                        className="control compare-control",
                    ),
                    html.Div(
                        [
                            html.Label("Window", htmlFor="window-select"),
                            dcc.RadioItems(
                                id="window-select",
                                options=WINDOW_OPTIONS,
                                value=DEFAULT_WINDOW,
                                inline=True,
                                className="radio-row",
                            ),
                        ],
                        className="control",
                    ),
                    html.Button("Refresh", id="refresh-button", n_clicks=0, className="refresh-button"),
                ],
                className="controls",
            ),
            dcc.Loading(
                id="loading-state",
                type="default",
                children=[
                    html.Section(id="status-strip", className="status-strip"),
                    html.Section(id="kpi-row", className="kpis"),
                    html.Section(html.P(id="market-note"), className="market-note"),
                    html.Section(
                        [
                            html.Div(
                                dcc.Graph(
                                    id="spot-graph",
                                    config=GRAPH_CONFIG,
                                    className="chart-graph",
                                ),
                                className="chart-panel chart-panel-wide",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="indexed-graph",
                                    config=GRAPH_CONFIG,
                                    className="chart-graph",
                                ),
                                className="chart-panel chart-panel-wide",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="correlation-graph",
                                    config=GRAPH_CONFIG,
                                    className="chart-graph",
                                ),
                                className="chart-panel",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="risk-regime-graph",
                                    config=GRAPH_CONFIG,
                                    className="chart-graph",
                                ),
                                className="chart-panel",
                            ),
                        ],
                        className="chart-grid",
                    ),
                ],
            ),
            dcc.Store(id="monitor-state-store"),
            html.Footer(
                [
                    "API keys stay server-side. The browser receives chart data and a non-sensitive dashboard snapshot only.",
                ],
                className="footer",
            ),
        ],
        className="page",
    )


app = Dash(
    __name__,
    title="FXMacroData Dash MCP Monitor",
    suppress_callback_exceptions=True,
    **_dash_mcp_constructor_options(),
)
server = app.server

if configure_mcp_server is not None:
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
      :root {
        --bg: #eef2f7;
        --panel: #ffffff;
        --ink: #0f172a;
        --muted: #64748b;
        --line: #d9e2ec;
        --blue: #2563eb;
        --cyan: #0891b2;
        --teal: #0f766e;
        --amber: #d97706;
        --red: #dc2626;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--ink);
        font-family: Inter, Segoe UI, Arial, sans-serif;
      }
      .page {
        max-width: 1260px;
        margin: 0 auto;
        padding: 28px 20px 44px;
      }
      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 260px;
        gap: 22px;
        align-items: stretch;
        margin-bottom: 18px;
      }
      .hero-copy,
      .endpoint-panel,
      .controls,
      .status-strip,
      .market-note,
      .chart-panel,
      .kpi {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
      }
      .hero-copy { padding: 24px; }
      .eyebrow {
        margin: 0 0 8px;
        color: var(--cyan);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }
      h1 {
        margin: 0 0 10px;
        font-size: clamp(34px, 5vw, 56px);
        line-height: 1.02;
        letter-spacing: 0;
      }
      .lede {
        max-width: 760px;
        margin: 0 0 18px;
        color: #475569;
        font-size: 18px;
        line-height: 1.55;
      }
      .link-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .link-row a {
        border: 1px solid #bae6fd;
        background: #ecfeff;
        color: #075985;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 800;
        padding: 8px 10px;
        text-decoration: none;
      }
      .endpoint-panel {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 9px;
        padding: 20px;
      }
      .endpoint-label {
        color: var(--muted);
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
      }
      .endpoint-panel code {
        display: block;
        width: fit-content;
        background: #0f172a;
        color: #f8fafc;
        border-radius: 6px;
        padding: 7px 9px;
        font-size: 18px;
      }
      .endpoint-panel small { color: var(--muted); line-height: 1.45; }
      .controls {
        display: grid;
        grid-template-columns: minmax(170px, 0.9fr) minmax(280px, 1.5fr) minmax(170px, 0.8fr) auto;
        gap: 14px;
        align-items: end;
        margin-bottom: 14px;
        padding: 16px;
      }
      .control { min-width: 0; }
      label {
        display: block;
        margin-bottom: 6px;
        color: #334155;
        font-size: 13px;
        font-weight: 800;
      }
      .radio-row label {
        margin-right: 12px;
        color: #334155;
        font-weight: 700;
      }
      .refresh-button {
        border: 0;
        border-radius: 8px;
        background: var(--blue);
        color: #ffffff;
        cursor: pointer;
        font-size: 14px;
        font-weight: 800;
        min-height: 38px;
        padding: 0 16px;
      }
      .refresh-button:hover { background: #1d4ed8; }
      .status-strip {
        margin-bottom: 12px;
        padding: 10px 14px;
      }
      .status-content {
        display: flex;
        flex-wrap: wrap;
        gap: 10px 18px;
        align-items: center;
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
      }
      .status-primary {
        color: var(--teal);
        font-weight: 900;
      }
      .kpis {
        display: grid;
        grid-template-columns: repeat(5, minmax(125px, 1fr));
        gap: 12px;
        margin: 0 0 12px;
      }
      .kpi {
        min-height: 86px;
        padding: 14px;
      }
      .kpi span {
        display: block;
        margin-bottom: 7px;
        color: var(--muted);
        font-size: 12px;
        font-weight: 800;
      }
      .kpi strong {
        color: var(--ink);
        font-size: 21px;
        line-height: 1.15;
      }
      .regime-normal strong { color: var(--teal); }
      .regime-watch strong { color: var(--amber); }
      .regime-elevated strong { color: var(--red); }
      .market-note {
        margin-bottom: 14px;
        padding: 14px 16px;
      }
      .market-note p {
        margin: 0;
        color: #334155;
        font-size: 15px;
        line-height: 1.55;
      }
      .chart-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
      }
      .chart-panel {
        min-width: 0;
        overflow: hidden;
        padding: 8px;
      }
      .chart-panel-wide {
        grid-column: span 1;
      }
      .chart-graph {
        min-height: 420px;
      }
      .footer {
        margin-top: 18px;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.5;
      }
      @media (max-width: 920px) {
        .hero,
        .controls,
        .chart-grid,
        .kpis {
          grid-template-columns: 1fr;
        }
        .endpoint-panel { min-height: auto; }
      }
      @media (max-width: 560px) {
        .page { padding: 16px 12px 34px; }
        .hero-copy,
        .endpoint-panel,
        .controls {
          padding: 16px;
        }
        h1 { font-size: 32px; }
        .lede { font-size: 16px; }
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


@app.callback(
    Output("monitor-state-store", "data"),
    Output("status-strip", "children"),
    Output("kpi-row", "children"),
    Output("market-note", "children"),
    Input("pair-select", "value"),
    Input("compare-select", "value"),
    Input("window-select", "value"),
    Input("refresh-button", "n_clicks"),
    **_dash_mcp_callback_options(),
)
def update_monitor_state(
    pair: str,
    compare_pairs: list[str] | None,
    window_key: str,
    _n_clicks: int,
) -> tuple[dict[str, Any], html.Div, list[html.Div], str]:
    """Fetch FX data and prepare one reusable dashboard state object."""
    state = build_monitor_state(pair, compare_pairs, window_key)
    metrics = state["metrics"]
    return state, status_strip(state), kpi_cards(metrics), state["summary"]


@app.callback(
    Output("spot-graph", "figure"),
    Output("indexed-graph", "figure"),
    Output("correlation-graph", "figure"),
    Output("risk-regime-graph", "figure"),
    Input("monitor-state-store", "data"),
)
def render_figures(state: dict[str, Any] | None) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    if not state:
        loading = empty_figure("Loading", "Loading dashboard state...")
        return loading, loading, loading, loading
    return (
        build_spot_figure(state),
        build_indexed_figure(state),
        build_correlation_figure(state),
        build_risk_figure(state),
    )


@mcp_enabled(name="get_public_macro_monitor_snapshot", expose_docstring=True)
def get_public_macro_monitor_snapshot(
    pair: str = DEFAULT_PAIR,
    window_key: str = DEFAULT_WINDOW,
    compare_pair: str | None = "GBP_USD",
) -> dict[str, Any]:
    """Return a compact FX spot, risk, and comparison summary."""
    safe_pair = sanitize_pair(pair)
    safe_window = sanitize_window(window_key)
    safe_compare = sanitize_compare_pairs(safe_pair, [compare_pair] if compare_pair else None)
    state = build_monitor_state(safe_pair, safe_compare, safe_window)
    metrics = state["metrics"]
    return {
        "summary": state["summary"],
        "pair": metrics.get("pair_label"),
        "window": metrics.get("window_label"),
        "latest": metrics.get("latest"),
        "latest_date": metrics.get("latest_date"),
        "window_return_pct": metrics.get("window_return_pct"),
        "annualized_vol_pct": metrics.get("annualized_vol_pct"),
        "risk_regime": metrics.get("risk_regime"),
        "compare_pairs": metrics.get("compare_labels"),
        "observations": metrics.get("observations"),
        "source": metrics.get("source"),
        "api_key_configured": metrics.get("api_key_configured"),
        "updated_at": state.get("updated_at"),
    }


if __name__ == "__main__":
    app.run(
        debug=os.getenv("DASH_DEBUG", "0").lower() in {"1", "true", "yes"},
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8050")),
    )
