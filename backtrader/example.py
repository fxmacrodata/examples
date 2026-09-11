#!/usr/bin/env python3
"""
FXMacroData — Backtrader Example
==================================
Inflation Signal Strategy: trade EUR/USD based on the month-over-month
direction of US CPI inflation.

Data used in this demo:
  - /v1/forex/eur/usd                  — EUR/USD daily spot rates (API key required)
  - /v1/announcements/usd/inflation    — US CPI Inflation (YoY %), free for
                                         the most recent 90 days

Strategy logic
--------------
The monthly CPI reading is forward-filled to a business-day daily cadence.
Three-month momentum on the inflation series drives the signal:

  - Inflation over the past 3 months is **rising** → Fed likely hawkish
    → USD bullish → **SELL** EUR/USD

  - Inflation over the past 3 months is **falling** → Fed likely dovish
    → USD bearish → **BUY** EUR/USD

Positions are closed when the signal reverses.

Run
---
    python example.py
    python example.py --start 2024-06-01 --no-plot
    python example.py --api-key YOUR_KEY      # unlock protected non-USD announcements and commodities
"""
from __future__ import annotations

import argparse
import datetime
import math
import sys
from typing import Optional

import backtrader as bt
import backtrader.analyzers as btanalyzers

from fxmacrodata_bt import load_forex, load_indicator

# ─── Strategy ────────────────────────────────────────────────────────────────


class InflationSignalStrategy(bt.Strategy):
    """
    Macro-driven EUR/USD strategy using US CPI inflation as a signal.

    Data feeds expected (by index):
      0 → FXSpotData         : EUR/USD daily spot rates
      1 → MacroIndicatorData : USD CPI inflation, YoY % (forward-filled daily)

    Signal: 3-month momentum on the inflation series
    -------
    ``inflation_now`` vs ``inflation_66d_ago`` (≈ 3 months of trading days):

      Rising  (now > ago + threshold) → hawkish bias → **short** EUR/USD
      Falling (now < ago − threshold) → dovish bias  → **long**  EUR/USD

    Positions are closed when the opposite signal triggers.

    Parameters
    ----------
    lookback : int
        Number of business days for the momentum lookback (default 66 ≈ 3M).
    threshold : float
        Minimum absolute change in inflation (pp) required to generate a
        signal (default 0.1 pp).  Helps avoid whipsawing on tiny revisions.
    trade_usd : float
        USD-denominated trade size per position (default 10 000).
    verbose : bool
        Whether to print signal / order / trade logs.
    """

    params = (
        ("lookback", 66),  # ≈ 3 months of business days
        ("threshold", 0.10),  # minimum pp change to trigger a signal
        ("trade_usd", 10_000),  # USD value per trade
        ("verbose", True),
    )

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self.fx = self.datas[0]  # EUR/USD price feed
        self.infl = self.datas[1]  # USD inflation feed (forward-filled)

        # EMA on EUR/USD for chart context only
        self.fx_ema = bt.indicators.EMA(
            self.fx.close,
            period=20,
            plotname="EMA-20",
        )

        self.order: Optional[bt.Order] = None

    # ── Logging ───────────────────────────────────────────────────────────────

    def log(self, msg: str, dt: Optional[datetime.date] = None) -> None:
        if self.p.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            print(f"{dt}  {msg}")

    # ── Order / trade notifications ────────────────────────────────────────────

    def notify_order(self, order: bt.Order) -> None:
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status == order.Completed:
            side = "BUY " if order.isbuy() else "SELL"
            self.log(
                f"{side}  {self.fx._name}  "
                f"price={order.executed.price:.5f}  "
                f"size={order.executed.size:.0f}  "
                f"cost={order.executed.value:.2f}  "
                f"comm={order.executed.comm:.4f}"
            )
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"Order {order.Status[order.status]}")
        self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        if trade.isclosed:
            self.log(f"CLOSED  pnl={trade.pnl:.2f}  pnlcomm={trade.pnlcomm:.2f}")

    # ── Strategy logic ────────────────────────────────────────────────────────

    def next(self) -> None:
        if self.order:
            return  # wait for pending order to settle

        # Need lookback bars of macro data before generating signals
        if len(self.infl) <= self.p.lookback:
            return

        infl_now = self.infl.close[0]
        infl_ago = self.infl.close[-self.p.lookback]

        if math.isnan(infl_now) or math.isnan(infl_ago):
            return  # macro data not yet available (before first release)

        delta = infl_now - infl_ago
        fx_price = self.fx.close[0]
        size = max(1, int(self.p.trade_usd / fx_price))

        if not self.position:
            if delta > self.p.threshold:
                # Inflation rising → hawkish bias → short EUR/USD
                self.log(
                    f"SIGNAL HAWKISH  infl={infl_now:.2f}%  "
                    f"3m_delta={delta:+.2f}pp  "
                    f"→ SHORT EUR/USD @ {fx_price:.5f}"
                )
                self.order = self.sell(size=size)
            elif delta < -self.p.threshold:
                # Inflation falling → dovish bias → long EUR/USD
                self.log(
                    f"SIGNAL DOVISH   infl={infl_now:.2f}%  "
                    f"3m_delta={delta:+.2f}pp  "
                    f"→ LONG  EUR/USD @ {fx_price:.5f}"
                )
                self.order = self.buy(size=size)
        else:
            # Close on reverse signal
            if self.position.size < 0 and delta < -self.p.threshold:
                self.log(f"REVERSE → LONG  infl={infl_now:.2f}%  delta={delta:+.2f}pp")
                self.order = self.close()
            elif self.position.size > 0 and delta > self.p.threshold:
                self.log(f"REVERSE → SHORT infl={infl_now:.2f}%  delta={delta:+.2f}pp")
                self.order = self.close()

    def stop(self) -> None:
        self.log(
            f"=== Backtest complete.  "
            f"Final value: ${self.broker.getvalue():,.2f} ===",
            dt=self.datas[0].datetime.date(0),
        )


# ─── Backtest runner ─────────────────────────────────────────────────────────


def run_backtest(
    start: str = "2024-06-01",
    end: Optional[str] = None,
    initial_cash: float = 100_000.0,
    api_key: Optional[str] = None,
    plot: bool = True,
) -> None:
    """
    Set up Cerebro, load FXMacroData feeds, run the strategy, and print results.

    Parameters
    ----------
    start :
        Backtest start date (``"YYYY-MM-DD"``).  Defaults to 2024-06-01.
        The inflation feed loads from ``start`` to ensure the 3-month
        momentum window is populated from the first available forex bar.
    end :
        Backtest end date (``"YYYY-MM-DD"``).  Defaults to today.
    initial_cash :
        Starting portfolio value in USD.
    api_key :
        FXMacroData Professional API key (not required for free USD data).
    plot :
        If ``True``, display the Backtrader chart after the run.
        Pass ``--no-plot`` on the command line to suppress the chart.
    """
    end = end or datetime.date.today().isoformat()

    _banner(start, end, initial_cash)

    # ── Fetch data ─────────────────────────────────────────────────────────────
    print("Fetching EUR/USD spot rates from FXMacroData…")
    fx_feed = load_forex("EUR", "USD", start, end, api_key=api_key)

    # Load inflation from slightly before start so the lookback window is warm
    infl_start = (
        datetime.date.fromisoformat(start)
        - datetime.timedelta(days=130)  # ≈ 6 months back to fill lookback
    ).isoformat()
    print("Fetching USD CPI inflation from FXMacroData…")
    infl_feed = load_indicator(
        "USD",
        "inflation",
        infl_start,
        end,
        api_key=api_key,
    )

    # ── Cerebro setup ─────────────────────────────────────────────────────────
    cerebro = bt.Cerebro()

    cerebro.adddata(fx_feed, name="EURUSD")
    cerebro.adddata(infl_feed, name="USD_inflation")

    cerebro.addstrategy(InflationSignalStrategy)

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.00015)  # ≈ 1.5 pip spread

    # Standard analyzers
    cerebro.addanalyzer(
        btanalyzers.SharpeRatio,
        _name="sharpe",
        riskfreerate=0.04,
        annualize=True,
        timeframe=bt.TimeFrame.Days,
    )
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(
        btanalyzers.Returns, _name="returns", timeframe=bt.TimeFrame.Years
    )
    cerebro.addanalyzer(btanalyzers.TradeAnalyzer, _name="trades")

    # ── Run ───────────────────────────────────────────────────────────────────
    print(f"\nStarting portfolio value: ${cerebro.broker.getvalue():,.2f}\n")
    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    total_return = (final_value / initial_cash - 1.0) * 100.0

    # ── Print results ─────────────────────────────────────────────────────────
    _print_results(strat, final_value, total_return)

    # ── Chart ─────────────────────────────────────────────────────────────────
    if plot:
        try:
            cerebro.plot(style="line", iplot=False, numfigs=1)
        except Exception as exc:
            print(f"\nNote: chart unavailable ({exc}).")
            print("Run with --no-plot to suppress this message.")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _banner(start: str, end: str, cash: float) -> None:
    print()
    print("FXMacroData × Backtrader — Inflation Signal Strategy")
    print("─" * 62)
    print(f"  Period         : {start} → {end}")
    print(f"  Initial cash   : ${cash:,.0f}")
    print(f"  Instrument     : EUR/USD spot")
    print(f"  Signal         : USD CPI inflation 3-month momentum (free data)")
    print(f"  Commission     : ≈ 1.5 pip spread")
    print()


def _print_results(strat, final_value: float, total_return: float) -> None:
    print()
    print("─" * 62)
    print("RESULTS")
    print("─" * 62)
    print(f"  Final portfolio value  : ${final_value:>12,.2f}")
    print(f"  Total return           : {total_return:>+11.2f}%")

    sharpe_dict = strat.analyzers.sharpe.get_analysis()
    drawdown_dict = strat.analyzers.drawdown.get_analysis()
    trade_dict = strat.analyzers.trades.get_analysis()

    sharpe_val = sharpe_dict.get("sharperatio")
    if sharpe_val is not None:
        print(f"  Sharpe ratio           : {sharpe_val:>12.3f}")

    max_dd = drawdown_dict.get("max", {}).get("drawdown", 0.0)
    print(f"  Max drawdown           : {max_dd:>11.2f}%")

    try:
        total = trade_dict.total.closed
        print(f"  Total closed trades    : {total:>12}")
        if total:
            won = trade_dict.won.total
            win_rate = won / total * 100
            avg_pnl = trade_dict.pnl.net.total / total
            print(f"  Win rate               : {win_rate:>11.1f}%")
            print(f"  Avg net P&L per trade  : ${avg_pnl:>11.2f}")
    except (AttributeError, ZeroDivisionError):
        pass

    print("─" * 62)
    print()


# ─── CLI entry point ─────────────────────────────────────────────────────────


def _cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "FXMacroData × Backtrader — Inflation Signal Strategy\n"
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
        help="FXMacroData API key (required for FX spot rates and commodities)",
    )
    p.add_argument(
        "--no-plot",
        action="store_true",
        help="Suppress the Backtrader chart window",
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
            plot=not args.no_plot,
        )
    except PermissionError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
