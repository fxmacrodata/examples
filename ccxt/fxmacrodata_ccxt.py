"""
FXMacroData — CCXT Exchange Integration
========================================
A CCXT-compatible exchange adapter for the FXMacroData REST API.

Implements the standard CCXT unified interface so existing CCXT-based
trading and analysis code can consume FXMacroData FX spot rates,
commodity prices, and macro indicator series with minimal changes.

Supported CCXT methods
-----------------------
- ``load_markets()``         — list all available FX pairs and commodity markets
- ``fetch_markets()``        — same as above, raw list
- ``fetch_ohlcv(symbol)``    — daily OHLCV candles (open=high=low=close, volume=0)
- ``fetch_ticker(symbol)``   — latest mid-market rate
- ``fetch_tickers(symbols)`` — latest rates for a list of symbols

Custom extensions
-----------------
- ``fetch_macro_indicator(currency, indicator, start_date, end_date)``
  Returns a list of ``{date, val, announcement_datetime}`` dicts for any
  indicator in the FXMacroData catalogue (inflation, policy_rate, gdp, …).

Available markets
-----------------
- 30 FX pairs:  EUR/USD, GBP/USD, AUD/USD, USD/JPY, USD/CHF, … and crosses
- 3  commodity pairs: XAU/USD (gold), XAG/USD (silver), XPT/USD (platinum)

Quick start
-----------
    import ccxt
    from fxmacrodata_ccxt import fxmacrodata

    exchange = fxmacrodata()                # public FX endpoints and USD announcements
    exchange = fxmacrodata({'apiKey': 'YOUR_KEY'})  # unlock protected endpoints

    # Standard CCXT interface
    markets = exchange.load_markets()
    ohlcv   = exchange.fetch_ohlcv('EUR/USD', '1d', limit=60)
    ticker  = exchange.fetch_ticker('XAU/USD')

    # Custom macro extension
    rates = exchange.fetch_macro_indicator('USD', 'policy_rate',
                                           '2020-01-01', '2025-12-31')

API key
-------
FX spot rates are public, and USD announcement indicators are public.
To unlock protected non-USD announcements, commodities, and COT data, pass
``apiKey`` in the config dict or set the ``FXMACRODATA_API_KEY`` environment variable.
Get a key at https://fxmacrodata.com/api-management
"""
import logging
import sys

__copilot_logger = logging.getLogger(__name__)

def __copilot_log_print(*args, sep=" ", end="\n", file=None, flush=False):
    message = sep.join(str(arg) for arg in args)
    if end and end != "\n":
        message += end.rstrip("\n")
    stream = file if file is not None else sys.stdout
    level = logging.ERROR if stream is sys.stderr else logging.INFO
    __copilot_logger.log(level, message)


from __future__ import annotations

import datetime
import os
from typing import Dict, List, Optional, Tuple

import ccxt
import requests

# ─── Constants ───────────────────────────────────────────────────────────────

_API_BASE = "https://fxmacrodata.com/api/v1"
_SITE_URL = "https://fxmacrodata.com"
_DOCS_URL = "https://fxmacrodata.com/documentation"
_KEYS_URL = "https://fxmacrodata.com/api-management"

# Predefined FX pairs.  All FX spot rates are free; macro indicators for
# currencies other than USD require a Professional API key.
_FX_PAIRS: List[Tuple[str, str]] = [
    # Majors
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("AUD", "USD"),
    ("NZD", "USD"),
    ("USD", "JPY"),
    ("USD", "CHF"),
    ("USD", "CAD"),
    # Euro crosses
    ("EUR", "GBP"),
    ("EUR", "JPY"),
    ("EUR", "AUD"),
    ("EUR", "NZD"),
    ("EUR", "CHF"),
    ("EUR", "CAD"),
    # Sterling crosses
    ("GBP", "JPY"),
    ("GBP", "AUD"),
    ("GBP", "CHF"),
    ("GBP", "CAD"),
    # Commodity-currency crosses
    ("AUD", "JPY"),
    ("AUD", "CAD"),
    ("AUD", "NZD"),
    ("NZD", "JPY"),
    # Swiss franc crosses
    ("CHF", "JPY"),
    # Emerging & developed market pairs vs USD
    ("USD", "CNY"),
    ("USD", "SGD"),
    ("USD", "SEK"),
    ("USD", "DKK"),
    ("USD", "PLN"),
    ("USD", "BRL"),
    ("USD", "NOK"),
]

# Commodity symbol → FXMacroData indicator name
_COMMODITY_MAP: Dict[str, str] = {
    "XAU/USD": "gold",
    "XAG/USD": "silver",
    "XPT/USD": "platinum",
}

__all__ = ["fxmacrodata"]


# ─── Exchange class ───────────────────────────────────────────────────────────


class fxmacrodata(ccxt.Exchange):
    """
    CCXT-compatible exchange adapter for the FXMacroData REST API.

    Implements the standard CCXT unified interface for market discovery,
    OHLCV candle fetching, and ticker queries.  Adds a custom
    :meth:`fetch_macro_indicator` method for macroeconomic time series.

    Parameters
    ----------
    config : dict, optional
        CCXT-style configuration dict.  Recognised keys:

        * ``apiKey``  — FXMacroData Professional API key (optional; USD
          indicators and all FX spot rates are free without a key).  Can also
          be set via the ``FXMACRODATA_API_KEY`` environment variable.

    Examples
    --------
    >>> exchange = fxmacrodata()
    >>> exchange = fxmacrodata({'apiKey': 'YOUR_KEY'})
    >>> ohlcv = exchange.fetch_ohlcv('EUR/USD', '1d', limit=90)
    >>> ticker = exchange.fetch_ticker('XAU/USD')
    >>> rates  = exchange.fetch_macro_indicator('USD', 'policy_rate',
    ...                                         '2020-01-01', '2025-12-31')
    """

    def describe(self) -> dict:
        return self.deep_extend(
            super().describe(),
            {
                "id": "fxmacrodata",
                "name": "FXMacroData",
                "countries": ["US"],
                "rateLimit": 200,
                "version": "v1",
                "pro": False,
                "has": {
                    "cancelOrder": False,
                    "createOrder": False,
                    "fetchBalance": False,
                    "fetchMarkets": True,
                    "fetchOHLCV": True,
                    "fetchOrderBook": False,
                    "fetchTicker": True,
                    "fetchTickers": True,
                    "fetchTrades": False,
                },
                "timeframes": {
                    "1d": "1d",
                },
                "urls": {
                    "logo": (
                        "https://fxmacrodata.com" "/static/images/fxmacrodata-og.png"
                    ),
                    "api": {
                        "public": _API_BASE,
                    },
                    "www": _SITE_URL,
                    "doc": _DOCS_URL,
                    "fees": "https://fxmacrodata.com/pricing",
                },
                "api": {},
                "fees": {
                    "trading": {
                        "tierBased": False,
                        "percentage": False,
                        "taker": None,
                        "maker": None,
                    },
                },
                "options": {},
                "requiredCredentials": {
                    "apiKey": False,
                    "secret": False,
                },
            },
        )

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config or {})
        # Fall back to the environment variable if apiKey was not provided
        if not self.apiKey:
            self.apiKey = os.environ.get("FXMACRODATA_API_KEY") or ""

    # ── Market discovery ──────────────────────────────────────────────────────

    def fetch_markets(self, params: dict = {}) -> List[dict]:
        """
        Return a list of all available FX and commodity markets.

        Each entry follows the CCXT unified market structure.  No API request
        is made — the market list is pre-defined from the FXMacroData catalogue.

        Returns
        -------
        list of dict
            Each dict has keys ``symbol``, ``base``, ``quote``, ``id``,
            ``active``, ``type``, ``spot``, and ``info``.

        Example
        -------
        >>> markets = exchange.fetch_markets()
        >>> [m['symbol'] for m in markets[:5]]
        ['EUR/USD', 'GBP/USD', 'AUD/USD', 'NZD/USD', 'USD/JPY']
        """
        markets: List[dict] = []

        for base, quote in _FX_PAIRS:
            markets.append(
                _make_market(
                    base=base,
                    quote=quote,
                    market_type="forex",
                )
            )

        for symbol, indicator in _COMMODITY_MAP.items():
            base, quote = symbol.split("/")
            markets.append(
                _make_market(
                    base=base,
                    quote=quote,
                    market_type="commodity",
                    extra_info={"indicator": indicator},
                )
            )

        return markets

    # ── OHLCV ────────────────────────────────────────────────────────────────

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        since: Optional[int] = None,
        limit: Optional[int] = None,
        params: dict = {},
    ) -> List[List]:
        """
        Fetch daily OHLCV candles for a symbol from the FXMacroData API.

        FXMacroData provides daily mid-market close prices only.  ``open``,
        ``high``, and ``low`` are set equal to ``close``; ``volume`` is zero.

        Parameters
        ----------
        symbol :
            CCXT-style symbol, e.g. ``"EUR/USD"`` or ``"XAU/USD"``.
        timeframe :
            Must be ``"1d"`` — FXMacroData only provides daily data.
        since :
            Start of the range as a UTC millisecond timestamp.  If omitted,
            defaults to 365 calendar days before *end_date*.
        limit :
            Maximum number of candles to return.  Applied after fetching.
        params :
            Optional overrides:

            * ``end_date``  (``"YYYY-MM-DD"``) — upper bound of the range;
              defaults to today.

        Returns
        -------
        list of [timestamp_ms, open, high, low, close, volume]
            Timestamps are UTC milliseconds.  ``open == high == low == close``
            (daily mid-market rate).  ``volume`` is always ``0``.

        Raises
        ------
        ccxt.NotSupported
            If *timeframe* is not ``"1d"``.
        ccxt.BadSymbol
            If *symbol* is not in the catalogue.

        Example
        -------
        >>> ohlcv = exchange.fetch_ohlcv('EUR/USD', '1d', limit=30)
        >>> ts, o, h, l, c, v = ohlcv[-1]
        """
        if timeframe != "1d":
            raise ccxt.NotSupported(
                f"{self.id} only supports the '1d' timeframe, not '{timeframe}'. "
                "FXMacroData provides end-of-day data only."
            )

        start_date, end_date = self._resolve_date_range(since, limit, params)
        rows = self._fetch_rows(symbol, start_date, end_date)

        candles = [
            [
                _date_to_ms(row["date"]),  # timestamp (ms)
                row["val"],  # open  (= close)
                row["val"],  # high  (= close)
                row["val"],  # low   (= close)
                row["val"],  # close
                0.0,  # volume (not available)
            ]
            for row in rows
        ]

        if limit is not None:
            candles = candles[-limit:]

        return candles

    # ── Ticker ────────────────────────────────────────────────────────────────

    def fetch_ticker(self, symbol: str, params: dict = {}) -> dict:
        """
        Fetch the latest mid-market rate for a symbol.

        Makes a small API request (last 10 calendar days) to obtain the
        most recent daily close.

        Parameters
        ----------
        symbol :
            CCXT-style symbol, e.g. ``"EUR/USD"`` or ``"XAU/USD"``.

        Returns
        -------
        dict
            Unified CCXT ticker dict.  ``last`` and ``close`` hold the most
            recent mid-market rate.  Fields requiring bid/ask or volume data
            (``bid``, ``ask``, ``baseVolume``, ``quoteVolume``) are ``None``.

        Example
        -------
        >>> ticker = exchange.fetch_ticker('EUR/USD')
        >>> __copilot_log_print(ticker['last'])
        1.08542
        """
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=10)).isoformat()
        end_date = today.isoformat()

        rows = self._fetch_rows(symbol, start_date, end_date)
        if not rows:
            raise ccxt.ExchangeError(
                f"{self.id}: no data available for {symbol}. "
                "Check the symbol and your API key."
            )

        latest = rows[-1]
        prev = rows[-2] if len(rows) >= 2 else None

        ts = _date_to_ms(latest["date"])
        val = float(latest["val"])
        prev_val = float(prev["val"]) if prev else None
        change = (val - prev_val) if prev_val is not None else None
        pct = (change / prev_val * 100.0) if prev_val else None

        return {
            "symbol": symbol,
            "timestamp": ts,
            "datetime": latest["date"],
            "high": None,
            "low": None,
            "bid": None,
            "bidVolume": None,
            "ask": None,
            "askVolume": None,
            "vwap": None,
            "open": prev_val,
            "close": val,
            "last": val,
            "previousClose": prev_val,
            "change": change,
            "percentage": pct,
            "average": ((val + prev_val) / 2.0 if prev_val is not None else None),
            "baseVolume": None,
            "quoteVolume": None,
            "info": latest,
        }

    def fetch_tickers(
        self,
        symbols: Optional[List[str]] = None,
        params: dict = {},
    ) -> Dict[str, dict]:
        """
        Fetch the latest mid-market rates for multiple symbols.

        Each symbol triggers a separate API request.  If *symbols* is
        ``None``, only the 7 major FX pairs are fetched (fetching all
        markets at once would exceed rate limits).

        Parameters
        ----------
        symbols :
            List of CCXT-style symbols.  Defaults to the 7 major FX pairs
            when ``None``.

        Returns
        -------
        dict
            Mapping of ``symbol → ticker`` (see :meth:`fetch_ticker`).

        Example
        -------
        >>> tickers = exchange.fetch_tickers(['EUR/USD', 'GBP/USD', 'XAU/USD'])
        >>> tickers['EUR/USD']['last']
        1.08542
        """
        if symbols is None:
            symbols = [
                "EUR/USD",
                "GBP/USD",
                "AUD/USD",
                "NZD/USD",
                "USD/JPY",
                "USD/CHF",
                "USD/CAD",
            ]

        result: Dict[str, dict] = {}
        for symbol in symbols:
            try:
                result[symbol] = self.fetch_ticker(symbol, params)
            except ccxt.ExchangeError:
                pass  # skip symbols with no recent data

        return result

    # ── Macro indicators (custom extension) ──────────────────────────────────

    def fetch_macro_indicator(
        self,
        currency: str,
        indicator: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[dict]:
        """
        Fetch a macroeconomic indicator time series from FXMacroData.

        This is a custom extension to the CCXT interface — it is not part of
        the standard CCXT unified API.

        Parameters
        ----------
        currency :
            ISO currency code, e.g. ``"USD"``, ``"EUR"``, ``"GBP"``.
            USD announcement indicators are public; non-USD announcements
            require a Professional API key.
        indicator :
            Indicator slug, e.g. ``"inflation"``, ``"policy_rate"``,
            ``"gdp"``, ``"unemployment"``, ``"non_farm_payrolls"``.
            Full catalogue at https://fxmacrodata.com/documentation.
        start_date :
            Start of range (``"YYYY-MM-DD"``).  Defaults to 365 days ago.
        end_date :
            End of range (``"YYYY-MM-DD"``).  Defaults to today.

        Returns
        -------
        list of dict
            Each dict has keys:

            * ``date``                  — ``"YYYY-MM-DD"`` release date
            * ``val``                   — indicator value (float)
            * ``announcement_datetime`` — ISO-8601 UTC release timestamp
              (``None`` if unavailable)

        Raises
        ------
        ccxt.AuthenticationError
            If the requested currency requires a Professional API key.
        ccxt.ExchangeError
            If no data is found for the given range.

        Examples
        --------
        >>> rates = exchange.fetch_macro_indicator('USD', 'policy_rate',
        ...                                        '2020-01-01', '2025-12-31')
        >>> rates[-1]
        {'date': '2025-03-19', 'val': 4.33, 'announcement_datetime': '...'}

        Free USD indicators (sample)
        ----------------------------
        inflation, policy_rate, gdp, unemployment, non_farm_payrolls,
        retail_sales, pmi, trade_balance, core_inflation, housing_starts,
        industrial_production, consumer_confidence  (40+ total)

        See https://fxmacrodata.com/documentation for the full catalogue.
        """
        today = datetime.date.today()
        start = start_date or (today - datetime.timedelta(days=365)).isoformat()
        end = end_date or today.isoformat()

        rows = self._api_get(
            f"/announcements/{currency.lower()}/{indicator}",
            {"start_date": start, "end_date": end},
        )
        if not rows:
            raise ccxt.ExchangeError(
                f"{self.id}: no data returned for "
                f"{currency.upper()} / {indicator} "
                f"in [{start}, {end}]. "
                "Verify the currency code, indicator slug, and date range."
            )
        return rows

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch_rows(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> List[dict]:
        """Dispatch to the correct FXMacroData endpoint for *symbol*."""
        query: dict = {"start_date": start_date, "end_date": end_date}

        if symbol in _COMMODITY_MAP:
            indicator = _COMMODITY_MAP[symbol]
            return self._api_get(f"/commodities/{indicator}", query)

        if "/" not in symbol:
            raise ccxt.BadSymbol(
                f"{self.id}: invalid symbol '{symbol}'. "
                "Use CCXT format, e.g. 'EUR/USD' or 'XAU/USD'."
            )

        base, quote = symbol.split("/", 1)
        return self._api_get(f"/forex/{base.lower()}/{quote.lower()}", query)

    def _api_get(self, path: str, params: dict) -> List[dict]:
        """Execute a GET request against the FXMacroData REST API."""
        if self.apiKey:
            params = {**params, "api_key": self.apiKey}

        url = f"{_API_BASE}{path}"
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code == 401:
            raise ccxt.AuthenticationError(
                f"{self.id}: a Professional API key is required for this "
                "request. "
                f"Get yours at {_KEYS_URL}"
            )
        resp.raise_for_status()
        return resp.json().get("data", [])

    def _resolve_date_range(
        self,
        since: Optional[int],
        limit: Optional[int],
        params: dict,
    ) -> Tuple[str, str]:
        """
        Convert CCXT *since* / *limit* to ``start_date`` / ``end_date`` strings.

        - ``params['end_date']`` takes priority as the upper bound.
        - If *since* is provided it becomes the lower bound (converted from ms).
        - If only *limit* is given the lower bound is estimated by going back
          ``ceil(limit × 2.5) + 14`` calendar days (buffer for weekends/
          holidays).
        - If neither is provided the window is the last 365 calendar days.
        """
        today = datetime.date.today()
        end_date: str = params.get("end_date") or today.isoformat()

        if since is not None:
            start_date = _ms_to_date(since)
        elif limit is not None:
            lookback = int(limit * 2.5) + 14
            start_date = (today - datetime.timedelta(days=lookback)).isoformat()
        else:
            start_date = (today - datetime.timedelta(days=365)).isoformat()

        return start_date, end_date


# ─── Module-level helpers ────────────────────────────────────────────────────


def _make_market(
    base: str,
    quote: str,
    market_type: str,
    extra_info: Optional[dict] = None,
) -> dict:
    """Build a CCXT-format market dict."""
    symbol = f"{base}/{quote}"
    info: dict = {"type": market_type}
    if extra_info:
        info.update(extra_info)
    return {
        "id": f"{base}{quote}",
        "symbol": symbol,
        "base": base,
        "quote": quote,
        "baseId": base.lower(),
        "quoteId": quote.lower(),
        "active": True,
        "type": "spot",
        "spot": True,
        "margin": False,
        "future": False,
        "contract": False,
        "taker": None,
        "maker": None,
        "percentage": None,
        "tierBased": None,
        "info": info,
    }


def _date_to_ms(date_str: str) -> int:
    """Convert a ``"YYYY-MM-DD"`` string to a UTC millisecond timestamp."""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


def _ms_to_date(ms: int) -> str:
    """Convert a UTC millisecond timestamp to a ``"YYYY-MM-DD"`` string."""
    return (
        datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
        .date()
        .isoformat()
    )
