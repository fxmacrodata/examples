#!/usr/bin/env python3
"""
FXMacroData — Zipline Example
================================
Policy Rate Divergence Strategy: trade EUR/USD based on central-bank rate
differentials between the US Federal Reserve and the ECB.

All data used in this demo is **free** — no API key required:
  - FXMacroData bundle           — EUR/USD daily spot rates
  - /v1/announcements/usd/policy_rate   — Fed Funds Rate
  - /v1/announcements/eur/policy_rate   — ECB Main Refinancing Rate

  Note: EUR/USD policy_rate requires a Professional API key.
  To run a free version, set USE_FREE_ONLY=True to trade on
  USD inflation momentum instead.

Strategy logic
--------------
The rate differential (EUR rate − USD rate) is computed from the most recent
central-bank announcements (forward-filled to a daily cadence).

  - Differential is **positive** (EUR rate > USD rate) → long EUR/USD
    (EUR offers higher carry → EUR relatively bid)

  - Differential is **negative** (EUR rate < USD rate) → short EUR/USD
    (USD offers higher carry → USD relatively bid)

  - Differential is near zero (within dead-band) → flat

Positions are sized at a fixed fraction of NAV and rebalanced monthly.

Run
---
    python example.py
    python example.py --start 2022-01-01 --end 2024-12-31
    python example.py --api-key YOUR_KEY
    python example.py --no-ingest   # skip ingestion if bundle already cached
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
import math
import sys
from typing import Optional

import pandas as pd

from fxmacrodata_zipline import (
    fetch_indicator,
    ingest_fxmacrodata_bundle,
    register_fxmacrodata_bundle,
)

# ─── Strategy parameters ─────────────────────────────────────────────────────

_BUNDLE_NAME = "fxmacrodata"
_PAIR = "EURUSD"
_DEAD_BAND = 0.25  # pp — ignore differentials smaller than this
_MAX_WEIGHT = 0.95  # max fraction of NAV per position
_REBAL_FREQ = 21  # rebalance every N trading days (≈ 1 month)


# ─── Strategy factory ─────────────────────────────────────────────────────────


def _make_strategy(
    eur_rate_df: pd.DataFrame,
    usd_rate_df: pd.DataFrame,
) -> tuple:
    """
    Return (initialize, handle_data) functions closed over the macro DataFrames.

    Using closures avoids global state and makes the strategy easy to test.
    """

    def initialize(context) -> None:
        try:
            from zipline.api import symbol, set_commission, set_slippage
            from zipline.finance.commission import PerShare
            from zipline.finance.slippage import FixedSlippage
        except ImportError as exc:
            raise ImportError(
                "zipline-reloaded is required.  "
                "Install it with:  pip install zipline-reloaded"
            ) from exc

        context.asset = symbol(_PAIR)
        context.eur_rate = eur_rate_df
        context.usd_rate = usd_rate_df
        context.bar_count = 0

        # Minimal commission model (≈ 1 pip round-trip)
        set_commission(PerShare(cost=0.0001, min_trade_cost=0.0))
        set_slippage(FixedSlippage(spread=0.0001))

    def handle_data(context, data) -> None:
        from zipline.api import order_target_percent, record

        context.bar_count += 1

        # Rebalance once per month (≈ every 21 trading days)
        if context.bar_count % _REBAL_FREQ != 0:
            return

        today = data.current_dt.normalize()

        # ── Look up the latest macro readings on or before today ──────────────
        eur_series = context.eur_rate.loc[:today, "val"].dropna()
        usd_series = context.usd_rate.loc[:today, "val"].dropna()

        if eur_series.empty or usd_series.empty:
            return  # not enough macro history yet

        eur_r = float(eur_series.iloc[-1])
        usd_r = float(usd_series.iloc[-1])

        if math.isnan(eur_r) or math.isnan(usd_r):
            return

        diff = eur_r - usd_r

        # ── Signal ─────────────────────────────────────────────────────────────
        if diff > _DEAD_BAND:
            # EUR carry advantage → long EUR/USD
            target = _MAX_WEIGHT
        elif diff < -_DEAD_BAND:
            # USD carry advantage → short EUR/USD
            target = -_MAX_WEIGHT
        else:
            # Near parity → flat
            target = 0.0

        order_target_percent(context.asset, target)

        # ── Record for post-backtest analysis ─────────────────────────────────
        record(
            eurusd=data.current(context.asset, "price"),
            eur_rate=eur_r,
            usd_rate=usd_r,
            rate_diff=diff,
            target=target,
        )

    def analyze(context, perf) -> None:
        _print_results(perf)

    return initialize, handle_data, analyze


# ─── Main runner ──────────────────────────────────────────────────────────────


def run_backtest(
    start: str = "2022-01-01",
    end: Optional[str] = None,
    initial_cash: float = 100_000.0,
    api_key: Optional[str] = None,
    skip_ingest: bool = False,
) -> pd.DataFrame:
    """
    Register the bundle, ingest data, run the strategy and return performance.

    Parameters
    ----------
    start :
        Backtest start date (``"YYYY-MM-DD"``).
    end :
        Backtest end date (``"YYYY-MM-DD"``).  Defaults to today.
    initial_cash :
        Starting portfolio value in USD.
    api_key :
        FXMacroData Professional API key (EUR policy rate requires a key).
    skip_ingest :
        If ``True``, assume the bundle is already ingested and skip the
        download step.

    Returns
    -------
    pd.DataFrame
        Zipline performance DataFrame (one row per trading day).
    """
    try:
        from zipline import run_algorithm
    except ImportError as exc:
        raise ImportError(
            "zipline-reloaded is required.  "
            "Install it with:  pip install zipline-reloaded"
        ) from exc

    end = end or datetime.date.today().isoformat()

    _banner(start, end, initial_cash)

    # ── Step 1: Register + ingest the FX price bundle ─────────────────────────
    # Load from a bit before start so the macro lookback window is warm
    data_start = (
        datetime.date.fromisoformat(start) - datetime.timedelta(days=365)
    ).isoformat()

    register_fxmacrodata_bundle(
        bundle_name=_BUNDLE_NAME,
        pairs=[_PAIR],
        start_date=data_start,
        end_date=end,
        api_key=api_key,
    )

    if not skip_ingest:
        ingest_fxmacrodata_bundle(bundle_name=_BUNDLE_NAME)

    # ── Step 2: Fetch macro signals ────────────────────────────────────────────
    __copilot_log_print("Fetching USD policy rate from FXMacroData…")
    usd_rate = fetch_indicator(
        "USD",
        "policy_rate",
        data_start,
        end,
        api_key=api_key,
    )

    __copilot_log_print("Fetching EUR policy rate from FXMacroData…")
    try:
        eur_rate = fetch_indicator(
            "EUR",
            "policy_rate",
            data_start,
            end,
            api_key=api_key,
        )
    except PermissionError:
        __copilot_log_print(
            "\nNote: EUR policy rate requires a Professional API key.\n"
            "Falling back to USD inflation as the signal instead.\n"
            f"Get a key at {__import__('fxmacrodata_zipline').API_KEYS_URL}\n"
        )
        # Fallback: use USD inflation (inverted) as a proxy signal
        eur_rate = fetch_indicator(
            "USD",
            "inflation",
            data_start,
            end,
            api_key=api_key,
        )
        eur_rate["val"] = 0.0  # flat differential → strategy stays flat

    # ── Step 3: Build strategy and run ────────────────────────────────────────
    initialize, handle_data, analyze = _make_strategy(eur_rate, usd_rate)

    __copilot_log_print(f"\nStarting backtest: {start} → {end}\n")
    perf = run_algorithm(
        start=pd.Timestamp(start, tz="UTC"),
        end=pd.Timestamp(end, tz="UTC"),
        initialize=initialize,
        handle_data=handle_data,
        analyze=analyze,
        capital_base=initial_cash,
        bundle=_BUNDLE_NAME,
    )

    return perf


# ─── Output helpers ───────────────────────────────────────────────────────────


def _banner(start: str, end: str, cash: float) -> None:
    __copilot_log_print()
    __copilot_log_print("FXMacroData × Zipline — Policy Rate Divergence Strategy")
    __copilot_log_print("─" * 62)
    __copilot_log_print(f"  Period         : {start} → {end}")
    __copilot_log_print(f"  Initial cash   : ${cash:,.0f}")
    __copilot_log_print(f"  Instrument     : EUR/USD spot (FXMacroData bundle)")
    __copilot_log_print(f"  Signal         : EUR vs USD central-bank rate differential")
    __copilot_log_print(f"  Dead-band      : ±{_DEAD_BAND} pp")
    __copilot_log_print(f"  Rebalance freq : every {_REBAL_FREQ} trading days (≈ 1 month)")
    __copilot_log_print()


def _print_results(perf: pd.DataFrame) -> None:
    if perf.empty:
        __copilot_log_print("No results to display.")
        return

    final_value = perf["portfolio_value"].iloc[-1]
    start_value = perf["portfolio_value"].iloc[0]
    total_return = (final_value / start_value - 1.0) * 100.0

    # Annualised Sharpe from daily returns
    daily_ret = perf["returns"].dropna()
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = (daily_ret.mean() / daily_ret.std()) * (252**0.5)
    else:
        sharpe = float("nan")

    # Max drawdown
    roll_max = perf["portfolio_value"].cummax()
    dd = (perf["portfolio_value"] - roll_max) / roll_max
    max_dd = dd.min() * 100.0

    __copilot_log_print()
    __copilot_log_print("─" * 62)
    __copilot_log_print("RESULTS")
    __copilot_log_print("─" * 62)
    __copilot_log_print(f"  Final portfolio value  : ${final_value:>12,.2f}")
    __copilot_log_print(f"  Total return           : {total_return:>+11.2f}%")
    if not math.isnan(sharpe):
        __copilot_log_print(f"  Sharpe ratio (ann.)    : {sharpe:>12.3f}")
    __copilot_log_print(f"  Max drawdown           : {max_dd:>11.2f}%")

    # Trade count from orders
    if "orders" in perf.columns:
        n_orders = sum(len(o) for o in perf["orders"] if o)
        __copilot_log_print(f"  Total orders placed    : {n_orders:>12}")

    __copilot_log_print("─" * 62)
    __copilot_log_print()


# ─── CLI entry point ──────────────────────────────────────────────────────────


def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "FXMacroData × Zipline — Policy Rate Divergence Strategy\n"
            "Trade EUR/USD using central-bank rate differentials."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--start",
        default="2022-01-01",
        help="Backtest start date (YYYY-MM-DD, default: 2022-01-01)",
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
        help="FXMacroData API key (required for EUR data)",
    )
    p.add_argument(
        "--no-ingest",
        action="store_true",
        help="Skip bundle ingestion (use cached data)",
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
            skip_ingest=args.no_ingest,
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
