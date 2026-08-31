#!/usr/bin/env python3
"""
FXMacroData × CCXT — Carry Trade Scanner
==========================================
Uses the FXMacroData CCXT adapter to run a macro-driven carry-trade
scanner over EUR/USD and GBP/USD, driven by USD CPI inflation momentum.

Data used in this demo:
  - EUR/USD and GBP/USD daily spot rates  (/v1/forex/, API key required)
  - USD CPI inflation                     (/v1/announcements/usd/inflation, free)
  - USD policy rate                       (/v1/announcements/usd/policy_rate, free)
  - XAU/USD (gold) daily spot             (/v1/commodities/gold, API key required)

The free USD announcement endpoints cover the most recent 90 days.

Strategy logic
--------------
This script is a **scanner**, not a backtester — it analyses the current
macro environment and prints a forward-looking carry signal:

1. Compute the USD real policy rate (policy_rate − inflation).
2. Compare recent EUR/USD momentum (last close vs 20-day average).
3. Combine into a composite signal:

     real_rate > +1 pp  → USD attractive → signal SELL EUR/USD
     real_rate < -1 pp  → USD expensive  → signal BUY  EUR/USD
     otherwise          → signal FLAT

4. Print a summary table of major FX and gold rates alongside the signal.

Run
---
    python example.py
    python example.py --lookback 90 --no-gold
    python example.py --api-key YOUR_KEY      # unlock protected endpoints
"""
from __future__ import annotations

import argparse
import datetime
import math
import sys
from typing import Optional

import pandas as pd

from fxmacrodata_ccxt import fxmacrodata

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _indicator_series(rows: list[dict]) -> pd.Series:
    """
    Convert a list of ``{date, val}`` dicts to a forward-filled daily Series.

    Monthly releases are forward-filled so every business day carries the
    most recently released value.
    """
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["date"])
    series = df["val"].sort_index()

    today = datetime.date.today().isoformat()
    full_idx = pd.bdate_range(start=series.index[0], end=today)
    return series.reindex(full_idx).ffill()


def _ohlcv_to_series(ohlcv: list[list]) -> pd.Series:
    """Convert CCXT OHLCV rows to a close-only daily pandas Series."""
    idx = pd.to_datetime(
        [
            datetime.datetime.fromtimestamp(row[0] / 1000, tz=datetime.timezone.utc)
            .date()
            .isoformat()
            for row in ohlcv
        ]
    )
    vals = [row[4] for row in ohlcv]  # close
    return pd.Series(vals, index=idx, name="close")


def _fmt_pct(val: Optional[float], digits: int = 2) -> str:
    if val is None or math.isnan(val):
        return "  n/a"
    return f"{val:+.{digits}f}%"


def _fmt_rate(val: Optional[float], digits: int = 5) -> str:
    if val is None or math.isnan(val):
        return "  n/a"
    return f"{val:.{digits}f}"


# ─── Main ─────────────────────────────────────────────────────────────────────


def run_scanner(
    lookback: int = 60,
    show_gold: bool = True,
    api_key: Optional[str] = None,
) -> None:
    """
    Fetch data via the CCXT adapter, compute macro signals, and print results.

    Parameters
    ----------
    lookback :
        Number of calendar days of FX data to fetch (default 60).
    show_gold :
        Include XAU/USD (gold) in the rates table.
    api_key :
        FXMacroData Professional API key.  Not required for the default demo.
    """
    _banner()

    cfg = {"apiKey": api_key} if api_key else {}
    exchange = fxmacrodata(cfg)

    today = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=lookback)).isoformat()
    macro_start = "2022-01-01"  # wide window for forward-fill accuracy

    # ── 1.  Load markets ─────────────────────────────────────────────────────
    print("Loading markets…")
    markets = exchange.load_markets()
    fx_symbols = [m["symbol"] for m in markets.values() if m["info"]["type"] == "forex"]
    comm_symbols = [
        m["symbol"] for m in markets.values() if m["info"]["type"] == "commodity"
    ]
    print(f"  {len(fx_symbols)} FX pairs  |  {len(comm_symbols)} commodity pairs\n")

    # ── 2.  Current FX rates (standard CCXT fetch_tickers) ───────────────────
    scan_pairs = ["EUR/USD", "GBP/USD", "AUD/USD", "USD/JPY", "USD/CHF", "USD/CAD"]
    if show_gold:
        scan_pairs.append("XAU/USD")

    print(f"Fetching current rates for {len(scan_pairs)} symbols…")
    tickers = exchange.fetch_tickers(scan_pairs)

    # ── 3.  EUR/USD historical OHLCV (standard CCXT fetch_ohlcv) ─────────────
    print("Fetching EUR/USD OHLCV…")
    eurusd_since = int(
        datetime.datetime(
            *map(int, start.split("-")),
            tzinfo=datetime.timezone.utc,
        ).timestamp()
        * 1000
    )
    eurusd_ohlcv = exchange.fetch_ohlcv("EUR/USD", "1d", since=eurusd_since)
    eurusd = _ohlcv_to_series(eurusd_ohlcv)

    # ── 4.  Macro indicators (custom extension) ───────────────────────────────
    print("Fetching USD CPI inflation…")
    infl_rows = exchange.fetch_macro_indicator("USD", "inflation", macro_start, today)
    inflation = _indicator_series(infl_rows)

    print("Fetching USD policy rate…")
    rate_rows = exchange.fetch_macro_indicator("USD", "policy_rate", macro_start, today)
    policy_rate = _indicator_series(rate_rows)

    # ── 5.  Signal calculation ────────────────────────────────────────────────
    latest_infl = float(inflation.dropna().iloc[-1])
    latest_rate = float(policy_rate.dropna().iloc[-1])
    real_rate = latest_rate - latest_infl

    eurusd_now = float(eurusd.iloc[-1])
    eurusd_ma20 = float(eurusd.tail(20).mean()) if len(eurusd) >= 20 else eurusd_now
    fx_momentum = (eurusd_now / eurusd_ma20 - 1.0) * 100.0  # % above/below 20d MA

    if real_rate > 1.0:
        signal = "SELL EUR/USD"
        signal_icon = "↓"
        rationale = "USD real rate attractive → USD bullish"
    elif real_rate < -1.0:
        signal = "BUY  EUR/USD"
        signal_icon = "↑"
        rationale = "USD real rate negative → USD bearish"
    else:
        signal = "FLAT"
        signal_icon = "→"
        rationale = "Real rate within neutral band (±1 pp)"

    # ── 6.  Output ────────────────────────────────────────────────────────────
    _print_rates(tickers, scan_pairs)
    _print_macro(
        latest_infl, latest_rate, real_rate, fx_momentum, inflation, policy_rate
    )
    _print_signal(signal, signal_icon, rationale)


# ─── Formatting helpers ───────────────────────────────────────────────────────


def _banner() -> None:
    print()
    print("FXMacroData × CCXT — Macro Carry Scanner")
    print("─" * 56)
    print("  All data via standard CCXT interface")
    print("  EUR/USD, GBP/USD, XAU/USD  ·  USD inflation & policy rate")
    print("  USD announcements free for 90 days; FX and gold need an API key")
    print()


def _print_rates(tickers: dict, symbols: list[str]) -> None:
    print()
    print("─" * 56)
    print(f"  {'Symbol':<12}  {'Last rate':>12}  {'1d change':>10}")
    print("─" * 56)
    for sym in symbols:
        t = tickers.get(sym)
        if not t:
            continue
        last = _fmt_rate(t["last"])
        chg = _fmt_pct(t["percentage"])
        print(f"  {sym:<12}  {last:>12}  {chg:>10}")
    print("─" * 56)


def _print_macro(
    inflation: float,
    policy_rate: float,
    real_rate: float,
    fx_momentum: float,
    infl_series: "pd.Series",
    rate_series: "pd.Series",
) -> None:
    # 3-month inflation change (≈ 66 business days)
    infl_clean = infl_series.dropna()
    infl_3m_delta: Optional[float] = None
    if len(infl_clean) >= 66:
        infl_3m_delta = float(infl_clean.iloc[-1]) - float(infl_clean.iloc[-66])

    # Rate direction
    rate_clean = rate_series.dropna()
    rate_6m_delta: Optional[float] = None
    if len(rate_clean) >= 132:
        rate_6m_delta = float(rate_clean.iloc[-1]) - float(rate_clean.iloc[-132])

    print()
    print("  Macro snapshot (USD, latest released values)")
    print("─" * 56)
    print(f"  CPI inflation (YoY)      : {inflation:>7.2f} %")
    if infl_3m_delta is not None:
        print(f"  Inflation 3m momentum    : {infl_3m_delta:>+7.2f} pp")
    print(f"  Fed policy rate          : {policy_rate:>7.2f} %")
    if rate_6m_delta is not None:
        print(f"  Rate 6m change           : {rate_6m_delta:>+7.2f} pp")
    print(f"  USD real rate (rate-CPI) : {real_rate:>+7.2f} pp")
    print(f"  EUR/USD vs 20d MA        : {fx_momentum:>+7.2f} %")
    print("─" * 56)


def _print_signal(signal: str, icon: str, rationale: str) -> None:
    print()
    print(f"  Signal  {icon}  {signal}")
    print(f"  Why       {rationale}")
    print()
    print("  Note: this is a macro scanner, not a backtested strategy.")
    print("  For full backtesting, see the Backtrader and Zipline examples.")
    print(f"  Docs & Pro key → https://fxmacrodata.com/api-management")
    print()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "FXMacroData × CCXT — Macro Carry Scanner\n"
            "Fetch FX and macro data via the CCXT interface and compute a\n"
            "USD carry signal for EUR/USD."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--lookback",
        default=60,
        type=int,
        help="Calendar days of FX history to fetch (default: 60)",
    )
    p.add_argument(
        "--no-gold",
        action="store_true",
        help="Exclude XAU/USD from the rates table",
    )
    p.add_argument(
        "--api-key",
        default=None,
        dest="api_key",
        help=(
            "FXMacroData API key (required for FX spot rates and commodities)"
        ),
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _cli()
    try:
        run_scanner(
            lookback=args.lookback,
            show_gold=not args.no_gold,
            api_key=args.api_key,
        )
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
