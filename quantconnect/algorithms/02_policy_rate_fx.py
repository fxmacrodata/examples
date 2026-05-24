"""
FXMacroData — Policy Rate Divergence FX Strategy (Example Algorithm 2)
=======================================================================

A macro-driven FX carry/divergence strategy that uses policy-rate
differentials from the FXMacroData API to tilt exposure toward
higher-yielding FX pairs.

Strategy logic
--------------
* Universe: three major pairs — AUD/USD, EUR/USD, GBP/USD.
* Each month the algorithm reads the latest central-bank policy rates for
  USD, AUD, EUR, and GBP.
* A *rate differential score* is computed for each non-USD currency
  (currency rate − USD rate).
* Positions are scaled proportionally to the score:
    - Positive differential → long the pair (long high-yielder vs USD).
    - Negative differential → short the pair (long USD vs low-yielder).
    - Near-zero differential → flat.
* Maximum position size is capped at 20 % of portfolio NAV per pair.
* A simple volatility guard exits all FX positions when the CBOE VIX
  equivalent (proxied by the SPY 20-day realised vol) exceeds 30 %.

What this demonstrates
----------------------
* Combining FXMacroData custom data with native LEAN FX/equity instruments
* Monthly rebalancing triggered by custom-data arrivals
* Portfolio-level position sizing with risk caps
* COT sentiment as an optional confirmation signal

Run instructions
----------------
1. Upload ``fxmacrodata/lean.py`` (and ``fxmacrodata/__init__.py``) alongside
   this file in your QuantConnect project.
2. Set ``FXMACRODATA_API_KEY`` in the project environment variables — a
    Professional key is required for EUR, GBP, and AUD policy rates.
    USD announcement data is public.
3. Press **Backtest**.

Note: this is an educational example.  Past performance is not indicative
of future results.
"""

from AlgorithmImports import *

from fxmacrodata.lean import FXMacroCOT, FXMacroIndicator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# FX pairs traded (LEAN canonical format)
_FX_PAIRS = ["AUDUSD", "EURUSD", "GBPUSD"]

# Currency codes whose policy rates are monitored (must match FX pairs above)
_CURRENCIES = ["AUD", "EUR", "GBP"]

# Maximum notional weight per pair (fraction of portfolio)
_MAX_WEIGHT = 0.20

# Rate differential threshold — pairs within ±_FLAT_ZONE bps are held flat
_FLAT_ZONE = 0.10  # percentage points

# Annualised realised-volatility threshold for the vol guard (SPY proxy)
_VOL_GUARD_THRESHOLD = 0.30


class PolicyRateDivergenceAlgorithm(QCAlgorithm):
    """FX carry/divergence strategy driven by central-bank rate differentials."""

    def initialize(self) -> None:
        self.set_start_date(2010, 1, 1)
        self.set_end_date(2025, 1, 1)
        self.set_cash(100_000)
        self.set_brokerage_model(BrokerageName.FOREX_BROKER, AccountType.MARGIN)

        # ------------------------------------------------------------------ #
        # FX instruments                                                       #
        # ------------------------------------------------------------------ #
        self._fx_symbols: dict[str, Symbol] = {}
        for pair in _FX_PAIRS:
            sym = self.add_forex(pair, Resolution.DAILY).symbol
            self._fx_symbols[pair] = sym

        # ------------------------------------------------------------------ #
        # FXMacroData — policy rates (Professional key required for non-USD)  #
        # ------------------------------------------------------------------ #
        self._rate_symbols: dict[str, Symbol] = {}
        for ccy in ["USD"] + _CURRENCIES:
            sym = self.add_data(
                FXMacroIndicator,
                f"{ccy}_POLICY_RATE",
                Resolution.DAILY,
            ).symbol
            self._rate_symbols[ccy] = sym

        # ------------------------------------------------------------------ #
        # FXMacroData — COT positioning (optional confirmation, Pro key req.) #
        # ------------------------------------------------------------------ #
        self._cot_symbols: dict[str, Symbol] = {}
        for ccy in _CURRENCIES:
            sym = self.add_data(FXMacroCOT, ccy, Resolution.DAILY).symbol
            self._cot_symbols[ccy] = sym

        # ------------------------------------------------------------------ #
        # SPY — used to compute a realised-vol guard proxy                    #
        # ------------------------------------------------------------------ #
        self._spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self._spy_roc = self.roc(self._spy, 1, Resolution.DAILY)
        self._spy_vol = self.std(self._spy, 20, Resolution.DAILY)

        # ------------------------------------------------------------------ #
        # State                                                                #
        # ------------------------------------------------------------------ #
        self._latest_rates: dict[str, float] = {}
        self._latest_cot: dict[str, float] = {}

        # Rebalance once per month
        self.schedule.on(
            self.date_rules.month_start(),
            self.time_rules.after_market_open("SPY", 30),
            self._rebalance,
        )

        # ------------------------------------------------------------------ #
        # Charts                                                               #
        # ------------------------------------------------------------------ #
        rate_chart = Chart("Policy Rate Differentials")
        for ccy in _CURRENCIES:
            rate_chart.add_series(Series(f"{ccy}-USD (pp)", SeriesType.LINE))
        self.add_chart(rate_chart)

        cot_chart = Chart("COT Net Positions")
        for ccy in _CURRENCIES:
            cot_chart.add_series(Series(f"{ccy} Net", SeriesType.LINE))
        self.add_chart(cot_chart)

    # ---------------------------------------------------------------------- #
    # Data handler — capture latest macro readings as they arrive             #
    # ---------------------------------------------------------------------- #

    def on_data(self, slice: Slice) -> None:  # noqa: A002
        # Update policy rates
        for ccy, sym in self._rate_symbols.items():
            if slice.contains_key(sym):
                self._latest_rates[ccy] = slice[sym].value

        # Update COT net positions
        for ccy, sym in self._cot_symbols.items():
            if slice.contains_key(sym):
                self._latest_cot[ccy] = slice[sym].value

        # Plot rate differentials and COT whenever we receive new data
        usd_rate = self._latest_rates.get("USD")
        if usd_rate is not None:
            for ccy in _CURRENCIES:
                if ccy in self._latest_rates:
                    diff = self._latest_rates[ccy] - usd_rate
                    self.plot("Policy Rate Differentials", f"{ccy}-USD (pp)", diff)
        for ccy, net in self._latest_cot.items():
            self.plot("COT Net Positions", f"{ccy} Net", net)

    # ---------------------------------------------------------------------- #
    # Monthly rebalance                                                        #
    # ---------------------------------------------------------------------- #

    def _rebalance(self) -> None:
        if not self._has_sufficient_data():
            return

        # Vol guard — exit FX if SPY realised vol is elevated
        if (
            self._spy_vol.is_ready
            and self._spy_vol.current.value > _VOL_GUARD_THRESHOLD
        ):
            self.log(
                f"Vol guard triggered (SPY 20d vol={self._spy_vol.current.value:.1%})"
                " — closing all FX positions."
            )
            for sym in self._fx_symbols.values():
                self.liquidate(sym)
            return

        usd_rate = self._latest_rates["USD"]
        target_weights = self._compute_weights(usd_rate)
        self._apply_weights(target_weights)

    def _has_sufficient_data(self) -> bool:
        """Return True only when we have policy rates for all currencies."""
        required = ["USD"] + _CURRENCIES
        missing = [c for c in required if c not in self._latest_rates]
        if missing:
            self.log(f"Waiting for rate data: {missing}")
            return False
        return True

    def _compute_weights(self, usd_rate: float) -> dict[str, float]:
        """Convert rate differentials to target portfolio weights.

        Weights are proportional to the differential, normalised so the
        maximum absolute weight does not exceed ``_MAX_WEIGHT``.  Pairs
        within the flat zone are held at zero.
        """
        diffs: dict[str, float] = {}
        for ccy in _CURRENCIES:
            diff = self._latest_rates[ccy] - usd_rate
            diffs[ccy] = diff

        # Optional COT confirmation: shrink weight when positioning is
        # strongly one-sided against the rate signal.
        # 200 000 contracts ≈ 95th-percentile historical COT net position across
        # major FX futures (CFTC legacy report, 2000-2025).  Used to normalise
        # net positioning to a [0, 1] scale for the COT adjustment factor.
        _COT_NORM = 200_000

        adjusted: dict[str, float] = {}
        for ccy, diff in diffs.items():
            if abs(diff) < _FLAT_ZONE:
                adjusted[ccy] = 0.0
                continue
            weight = diff  # raw differential as weight proxy
            if ccy in self._latest_cot:
                cot = self._latest_cot[ccy]
                # Reduce weight by up to 50 % when COT is heavily opposed
                cot_factor = (
                    max(0.5, 1.0 - abs(cot) / _COT_NORM * 0.5)
                    if cot * weight < 0
                    else 1.0
                )
                weight *= cot_factor
            adjusted[ccy] = weight

        # Normalise: scale so the largest absolute weight equals _MAX_WEIGHT
        max_abs = max((abs(v) for v in adjusted.values()), default=1.0)
        if max_abs == 0:
            return {ccy: 0.0 for ccy in _CURRENCIES}

        scale = _MAX_WEIGHT / max_abs
        return {ccy: w * scale for ccy, w in adjusted.items()}

    def _apply_weights(self, target_weights: dict[str, float]) -> None:
        """Set FX positions to match target weights."""
        nav = self.portfolio.total_portfolio_value
        for ccy, weight in target_weights.items():
            pair = f"{ccy}USD"
            sym = self._fx_symbols.get(pair)
            if sym is None:
                continue
            if abs(weight) < 1e-6:
                self.liquidate(sym)
                continue
            # Convert weight to notional units (one LEAN FX contract = 1 unit)
            notional = nav * weight
            fx_rate = self.securities[sym].price
            if fx_rate and fx_rate > 0:
                quantity = round(notional / fx_rate)
                self.market_order(sym, quantity)
                self.log(
                    f"{pair}: weight={weight:.1%}, rate_diff="
                    f"{self._latest_rates[ccy] - self._latest_rates['USD']:+.2f}pp"
                    f", qty={quantity}"
                )
