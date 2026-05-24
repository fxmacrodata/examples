"""
FXMacroData — Blankly Integration
====================================
Data-loader helpers and exchange factory for the FXMacroData REST API.

Available helpers
-----------------
- fetch_forex(base, quote, ...)       : FX daily close-only OHLCV DataFrame (blankly format)
- fetch_indicator(currency, ...)      : macro time-series (forward-filled daily)
- fetch_commodity(indicator, ...)     : commodity daily close-only OHLCV DataFrame
- create_exchange(base, quote, ...)   : KeylessExchange ready for a blankly Strategy
- get_macro_signal(df, timestamp)     : look up the most recent macro value at a timestamp

Quick start
-----------
    from fxmacrodata_blankly import (
        create_exchange,
        fetch_indicator,
        get_macro_signal,
    )
    import blankly

    exchange = create_exchange("EUR", "USD", "2022-01-01", "2024-12-31")
    inflation = fetch_indicator("USD", "inflation", "2022-01-01", "2024-12-31")

    def init(symbol, state: blankly.StrategyState):
        state.variables['inflation'] = inflation

    def price_event(price, symbol, state: blankly.StrategyState):
        val = get_macro_signal(state.variables['inflation'], state.time)
        if val is None:
            return
        # … trading logic using val …

    strategy = blankly.Strategy(exchange)
    strategy.add_price_event(price_event, symbol='EUR-USD', resolution='1d', init=init)
    results = strategy.backtest(
        start_date='2022-01-01',
        end_date='2024-12-31',
        initial_values={'USD': 100_000},
    )

API key
-------
FX spot rates are public, and USD announcement indicators are public.
Pass ``api_key="YOUR_KEY"`` to unlock protected non-USD announcements and
commodities data, or set the ``FXMACRODATA_API_KEY`` environment variable.
Get a key at https://fxmacrodata.com/api-management
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

import pandas as pd
import requests

# ─── Constants ───────────────────────────────────────────────────────────────

API_BASE = "https://fxmacrodata.com/api/v1"
SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

__all__ = [
    "fetch_forex",
    "fetch_indicator",
    "fetch_commodity",
    "create_exchange",
    "get_macro_signal",
]


# ─── Private helpers ──────────────────────────────────────────────────────────


def _get(path: str, params: dict, timeout: int = 30) -> dict:
    """Execute a GET request against the FXMacroData REST API."""
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=timeout)
    if resp.status_code == 401:
        raise PermissionError(
            "A Professional API key is required for this endpoint. "
            f"Get yours at {API_KEYS_URL}"
        )
    resp.raise_for_status()
    return resp.json()


def _api_key(explicit: Optional[str]) -> Optional[str]:
    """Return the explicit key or fall back to the environment variable."""
    return explicit or os.environ.get("FXMACRODATA_API_KEY") or None


def _to_blankly_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """
    Convert a list of ``{date, val}`` dicts to a blankly-compatible OHLCV
    DataFrame.

    Blankly's ``PriceReader`` requires these columns (in any order):
        ``time``  — Unix epoch (integer seconds)
        ``open``, ``high``, ``low``, ``close``  — price columns
        ``volume`` — trade volume (set to 0 for FX/macro data)

    FXMacroData provides daily close-only data, so ``open``, ``high``, and
    ``low`` are all set equal to ``close``.
    """
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime").sort_index()

    result = pd.DataFrame(index=df.index)
    result["time"] = df.index.astype("int64") // 10**9  # nanoseconds → seconds
    result["open"] = df["val"]
    result["high"] = df["val"]
    result["low"] = df["val"]
    result["close"] = df["val"]
    result["volume"] = 0
    return result.reset_index(drop=True)


def _to_forward_filled_df(rows: list[dict], start: str, end: str) -> pd.DataFrame:
    """
    Convert a list of ``{date, val}`` dicts to a business-day daily DataFrame.

    Monthly or quarterly observations are forward-filled so that every
    business day holds the most recently released value.  Days before the
    first observation will have ``NaN`` (the strategy should skip those bars).

    The index is a ``DatetimeIndex``; the single column is ``"val"``.
    """
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")[["val"]].sort_index()

    full_idx = pd.bdate_range(start=start, end=end)
    df = df.reindex(full_idx).ffill()
    df.index.name = "date"
    return df


# ─── Public data loaders ──────────────────────────────────────────────────────


def fetch_forex(
    base: str,
    quote: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch FX spot rates and return a blankly-compatible OHLCV DataFrame.

    The DataFrame has integer columns ``time`` (Unix epoch seconds),
    ``open``, ``high``, ``low``, ``close``, and ``volume``.  Because
    FXMacroData provides daily close-only rates, ``open``, ``high``, and
    ``low`` are equal to ``close``; ``volume`` is zero.

    Pass this DataFrame directly to :func:`create_exchange` or to blankly's
    ``PriceReader`` to create a ``KeylessExchange``.

    Parameters
    ----------
    base, quote :
        ISO currency codes, e.g. ``"EUR"``, ``"USD"``.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  Not required for most pairs.

    Returns
    -------
    pd.DataFrame
        OHLCV DataFrame (blankly ``PriceReader`` format).

    Example
    -------
    >>> df = fetch_forex("EUR", "USD", "2022-01-01", "2024-12-31")
    >>> exchange = create_exchange("EUR", "USD", df=df)
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    key = _api_key(api_key)
    if key:
        params["api_key"] = key

    payload = _get(f"/forex/{base.lower()}/{quote.lower()}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No forex data returned for {base}/{quote} "
            f"in the range [{start_date}, {end_date}]. "
            "Check the currency codes and date range."
        )
    return _to_blankly_ohlcv(rows)


def fetch_indicator(
    currency: str,
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch a macroeconomic indicator, forward-filled to business-day cadence.

    Each business day holds the most recently released value.  Days before the
    first release will have ``NaN`` — guard against these with
    :func:`get_macro_signal`.

    Parameters
    ----------
    currency :
        ISO currency code, e.g. ``"USD"``, ``"EUR"``.
    indicator :
        Indicator slug, e.g. ``"inflation"``, ``"policy_rate"``, ``"gdp"``.
        See https://fxmacrodata.com/documentation for the full catalogue.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  USD indicators are free.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex (``date``), single column ``"val"`` (forward-filled).

    Example
    -------
    >>> df = fetch_indicator("USD", "inflation", "2022-01-01", "2024-12-31")
    >>> get_macro_signal(df, state.time)   # inside a price_event
    3.0
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    key = _api_key(api_key)
    if key:
        params["api_key"] = key

    payload = _get(f"/announcements/{currency.lower()}/{indicator}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No indicator data returned for {currency}/{indicator} "
            f"in the range [{start_date}, {end_date}]. "
            "Check the currency code, indicator slug, and date range."
        )
    return _to_forward_filled_df(rows, start_date, end_date)


def fetch_commodity(
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch commodity prices and return a blankly-compatible OHLCV DataFrame.

    Parameters
    ----------
    indicator :
        ``"gold"``, ``"silver"``, or ``"platinum"``.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  Commodities are free.

    Returns
    -------
    pd.DataFrame
        OHLCV DataFrame (blankly ``PriceReader`` format).

    Example
    -------
    >>> df = fetch_commodity("gold", "2022-01-01", "2024-12-31")
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    key = _api_key(api_key)
    if key:
        params["api_key"] = key

    payload = _get(f"/commodities/{indicator.lower()}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No commodity data returned for {indicator} "
            f"in the range [{start_date}, {end_date}]."
        )
    return _to_blankly_ohlcv(rows)


# ─── Exchange factory ─────────────────────────────────────────────────────────


def create_exchange(
    base: str,
    quote: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    api_key: Optional[str] = None,
    df: Optional[pd.DataFrame] = None,
) -> "blankly.KeylessExchange":
    """
    Create a blankly ``KeylessExchange`` loaded with FXMacroData FX spot rates.

    The exchange provides one symbol: ``"<BASE>-<QUOTE>"`` (e.g. ``"EUR-USD"``).
    Use it to build a ``blankly.Strategy`` for keyless backtesting.

    Either provide ``start_date``/``end_date`` to fetch data automatically, or
    pass a pre-fetched ``df`` from :func:`fetch_forex`.

    Parameters
    ----------
    base, quote :
        ISO currency codes, e.g. ``"EUR"``, ``"USD"``.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.  Required when ``df`` is not
        provided.
    api_key :
        FXMacroData Professional API key.  Not required for most pairs.
    df :
        Pre-fetched OHLCV DataFrame from :func:`fetch_forex`.  If provided,
        ``start_date``/``end_date`` are ignored.

    Returns
    -------
    blankly.KeylessExchange
        Pass to ``blankly.Strategy(exchange)`` to build a strategy.

    Example
    -------
    >>> exchange  = create_exchange("EUR", "USD", "2022-01-01", "2024-12-31")
    >>> strategy  = blankly.Strategy(exchange)
    >>> strategy.add_price_event(price_event, symbol='EUR-USD', resolution='1d', init=init)
    >>> results   = strategy.backtest(
    ...     start_date='2022-01-01',
    ...     end_date='2024-12-31',
    ...     initial_values={'USD': 100_000},
    ... )
    """
    try:
        import blankly
        from blankly.data import PriceReader
    except ImportError as exc:
        raise ImportError(
            "blankly is required.  " "Install it with:  pip install blankly"
        ) from exc

    if df is None:
        if start_date is None or end_date is None:
            raise ValueError(
                "Provide either start_date + end_date, or a pre-fetched df."
            )
        df = fetch_forex(base, quote, start_date, end_date, api_key=api_key)

    symbol = f"{base.upper()}-{quote.upper()}"

    # Write to a temporary CSV so PriceReader can load it.
    # PriceReader resolves file type from the file extension.
    # The file is deleted immediately after PriceReader reads it into memory.
    import os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        df.to_csv(tmp, index=False)
        tmp_path = tmp.name

    try:
        price_reader = PriceReader(tmp_path, symbol)
    finally:
        os.unlink(tmp_path)

    return blankly.KeylessExchange(price_reader=price_reader)


# ─── Macro signal helper ──────────────────────────────────────────────────────


def get_macro_signal(
    df: pd.DataFrame,
    timestamp: float,
    col: str = "val",
) -> Optional[float]:
    """
    Look up the most recently available macro value at or before ``timestamp``.

    Use this inside a blankly ``price_event`` or ``init`` function to retrieve
    the current macro reading without look-ahead bias.

    Parameters
    ----------
    df :
        DataFrame returned by :func:`fetch_indicator` (DatetimeIndex, column
        ``"val"``).
    timestamp :
        Current time as a Unix epoch float (``state.time`` in blankly).
    col :
        Column name to read.  Defaults to ``"val"``.

    Returns
    -------
    float or None
        The most recently released value, or ``None`` if no data is available
        yet (before the first release in the series).

    Example
    -------
    >>> def price_event(price, symbol, state: blankly.StrategyState):
    ...     val = get_macro_signal(state.variables['inflation'], state.time)
    ...     if val is None:
    ...         return
    ...     # use val in trading logic
    """
    import math

    dt = pd.Timestamp(timestamp, unit="s", tz="UTC").tz_convert(None)
    available = df.loc[df.index <= dt, col].dropna()
    if available.empty:
        return None
    value = float(available.iloc[-1])
    return None if math.isnan(value) else value
