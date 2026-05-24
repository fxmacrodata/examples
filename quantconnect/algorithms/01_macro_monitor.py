"""
FXMacroData — Macro Monitor (Example Algorithm 1)
==================================================

A beginner-friendly QuantConnect algorithm that subscribes to free-tier
USD macro indicators and logs/plots them as the backtest runs.  No API key
is needed because USD data is publicly available.

What this demonstrates
----------------------
* How to add FXMacroData custom data with ``add_data``
* How to access data via ``on_data``
* How to plot custom series in the QuantConnect charting interface
* How to gate logic on new data arrivals

Run instructions
----------------
1. Upload ``fxmacrodata/lean.py`` (and ``fxmacrodata/__init__.py``) to your
   QuantConnect project alongside this file.
2. Set the algorithm entry point to this file.
3. Press **Backtest**.  No API key is required for USD indicators.

For all other currencies set ``FXMACRODATA_API_KEY`` in the project
environment variables (Algorithm Configuration → Environment Variables).
"""

from AlgorithmImports import *

from fxmacrodata.lean import FXMacroIndicator


class MacroMonitorAlgorithm(QCAlgorithm):
    """Logs and plots USD macro indicators — free tier, no API key needed."""

    def initialize(self) -> None:
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100_000)

        # ------------------------------------------------------------------ #
        # Subscribe to USD macro indicators (free — no API key required)      #
        # Symbol format: "{CURRENCY}_{INDICATOR}"                             #
        # ------------------------------------------------------------------ #
        self._policy_rate = self.add_data(
            FXMacroIndicator, "USD_POLICY_RATE", Resolution.DAILY
        ).symbol
        self._inflation = self.add_data(
            FXMacroIndicator, "USD_INFLATION", Resolution.DAILY
        ).symbol
        self._unemployment = self.add_data(
            FXMacroIndicator, "USD_UNEMPLOYMENT", Resolution.DAILY
        ).symbol
        self._gdp = self.add_data(FXMacroIndicator, "USD_GDP", Resolution.DAILY).symbol

        # ------------------------------------------------------------------ #
        # Custom charts                                                        #
        # ------------------------------------------------------------------ #
        self._chart_macro = Chart("USD Macro Indicators")
        self._chart_macro.add_series(Series("Policy Rate (%)", SeriesType.LINE, 0))
        self._chart_macro.add_series(Series("Inflation (% YoY)", SeriesType.LINE, 1))
        self._chart_macro.add_series(Series("Unemployment (%)", SeriesType.LINE, 2))
        self._chart_macro.add_series(Series("GDP (% YoY)", SeriesType.LINE, 3))
        self.add_chart(self._chart_macro)

        # Track latest values for logging
        self._latest: dict = {}

    # ---------------------------------------------------------------------- #
    # Data handler                                                             #
    # ---------------------------------------------------------------------- #

    def on_data(self, slice: Slice) -> None:  # noqa: A002
        changed = False

        if slice.contains_key(self._policy_rate):
            val = slice[self._policy_rate].value
            self._latest["policy_rate"] = val
            self.plot("USD Macro Indicators", "Policy Rate (%)", val)
            changed = True

        if slice.contains_key(self._inflation):
            val = slice[self._inflation].value
            self._latest["inflation"] = val
            self.plot("USD Macro Indicators", "Inflation (% YoY)", val)
            changed = True

        if slice.contains_key(self._unemployment):
            val = slice[self._unemployment].value
            self._latest["unemployment"] = val
            self.plot("USD Macro Indicators", "Unemployment (%)", val)
            changed = True

        if slice.contains_key(self._gdp):
            val = slice[self._gdp].value
            self._latest["gdp"] = val
            self.plot("USD Macro Indicators", "GDP (% YoY)", val)
            changed = True

        if changed:
            self._log_snapshot()

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #

    def _log_snapshot(self) -> None:
        parts = []
        if "policy_rate" in self._latest:
            parts.append(f"Rate={self._latest['policy_rate']:.2f}%")
        if "inflation" in self._latest:
            parts.append(f"CPI={self._latest['inflation']:.2f}%")
        if "unemployment" in self._latest:
            parts.append(f"UE={self._latest['unemployment']:.2f}%")
        if "gdp" in self._latest:
            parts.append(f"GDP={self._latest['gdp']:.2f}%")
        if parts:
            self.log(f"USD Macro | {' | '.join(parts)}")
