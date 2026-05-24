"""
FXMacroData × Freqtrade — Macro Signal Strategy
=================================================
A Freqtrade strategy that uses US macroeconomic data from FXMacroData to
trade BTC/USDT on a daily timeframe.

Signal logic
------------
USD real policy rate = Fed Funds Rate (%) − CPI Inflation (%)

  Negative real rate  → monetary conditions loose → risk-on → LONG BTC/USDT
  Positive real rate  → monetary conditions tight → risk-off → EXIT long

All data used is **free** — no API key required:
  /v1/announcements/usd/policy_rate   — Fed Funds Rate (%)
  /v1/announcements/usd/inflation     — CPI Inflation YoY (%)

Setup
-----
1. Copy ``fxmacrodata_ft.py`` into the same directory as this file
   (or install via ``pip install requests pandas``).

2. Place this file in your Freqtrade ``user_data/strategies/`` folder.

3. Run backtests:
       freqtrade backtesting \\
           --strategy MacroSignalStrategy \\
           --timeframe 1d \\
           --timerange 20200101-20251231 \\
           --pair BTC/USDT

4. Live / dry-run:
       freqtrade trade --strategy MacroSignalStrategy --dry-run

Optional: set a Professional API key for all 18 currencies:
       export FXMACRODATA_API_KEY=your_key_here
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
from freqtrade.strategy import IStrategy

# ── FXMacroData helpers ────────────────────────────────────────────────────────
# Place fxmacrodata_ft.py alongside this strategy file or anywhere on sys.path.
from fxmacrodata_ft import fetch_indicator, merge_macro

logger = logging.getLogger(__name__)

# ─── Strategy ────────────────────────────────────────────────────────────────


class MacroSignalStrategy(IStrategy):
    """
    Macro-driven BTC/USDT strategy powered by FXMacroData.

    Signal: USD real policy rate (Fed Funds Rate − CPI Inflation).

    - Real rate < −dead_band  → monetary policy loose → long BTC/USDT
    - Real rate > +dead_band  → monetary policy tight → exit long

    The macro series are fetched once on startup and reused across all
    ``populate_indicators`` calls (both backtesting and live trading).
    Call ``reload_macro()`` from the Freqtrade RPC interface or restart
    the bot to refresh the series in live trading.

    Parameters
    ----------
    dead_band : float
        Minimum absolute real-rate threshold (percentage points) required to
        generate a signal.  Prevents whipsawing near zero.  Default 0.5 pp.
    macro_lookback_years : int
        How many years of macro history to pre-load.  Default 5.
    """

    INTERFACE_VERSION = 3

    # ── Strategy config ───────────────────────────────────────────────────────

    # Minimal ROI — hold until a signal-based exit
    minimal_roi = {"0": 100}

    # Stoploss — 15 % hard stop
    stoploss = -0.15

    trailing_stop = False

    # Daily candles — macro releases are daily at best
    timeframe = "1d"

    # Freqtrade requires at least this many candles before trading
    startup_candle_count: int = 30

    # Long-only (no shorting in basic Freqtrade config)
    can_short = False

    # ── Tunable parameters ────────────────────────────────────────────────────

    # Dead-band: ignore real-rate signals within ±0.5 pp of zero
    dead_band: float = 0.5

    # Years of macro history to pre-load
    macro_lookback_years: int = 5

    # ── Internal state ────────────────────────────────────────────────────────

    _usd_policy_rate: Optional[pd.DataFrame] = None
    _usd_inflation: Optional[pd.DataFrame] = None

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._api_key: Optional[str] = os.environ.get("FXMACRODATA_API_KEY")
        self._load_macro_data()

    def _macro_date_range(self) -> tuple[str, str]:
        """Return (start, end) strings for the macro data fetch window."""
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=365 * self.macro_lookback_years)
        return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")

    def _load_macro_data(self) -> None:
        """Fetch and cache USD macro indicator series from FXMacroData."""
        start, end = self._macro_date_range()

        logger.info(
            "FXMacroData: fetching USD/policy_rate and USD/inflation (%s → %s)…",
            start,
            end,
        )

        try:
            self._usd_policy_rate = fetch_indicator(
                "USD", "policy_rate", start, end, api_key=self._api_key
            )
            logger.info(
                "FXMacroData: policy_rate loaded (%d rows)", len(self._usd_policy_rate)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("FXMacroData: could not load USD/policy_rate: %s", exc)

        try:
            self._usd_inflation = fetch_indicator(
                "USD", "inflation", start, end, api_key=self._api_key
            )
            logger.info(
                "FXMacroData: inflation loaded (%d rows)", len(self._usd_inflation)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("FXMacroData: could not load USD/inflation: %s", exc)

    def reload_macro(self) -> None:
        """
        Re-fetch macro data from FXMacroData.

        Call this to refresh the cached series without restarting the bot.
        Useful after a new CPI or FOMC release in live trading.

        Example (from a Python console with RPC access)::

            strategy.reload_macro()
        """
        self._load_macro_data()

    # ── Freqtrade hooks ───────────────────────────────────────────────────────

    def populate_indicators(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Merge USD macro signals onto the OHLCV DataFrame.

        Added columns
        -------------
        macro_policy_rate  : forward-filled Fed Funds Rate (%)
        macro_inflation    : forward-filled CPI Inflation YoY (%)
        macro_real_rate    : policy_rate − inflation (real rate, pp)
        """
        if self._usd_policy_rate is not None:
            dataframe = merge_macro(
                dataframe, self._usd_policy_rate, "macro_policy_rate"
            )
        else:
            dataframe["macro_policy_rate"] = float("nan")

        if self._usd_inflation is not None:
            dataframe = merge_macro(dataframe, self._usd_inflation, "macro_inflation")
        else:
            dataframe["macro_inflation"] = float("nan")

        # Real policy rate = nominal rate minus inflation
        dataframe["macro_real_rate"] = (
            dataframe["macro_policy_rate"] - dataframe["macro_inflation"]
        )

        return dataframe

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Long BTC/USDT when USD real rate is sufficiently negative.

        Negative real rates indicate loose monetary conditions — historically
        associated with risk-on behaviour and crypto strength.
        """
        dataframe.loc[
            (dataframe["macro_real_rate"] < -self.dead_band)
            & dataframe["macro_real_rate"].notna()
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Exit long when USD real rate turns sufficiently positive.

        Positive real rates indicate tight monetary conditions — historically
        associated with risk-off behaviour and crypto weakness.
        """
        dataframe.loc[
            (dataframe["macro_real_rate"] > self.dead_band)
            & dataframe["macro_real_rate"].notna(),
            "exit_long",
        ] = 1
        return dataframe
