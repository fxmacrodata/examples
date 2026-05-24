"""
FXMacroData — Freqtrade Integration
=====================================
Data-loader helpers for the FXMacroData REST API, designed for use inside
Freqtrade strategies.

Available helpers
-----------------
- fetch_indicator(currency, indicator, ...)  : macro time-series (forward-filled daily)
- fetch_forex(base, quote, ...)              : FX daily close-only DataFrame
- fetch_commodity(indicator, ...)            : commodity daily close-only DataFrame
- merge_macro(dataframe, macro_df, col)      : align a macro series onto an OHLCV frame

Quick start
-----------
    from fxmacrodata_ft import fetch_indicator, merge_macro

    # Fetch USD inflation (free — no API key needed)
    inflation = fetch_indicator("USD", "inflation", "2020-01-01", "2025-12-31")

    # In populate_indicators:
    dataframe = merge_macro(dataframe, inflation, "macro_inflation")

API key
-------
USD announcement indicators are public.
To unlock protected non-USD announcements and commodities, pass
``api_key="YOUR_KEY"`` to any loader, or set the
``FXMACRODATA_API_KEY`` environment variable.
Get a key at https://fxmacrodata.com/api-management
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import requests

# ─── Constants ───────────────────────────────────────────────────────────────

API_BASE = "https://fxmacrodata.com/api/v1"
SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

__all__ = [
    "fetch_indicator",
    "fetch_forex",
    "fetch_commodity",
    "merge_macro",
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


def _to_daily_df(rows: list[dict], start: str, end: str) -> pd.DataFrame:
    """
    Convert a list of ``{date, val}`` dicts to a business-day daily DataFrame.

    Monthly or quarterly observations are forward-filled so that every
    business day holds the most recently released value.  Days before the
    first observation will have ``NaN``.
    """
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")[["val"]].sort_index()
    full_idx = pd.bdate_range(start=start, end=end)
    df = df.reindex(full_idx).ffill()
    df.index.name = "date"
    return df


def _to_close_df(rows: list[dict]) -> pd.DataFrame:
    """Convert a list of ``{date, val}`` dicts to a close-only daily DataFrame."""
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["date"])
    df.index.name = "date"
    return df[["val"]].rename(columns={"val": "close"}).sort_index()


# ─── Public data loaders ──────────────────────────────────────────────────────


def fetch_indicator(
    currency: str,
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch a macroeconomic indicator, forward-filled to business-day cadence.

    Each business day holds the most recently released value.  Days before
    the first release will have ``NaN``.

    Parameters
    ----------
    currency :
        ISO currency code, e.g. ``"USD"``, ``"EUR"``.
    indicator :
        Indicator slug, e.g. ``"inflation"``, ``"policy_rate"``, ``"gdp"``.
        Full catalogue at https://fxmacrodata.com/documentation.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  USD indicators are free.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex (``date``), single column ``"val"`` with the indicator
        value, forward-filled to business-day cadence.

    Example
    -------
    >>> df = fetch_indicator("USD", "inflation", "2020-01-01", "2024-12-31")
    >>> df.loc["2023-07-01", "val"]
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
    return _to_daily_df(rows, start_date, end_date)


def fetch_forex(
    base: str,
    quote: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch FX spot rates and return a close-only daily DataFrame.

    Parameters
    ----------
    base, quote :
        ISO currency codes, e.g. ``"EUR"``, ``"USD"``.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  Not required for most major pairs.

    Returns
    -------
    pd.DataFrame
        DatetimeIndex (``date``), single column ``"close"`` with the daily
        mid-market spot rate.

    Example
    -------
    >>> df = fetch_forex("EUR", "USD", "2022-01-01", "2024-12-31")
    >>> df.head()
                   close
    date
    2022-01-03  1.12895
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
    return _to_close_df(rows)


def fetch_commodity(
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch commodity prices and return a close-only daily DataFrame.

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
        DatetimeIndex (``date``), single column ``"close"`` with the daily
        spot price (USD per troy ounce for precious metals).

    Example
    -------
    >>> df = fetch_commodity("gold", "2022-01-01", "2024-12-31")
    >>> df.head()
                  close
    date
    2022-01-03  1827.30
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
    return _to_close_df(rows)


# ─── Merge helper ─────────────────────────────────────────────────────────────


def merge_macro(
    dataframe: pd.DataFrame,
    macro_df: pd.DataFrame,
    col_name: str,
    value_col: str = "val",
) -> pd.DataFrame:
    """
    Merge a macro indicator series onto a Freqtrade OHLCV DataFrame.

    Uses ``pd.merge_asof`` to forward-fill the most recently released macro
    value onto each OHLCV bar, regardless of timeframe (daily, 4h, 1h, etc.).
    The macro value at each bar is the *last known* release as of that bar's
    date — no future data leakage.

    Parameters
    ----------
    dataframe :
        Freqtrade OHLCV DataFrame (must contain a ``"date"`` column).
    macro_df :
        DataFrame returned by :func:`fetch_indicator`, :func:`fetch_forex`, or
        :func:`fetch_commodity`.  DatetimeIndex, column ``value_col``.
    col_name :
        Name of the new column added to ``dataframe``.
    value_col :
        Column to pull from ``macro_df`` (default: ``"val"``; use ``"close"``
        for forex and commodity DataFrames).

    Returns
    -------
    pd.DataFrame
        ``dataframe`` with an additional column named ``col_name``.

    Example
    -------
    >>> inflation = fetch_indicator("USD", "inflation", "2020-01-01", "2025-12-31")
    >>> dataframe = merge_macro(dataframe, inflation, "macro_inflation")
    >>> dataframe["macro_inflation"].iloc[-1]
    3.2
    """
    # Build a timezone-naive date series from the OHLCV "date" column
    bar_dates = pd.to_datetime(dataframe["date"]).dt.tz_localize(None).dt.normalize()

    # Prepare macro lookup: tz-naive DatetimeIndex, sorted ascending
    macro_index = (
        macro_df.index.tz_localize(None) if macro_df.index.tz else macro_df.index
    )
    lookup = pd.DataFrame(
        {col_name: macro_df[value_col].values},
        index=macro_index,
    ).sort_index()
    lookup = lookup.reset_index().rename(columns={"date": "_macro_date"})
    lookup["_macro_date"] = pd.to_datetime(lookup["_macro_date"]).dt.normalize()

    # Build a temporary frame for merge_asof (needs sorted key column)
    tmp = pd.DataFrame({"_bar_date": bar_dates, "_orig_idx": dataframe.index})
    tmp = tmp.sort_values("_bar_date")

    merged = pd.merge_asof(
        tmp,
        lookup,
        left_on="_bar_date",
        right_on="_macro_date",
        direction="backward",
    )

    # Restore original row order
    merged = merged.sort_values("_orig_idx").set_index("_orig_idx")
    dataframe[col_name] = merged[col_name].values

    return dataframe
