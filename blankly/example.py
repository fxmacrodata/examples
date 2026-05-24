#!/usr/bin/env python3
"""
FXMacroData — Blankly Example
================================
Inflation Signal Strategy: trade EUR/USD based on the direction of
US CPI inflation using blankly's event-based backtesting engine.

All data used in this demo is **free** — no API key required:
  - /v1/forex/eur/usd                  — EUR/USD daily spot rates
  - /v1/announcements/usd/inflation    — US CPI Inflation (YoY %)

Strategy logic
--------------
The monthly CPI reading is forward-filled to a business-day daily cadence.
Three-month momentum on the inflation series drives the signal:

  - Inflation over the past 3 months is **rising** → Fed likely hawkish
    → USD bullish → **SELL** EUR/USD (short)

  - Inflation over the past 3 months is **falling** → Fed likely dovish
    → USD bearish → **BUY** EUR/USD (long)

Positions are closed when the signal reverses.

Run
---
    python example.py
    python example.py --start 2024-01-01 --end 2025-12-31
    python example.py --api-key YOUR_KEY      # unlock protected non-USD data
"""
import logging

__copilot_logger = logging.getLogger(__name__)

def __copilot_log_print(*args, sep=" ", end="\n", file=None, flush=False):
    message = sep.join(str(arg) for arg in args)
    if end and end != "\n":
        message += end.rstrip("\n")
    stream = file if file is not None else sys.stdout
    level = logging.ERROR if stream is sys.stderr else logging.INFO
    __copilot_logger.log(level, message)


from __future__ import annotations

import argparse
import datetime
import sys
from typing import Optional

from fxmacrodata_blankly import (
    create_exchange,
    fetch_indicator,
    get_macro_signal,
)

# ─── Strategy parameters ─────────────────────────────────────────────────────

_LOOKBACK_DAYS = 66  # ≈ 3 months of business days
_THRESHOLD = 0.10  # minimum pp change to trigger a signal
_TRADE_USD = 10_000  # USD value per trade


# ─── Strategy callbacks ───────────────────────────────────────────────────────


def init(symbol: str, state) -> None:
    """
    Called once per symbol before the backtest begins.

    Pre-loads the USD inflation series into ``state.variables`` so that
    ``price_event`` can access it without re-fetching on every bar.
    """
    state.variables["inflation"] = state.globals["inflation_df"]
    state.variables["owns_long"] = False
    state.variables["owns_short"] = False


def price_event(price: float, symbol: str, state) -> None:
    """
    Called once per day for the EUR-USD symbol.

    Signal: 3-month (≈ 66 business-day) momentum on the US CPI inflation
    series.

    - Rising inflation  (now > 66d_ago + threshold) → hawkish → SHORT
    - Falling inflation (now < 66d_ago − threshold) → dovish  → LONG
    - Reverse or close on opposite signal.
    """
    infl_df = state.variables["inflation"]
    owns_long = state.variables["owns_long"]
    owns_short = state.variables["owns_short"]

    infl_now = get_macro_signal(infl_df, state.time)
    # 66 trading days ≈ 13 calendar weeks; subtract from current timestamp
    ago_ts = state.time - _LOOKBACK_DAYS * 86_400
    infl_ago = get_macro_signal(infl_df, ago_ts)

    if infl_now is None or infl_ago is None:
        return  # not enough macro history yet

    delta = infl_now - infl_ago
    interface = state.interface
    size = max(1, int(_TRADE_USD / price))

    if not owns_long and not owns_short:
        if delta > _THRESHOLD:
            # Rising inflation → hawkish bias → short EUR/USD
            interface.market_order(symbol, side="sell", size=size)
            state.variables["owns_short"] = True
            state.variables["owns_long"] = False
        elif delta < -_THRESHOLD:
            # Falling inflation → dovish bias → long EUR/USD
            interface.market_order(symbol, side="buy", size=size)
            state.variables["owns_long"] = True
            state.variables["owns_short"] = False
    else:
        if owns_short and delta < -_THRESHOLD:
            # Close short → reverse to long
            interface.market_order(symbol, side="buy", size=size)  # close short
            state.variables["owns_short"] = False
        elif owns_long and delta > _THRESHOLD:
            # Close long → reverse to short
            curr = interface.account[state.base_asset].available
            if curr > 0:
                interface.market_order(symbol, side="sell", size=int(curr))
            state.variables["owns_long"] = False


# ─── Backtest runner ─────────────────────────────────────────────────────────


def run_backtest(
    start: str = "2024-06-01",
    end: Optional[str] = None,
    initial_cash: float = 100_000.0,
    api_key: Optional[str] = None,
) -> None:
    """
    Fetch FXMacroData, set up a blankly Strategy and run the backtest.

    Parameters
    ----------
    start :
        Backtest start date (``"YYYY-MM-DD"``).
    end :
        Backtest end date (``"YYYY-MM-DD"``).  Defaults to today.
    initial_cash :
        Starting portfolio value in USD.
    api_key :
        FXMacroData Professional API key (not required for free USD data).
    """
    try:
        import blankly
    except ImportError as exc:
        raise ImportError(
            "blankly is required.  Install it with:  pip install blankly"
        ) from exc

    end = end or datetime.date.today().isoformat()

    _banner(start, end, initial_cash)

    # ── Fetch data ─────────────────────────────────────────────────────────────
    # Load from a bit before start so the 3-month lookback window is warm
    data_start = (
        datetime.date.fromisoformat(start) - datetime.timedelta(days=130)
    ).isoformat()

    __copilot_log_print("Fetching EUR/USD spot rates from FXMacroData…")
    exchange = create_exchange("EUR", "USD", data_start, end, api_key=api_key)

    __copilot_log_print("Fetching USD CPI inflation from FXMacroData…")
    inflation_df = fetch_indicator("USD", "inflation", data_start, end, api_key=api_key)

    # ── Strategy setup ─────────────────────────────────────────────────────────
    strategy = blankly.Strategy(exchange)

    # Share the pre-fetched DataFrame via a globals dict so both init and
    # price_event can access it without re-fetching.
    if not hasattr(strategy, "globals"):
        strategy.globals = {}
    strategy.globals["inflation_df"] = inflation_df

    strategy.add_price_event(
        price_event,
        symbol="EUR-USD",
        resolution="1d",
        init=init,
    )

    # ── Run ────────────────────────────────────────────────────────────────────
    __copilot_log_print(f"\nStarting portfolio value: ${initial_cash:,.2f}\n")
    results = strategy.backtest(
        start_date=start,
        end_date=end,
        initial_values={"USD": initial_cash},
        GUI_output=False,
    )

    _print_results(results, initial_cash)


# ─── Output helpers ───────────────────────────────────────────────────────────


def _banner(start: str, end: str, cash: float) -> None:
    __copilot_log_print()
    __copilot_log_print("FXMacroData × Blankly — Inflation Signal Strategy")
    __copilot_log_print("─" * 62)
    __copilot_log_print(f"  Period         : {start} → {end}")
    __copilot_log_print(f"  Initial cash   : ${cash:,.0f}")
    __copilot_log_print(f"  Instrument     : EUR/USD spot")
    __copilot_log_print(f"  Signal         : USD CPI inflation 3-month momentum (free data)")
    __copilot_log_print(f"  Lookback       : {_LOOKBACK_DAYS} business days (≈ 3 months)")
    __copilot_log_print(f"  Threshold      : ±{_THRESHOLD} pp")
    __copilot_log_print()


def _print_results(results, initial_cash: float) -> None:
    import math

    __copilot_log_print()
    __copilot_log_print("─" * 62)
    __copilot_log_print("RESULTS")
    __copilot_log_print("─" * 62)

    try:
        # blankly returns a dict with a 'returns' key and a metrics DataFrame
        metrics = results.get("metrics", {})
        portfolio = results.get("user_calcs", {})

        final_value = portfolio.get("portfolio_value", initial_cash)
        total_return = (final_value / initial_cash - 1.0) * 100.0

        __copilot_log_print(f"  Final portfolio value  : ${final_value:>12,.2f}")
        __copilot_log_print(f"  Total return           : {total_return:>+11.2f}%")

        sharpe = metrics.get("sharpe", None)
        if sharpe is not None and not (
            isinstance(sharpe, float) and math.isnan(sharpe)
        ):
            __copilot_log_print(f"  Sharpe ratio           : {float(sharpe):>12.3f}")

        max_dd = metrics.get("max_drawdown", None)
        if max_dd is not None:
            __copilot_log_print(f"  Max drawdown           : {float(max_dd) * 100:>11.2f}%")

        trades = metrics.get("trades", None)
        if trades is not None:
            __copilot_log_print(f"  Total trades           : {int(trades):>12}")

    except (AttributeError, TypeError, KeyError, ValueError, ZeroDivisionError):
        # blankly result format can vary by version — print the raw object
        __copilot_log_print(f"  Raw results: {results}")

    __copilot_log_print("─" * 62)
    __copilot_log_print()


# ─── CLI entry point ─────────────────────────────────────────────────────────


def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "FXMacroData × Blankly — Inflation Signal Strategy\n"
            "Trade EUR/USD using US CPI inflation momentum (free data)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--start",
        default="2024-06-01",
        help="Backtest start date (YYYY-MM-DD, default: 2024-06-01)",
    )
    p.add_argument(
        "--end",
        default=None,
        help="Backtest end date (YYYY-MM-DD, default: today)",
    )
    p.add_argument(
        "--cash",
        default=100_000.0,
        type=float,
        help="Initial capital in USD (default: 100000)",
    )
    p.add_argument(
        "--api-key",
        default=None,
        dest="api_key",
        help="FXMacroData API key (optional — USD data is always free)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _cli()
    try:
        run_backtest(
            start=args.start,
            end=args.end,
            initial_cash=args.cash,
            api_key=args.api_key,
        )
    except PermissionError as exc:
        __copilot_log_print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        __copilot_log_print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        __copilot_log_print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
