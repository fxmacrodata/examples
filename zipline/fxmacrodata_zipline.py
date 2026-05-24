"""
FXMacroData — Zipline Integration
====================================
Data-loader helpers and a Zipline bundle factory for the FXMacroData REST API.

Available helpers
-----------------
- fetch_forex(base, quote, ...)       : FX daily close-only DataFrame
- fetch_indicator(currency, ...)      : macro time-series (forward-filled daily)
- fetch_commodity(indicator, ...)     : commodity daily close-only DataFrame
- register_fxmacrodata_bundle(...)    : register a Zipline daily-bar bundle
- ingest_fxmacrodata_bundle(...)      : programmatically ingest a registered bundle

Quick start
-----------
    from fxmacrodata_zipline import (
        register_fxmacrodata_bundle,
        ingest_fxmacrodata_bundle,
        fetch_indicator,
    )

    # 1. Register + ingest once (data is cached in ~/.zipline)
    register_fxmacrodata_bundle(pairs=["EURUSD", "GBPUSD", "AUDUSD"],
                                start_date="2020-01-01")
    ingest_fxmacrodata_bundle()

    # 2. Pre-load macro signals
    usd_rate = fetch_indicator("USD", "policy_rate", "2020-01-01", "2025-12-31")

    # 3. Use in run_algorithm
    from zipline import run_algorithm
    perf = run_algorithm(
        start=pd.Timestamp("2020-01-01", tz="UTC"),
        end=pd.Timestamp("2025-12-31", tz="UTC"),
        initialize=initialize,
        handle_data=handle_data,
        capital_base=100_000,
        bundle="fxmacrodata",
    )

API key
-------
FX spot rates are public, and USD announcement indicators are public.
To unlock protected non-USD announcements and commodities, pass
``api_key="YOUR_KEY"`` to any loader or set the ``FXMACRODATA_API_KEY``
environment variable.
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

import os
from typing import Optional, List

import numpy as np
import pandas as pd
import requests

# ─── Constants ───────────────────────────────────────────────────────────────

API_BASE = "https://fxmacrodata.com/api/v1"
SITE_URL = "https://fxmacrodata.com"
DOCS_URL = "https://fxmacrodata.com/documentation"
API_KEYS_URL = "https://fxmacrodata.com/api-management"

_DEFAULT_BUNDLE_NAME = "fxmacrodata"
_DEFAULT_CALENDAR = "24/5"

__all__ = [
    "fetch_forex",
    "fetch_indicator",
    "fetch_commodity",
    "register_fxmacrodata_bundle",
    "ingest_fxmacrodata_bundle",
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
        FXMacroData Professional API key.  Not required for most pairs.

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
        value (forward-filled to business-day cadence).

    Example
    -------
    >>> df = fetch_indicator("USD", "inflation", "2022-01-01", "2024-12-31")
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


# ─── Zipline bundle ───────────────────────────────────────────────────────────


def register_fxmacrodata_bundle(
    bundle_name: str = _DEFAULT_BUNDLE_NAME,
    pairs: Optional[List[str]] = None,
    start_date: str = "2010-01-01",
    end_date: Optional[str] = None,
    api_key: Optional[str] = None,
    calendar_name: str = _DEFAULT_CALENDAR,
) -> None:
    """
    Register a Zipline daily-bar bundle backed by FXMacroData FX spot rates.

    Each FX pair (e.g. ``"EURUSD"``) is registered as a synthetic equity-like
    asset.  ``open``, ``high``, and ``low`` are set equal to ``close`` (the
    daily mid-market spot rate); ``volume`` is zero.

    After calling this function, ingest the bundle before running a backtest:

        >>> ingest_fxmacrodata_bundle()          # programmatic
        $ zipline ingest -b fxmacrodata          # CLI equivalent

    Parameters
    ----------
    bundle_name :
        Name used when referencing the bundle in ``run_algorithm``.
        Defaults to ``"fxmacrodata"``.
    pairs :
        List of 6-character FX pair strings, e.g.
        ``["EURUSD", "GBPUSD", "AUDUSD"]``.
        Defaults to ``["EURUSD", "USDJPY", "GBPUSD", "AUDUSD"]``.
    start_date :
        Earliest date to ingest (``"YYYY-MM-DD"``).  Defaults to
        ``"2010-01-01"``.
    end_date :
        Latest date to ingest (``"YYYY-MM-DD"``).  Defaults to today.
    api_key :
        FXMacroData Professional API key (or set ``FXMACRODATA_API_KEY`` in the
        environment).  Not required for most major pairs.
    calendar_name :
        Exchange-calendars name.  Defaults to ``"24/5"`` (FX market, 24 hours
        Monday–Friday).

    Example
    -------
    >>> register_fxmacrodata_bundle(
    ...     pairs=["EURUSD", "GBPUSD"],
    ...     start_date="2020-01-01",
    ... )
    >>> ingest_fxmacrodata_bundle()
    """
    try:
        from zipline.data.bundles import register
    except ImportError as exc:
        raise ImportError(
            "zipline-reloaded is required.  "
            "Install it with:  pip install zipline-reloaded"
        ) from exc

    import datetime

    if pairs is None:
        pairs = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD"]

    _pairs = [p.upper() for p in pairs]
    _start = start_date
    _end = end_date or datetime.date.today().isoformat()
    _key = _api_key(api_key)

    def _ingest(
        environ,
        asset_db_writer,
        minute_bar_writer,
        daily_bar_writer,
        adjustment_writer,
        calendar,
        start_session,
        end_session,
        cache,
        show_progress,
        output_dir,
    ):
        # ── Asset metadata ────────────────────────────────────────────────────
        n = len(_pairs)
        equities = pd.DataFrame(
            {
                "symbol": _pairs,
                "asset_name": [f"{p[:3]}/{p[3:]}" for p in _pairs],
                "exchange": ["FX"] * n,
                "start_date": [pd.Timestamp(_start)] * n,
                "end_date": [pd.Timestamp(_end)] * n,
                "first_traded": [pd.Timestamp(_start)] * n,
                "auto_close_date": [pd.Timestamp(_end) + pd.Timedelta(days=1)] * n,
            },
            index=range(n),
        )

        exchanges = pd.DataFrame(
            {
                "exchange": ["FX"],
                "canonical_name": ["FX"],
                "country_code": ["XX"],
            }
        )

        asset_db_writer.write(equities=equities, exchanges=exchanges)

        # ── Daily bar data ────────────────────────────────────────────────────
        valid_sessions = calendar.sessions_in_range(start_session, end_session)

        def _generate_bars():
            for sid, pair in enumerate(_pairs):
                base, quote = pair[:3], pair[3:]
                try:
                    df = fetch_forex(base, quote, _start, _end, api_key=_key)
                except Exception as exc:  # noqa: BLE001
                    __copilot_log_print(f"  Warning: could not fetch {pair}: {exc}")
                    continue

                # Align to valid calendar sessions; forward-fill weekend gaps
                df = df.reindex(valid_sessions).ffill().dropna()

                bars = pd.DataFrame(
                    {
                        "open": df["close"].values,
                        "high": df["close"].values,
                        "low": df["close"].values,
                        "close": df["close"].values,
                        "volume": np.zeros(len(df), dtype=np.int64),
                    },
                    index=df.index,
                )
                yield sid, bars

        daily_bar_writer.write(_generate_bars(), show_progress=show_progress)

        # ── No adjustments (FX has no splits or dividends) ────────────────────
        adjustment_writer.write()

    register(bundle_name, _ingest, calendar_name=calendar_name)


def ingest_fxmacrodata_bundle(
    bundle_name: str = _DEFAULT_BUNDLE_NAME,
    show_progress: bool = True,
) -> None:
    """
    Programmatically ingest a previously registered FXMacroData bundle.

    Equivalent to running ``zipline ingest -b <bundle_name>`` from the CLI.
    The ingested data is cached in ``~/.zipline/data/<bundle_name>/``.

    Parameters
    ----------
    bundle_name :
        Name of the bundle to ingest.  Must match the name used in
        :func:`register_fxmacrodata_bundle`.  Defaults to ``"fxmacrodata"``.
    show_progress :
        Display a progress bar during ingestion.  Defaults to ``True``.

    Example
    -------
    >>> register_fxmacrodata_bundle(pairs=["EURUSD"])
    >>> ingest_fxmacrodata_bundle()  # one-time download & cache
    """
    try:
        from zipline.data.bundles import ingest
    except ImportError as exc:
        raise ImportError(
            "zipline-reloaded is required.  "
            "Install it with:  pip install zipline-reloaded"
        ) from exc

    __copilot_log_print(f"Ingesting bundle '{bundle_name}' from FXMacroData…")
    ingest(bundle_name, os.environ, show_progress=show_progress)
    __copilot_log_print(f"Bundle '{bundle_name}' ingested successfully.")
