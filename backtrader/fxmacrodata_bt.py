"""
FXMacroData — Backtrader Integration
=====================================
Backtrader data-feed classes and loader helpers for the FXMacroData REST API.

Available feeds
---------------
- FXSpotData          : daily FX spot rates        (/v1/forex/{base}/{quote})
- MacroIndicatorData  : macro time-series           (/v1/announcements/{currency}/{indicator})
- CommodityData       : commodity spot prices       (/v1/commodities/{indicator})

Quick start
-----------
    from fxmacrodata_bt import load_forex, load_indicator, load_commodity

    eurusd  = load_forex("EUR", "USD", "2022-01-01", "2024-12-31")
    inf_usd = load_indicator("USD", "inflation", "2022-01-01", "2024-12-31")
    gold    = load_commodity("gold", "2022-01-01", "2024-12-31")

    cerebro = bt.Cerebro()
    cerebro.adddata(eurusd,  name="EURUSD")
    cerebro.adddata(inf_usd, name="USD_inflation")
    cerebro.adddata(gold,    name="gold")

API key
-------
FX spot rates are public, and USD announcement indicators are public.
Pass ``api_key="YOUR_KEY"`` to unlock protected non-USD announcements and
commodities data.
Get a key at https://fxmacrodata.com/api-management
"""

from __future__ import annotations

from typing import Optional

import backtrader as bt
import pandas as pd
import requests

# ─── Constants ───────────────────────────────────────────────────────────────

API_BASE = "https://fxmacrodata.com/api/v1"
SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

__all__ = [
    "FXSpotData",
    "MacroIndicatorData",
    "CommodityData",
    "load_forex",
    "load_indicator",
    "load_commodity",
]


# ─── Data feed classes ────────────────────────────────────────────────────────


class FXSpotData(bt.feeds.PandasData):
    """
    Backtrader data feed for FX spot rates from the FXMacroData /v1/forex endpoint.

    ``close`` holds the daily mid-market spot rate.  ``open``, ``high``, and
    ``low`` are mapped to the same ``val`` column (close-only data) so that
    market orders execute at the correct daily spot rate rather than using a
    missing open price.
    ``volume`` and ``openinterest`` are not applicable.

    Suitable for use as the primary price feed in a Backtrader strategy.
    """

    params = (
        ("open", "val"),  # same as close — no separate open available
        ("high", "val"),  # same as close
        ("low", "val"),  # same as close
        ("close", "val"),  # daily mid-market spot rate
        ("volume", -1),  # not available
        ("openinterest", -1),  # not applicable
    )


class MacroIndicatorData(bt.feeds.PandasData):
    """
    Backtrader data feed for macroeconomic indicators from the FXMacroData
    /v1/announcements endpoint.

    ``close`` holds the indicator value.  Monthly or quarterly releases are
    forward-filled to a business-day daily cadence so that each bar contains
    the most recently released reading.  ``open``, ``high``, and ``low`` are
    mapped to the same ``val`` column.

    Suitable for use as a signal feed alongside a price feed in a strategy.
    """

    params = (
        ("open", "val"),
        ("high", "val"),
        ("low", "val"),
        ("close", "val"),  # indicator value (forward-filled)
        ("volume", -1),
        ("openinterest", -1),
    )


class CommodityData(bt.feeds.PandasData):
    """
    Backtrader data feed for commodity spot prices from the FXMacroData
    /v1/commodities endpoint.

    Supported indicators: ``gold``, ``silver``, ``platinum``.
    ``close`` holds the daily spot price (USD per troy ounce for metals).
    ``open``, ``high``, and ``low`` are mapped to the same ``val`` column.
    """

    params = (
        ("open", "val"),
        ("high", "val"),
        ("low", "val"),
        ("close", "val"),  # daily spot price
        ("volume", -1),
        ("openinterest", -1),
    )


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


def _to_daily_df(rows: list[dict], start: str, end: str) -> pd.DataFrame:
    """
    Convert a list of ``{date, val}`` dicts to a business-day daily DataFrame.

    Monthly or quarterly observations are forward-filled so that every
    business day holds the most recently released value.  Days before the
    first observation will have ``NaN`` (the strategy should skip those bars).
    """
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")[["val"]].sort_index()

    # Reindex to a full business-day range and forward-fill
    full_idx = pd.bdate_range(start=start, end=end)
    df = df.reindex(full_idx).ffill()
    df.index.name = "datetime"
    return df


# ─── Public loader functions ──────────────────────────────────────────────────


def load_forex(
    base: str,
    quote: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
    indicators: Optional[str] = None,
) -> FXSpotData:
    """
    Fetch FX spot rates and return a Backtrader :class:`FXSpotData` feed.

    Parameters
    ----------
    base, quote :
        ISO currency codes, e.g. ``"EUR"``, ``"USD"``.
    start_date, end_date :
        Date strings in ``"YYYY-MM-DD"`` format.
    api_key :
        FXMacroData Professional API key.  Not required for most pairs.
    indicators :
        Optional comma-separated technical indicator codes (e.g. ``"sma20"``).
        Passed directly to the API ``indicators`` query parameter.

    Returns
    -------
    FXSpotData
        Ready to pass to ``cerebro.adddata()``.

    Example
    -------
    >>> feed = load_forex("EUR", "USD", "2022-01-01", "2024-12-31")
    >>> cerebro.adddata(feed, name="EURUSD")
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key
    if indicators:
        params["indicators"] = indicators

    payload = _get(f"/forex/{base.lower()}/{quote.lower()}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No forex data returned for {base}/{quote} "
            f"in the range [{start_date}, {end_date}]. "
            "Check the currency codes and date range."
        )

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")[["val"]].sort_index()

    return FXSpotData(dataname=df, name=f"{base}/{quote}")


def load_indicator(
    currency: str,
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> MacroIndicatorData:
    """
    Fetch a macroeconomic indicator and return a Backtrader
    :class:`MacroIndicatorData` feed.

    Values are forward-filled to a business-day daily cadence — each bar
    holds the most recently released reading.

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
    MacroIndicatorData
        Ready to pass to ``cerebro.adddata()``.

    Example
    -------
    >>> feed = load_indicator("USD", "inflation", "2022-01-01", "2024-12-31")
    >>> cerebro.adddata(feed, name="USD_inflation")
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    payload = _get(f"/announcements/{currency.lower()}/{indicator}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No indicator data returned for {currency}/{indicator} "
            f"in the range [{start_date}, {end_date}]. "
            "Check the currency code, indicator slug, and date range."
        )

    df = _to_daily_df(rows, start_date, end_date)
    return MacroIndicatorData(dataname=df, name=f"{currency}_{indicator}")


def load_commodity(
    indicator: str,
    start_date: str,
    end_date: str,
    api_key: Optional[str] = None,
) -> CommodityData:
    """
    Fetch commodity prices and return a Backtrader :class:`CommodityData` feed.

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
    CommodityData
        Ready to pass to ``cerebro.adddata()``.

    Example
    -------
    >>> feed = load_commodity("gold", "2022-01-01", "2024-12-31")
    >>> cerebro.adddata(feed, name="gold")
    """
    params: dict = {"start_date": start_date, "end_date": end_date}
    if api_key:
        params["api_key"] = api_key

    payload = _get(f"/commodities/{indicator.lower()}", params)
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(
            f"No commodity data returned for {indicator} "
            f"in the range [{start_date}, {end_date}]."
        )

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["date"])
    df = df.set_index("datetime")[["val"]].sort_index()

    return CommodityData(dataname=df, name=indicator)
