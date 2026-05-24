"""
FXMacroData — pandas-datareader Integration
=============================================
pandas-datareader-compatible readers for the FXMacroData REST API.

Supported data types
---------------------
- **Macro indicators** — ``FXMacroDataIndicatorReader``
  Symbol: ``"USD/inflation"`` · ``"EUR/policy_rate"`` · ``"AUD/gdp"``

- **FX spot rates** — ``FXMacroDataForexReader``
  Symbol: ``"EURUSD"`` · ``"EUR/USD"`` · ``"AUD/USD"``

- **Precious metals** — ``FXMacroDataCommoditiesReader``
  Symbol: ``"gold"`` · ``"silver"`` · ``"platinum"``

- **CFTC COT positioning** — ``FXMacroDataCOTReader``
  Symbol: ``"EUR"`` · ``"JPY"`` · ``"GBP"``

Quick start (using DataReader after registering)
-------------------------------------------------
    import pandas_datareader as pdr
    import fxmacrodata_datareader as fxmd

    fxmd.register()   # patches DataReader once

    # Macro indicator (USD announcements are public; non-USD require an API key)
    df = pdr.DataReader("USD/inflation", "fxmacrodata", start, end)

    # With API key
    df = pdr.DataReader("EUR/policy_rate", "fxmacrodata", start, end,
                        api_key="YOUR_KEY")

    # FX spot rate
    df = pdr.DataReader("EURUSD", "fxmacrodata-forex", start, end)

    # Precious metal
    df = pdr.DataReader("gold", "fxmacrodata-commodity", start, end)

    # COT positioning
    df = pdr.DataReader("EUR", "fxmacrodata-cot", start, end, api_key="YOUR_KEY")

Standalone readers (no registration needed)
--------------------------------------------
    from fxmacrodata_datareader import (
        FXMacroDataIndicatorReader,
        FXMacroDataForexReader,
        FXMacroDataCommoditiesReader,
        FXMacroDataCOTReader,
    )

    reader = FXMacroDataIndicatorReader("USD/inflation", "2020-01-01", "2025-12-31")
    df = reader.read()

API key
-------
USD announcement indicators are public. Non-USD announcement indicators,
commodities, and COT data require a Professional API key. Pass it explicitly
via ``api_key=`` or set the ``FXMACRODATA_API_KEY`` environment variable.

Get your key at https://fxmacrodata.com/api-management
"""

from __future__ import annotations

import os
from typing import List, Optional, Union

import pandas as pd

_API_BASE = "https://fxmacrodata.com/api/v1"
_DOCS_URL = "https://fxmacrodata.com/documentation"
_API_KEYS_URL = "https://fxmacrodata.com/api-management"

# Precious-metal symbols handled by the /v1/commodities/ endpoint
_COMMODITY_SYMBOLS = frozenset({"gold", "silver", "platinum"})

__all__ = [
    "FXMacroDataIndicatorReader",
    "FXMacroDataForexReader",
    "FXMacroDataCommoditiesReader",
    "FXMacroDataCOTReader",
    "get_data_fxmacrodata",
    "register",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_api_key(explicit: Optional[str]) -> Optional[str]:
    """Return the explicit key or fall back to the environment variable."""
    return explicit or os.environ.get("FXMACRODATA_API_KEY") or None


def _get(session, url: str, params: dict, timeout: int = 30) -> dict:
    """Execute a GET and return the parsed JSON body.

    Raises
    ------
    PermissionError
        When the server returns HTTP 401 (missing or invalid API key).
    ValueError
        When the server returns HTTP 404 (unsupported symbol / date range).
    OSError
        For any other non-200 response.
    """
    resp = session.get(url, params=params, timeout=timeout)
    if resp.status_code == 401:
        raise PermissionError(
            "A Professional API key is required for this resource. "
            f"Get yours at {_API_KEYS_URL}"
        )
    if resp.status_code == 404:
        raise ValueError(
            f"No data found — check the symbol and date range. "
            f"Full catalogue: {_DOCS_URL}"
        )
    resp.raise_for_status()
    return resp.json()


def _rows_to_df(
    rows: list,
    value_col: str = "val",
    keep_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Convert a list of ``{date, val, ...}`` dicts to a DatetimeIndex DataFrame."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["date"])
    df.index.name = "date"
    df = df.drop(columns=["date"], errors="ignore")
    if keep_cols:
        df = df[[c for c in keep_cols if c in df.columns]]
    return df.sort_index()


def _parse_indicator_symbol(symbol: str):
    """Split ``"USD/inflation"`` or ``"USD_inflation"`` into (currency, indicator)."""
    for sep in ("/", "_"):
        if sep in symbol:
            parts = symbol.split(sep, 1)
            if len(parts) == 2:
                return parts[0].upper(), parts[1].lower()
    raise ValueError(
        f"Cannot parse indicator symbol {symbol!r}. "
        "Expected format: 'USD/inflation' or 'USD_inflation'."
    )


def _parse_forex_symbol(symbol: str):
    """Split ``"EURUSD"`` or ``"EUR/USD"`` into (base, quote)."""
    if "/" in symbol:
        parts = symbol.split("/")
        if len(parts) == 2:
            return parts[0].upper(), parts[1].upper()
    if len(symbol) == 6:
        return symbol[:3].upper(), symbol[3:].upper()
    raise ValueError(
        f"Cannot parse FX symbol {symbol!r}. " "Expected format: 'EURUSD' or 'EUR/USD'."
    )


# ---------------------------------------------------------------------------
# Base reader (compatible with pandas-datareader _BaseReader contract)
# ---------------------------------------------------------------------------


class _FXMacroDataBaseReader:
    """
    Minimal base class that mirrors the pandas-datareader ``_BaseReader``
    interface so that the readers can be used both standalone and via the
    patched ``DataReader`` dispatcher.

    Parameters
    ----------
    symbols : str or list of str
        Symbol(s) to fetch.  The format depends on the concrete reader.
    start : str or datetime-like, optional
        Start of the date range (YYYY-MM-DD).  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End of the date range (YYYY-MM-DD).  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  Falls back to the
        ``FXMACRODATA_API_KEY`` environment variable.
    retry_count : int, default 3
        Number of times to retry a failed request.
    pause : float, default 0.1
        Seconds between retries.
    session : requests.Session, optional
        Pre-configured requests Session.  A new session is created if omitted.
    """

    def __init__(
        self,
        symbols: Union[str, List[str]],
        start=None,
        end=None,
        api_key: Optional[str] = None,
        retry_count: int = 3,
        pause: float = 0.1,
        session=None,
    ):
        import datetime as _dt

        self.symbols = symbols
        self.api_key = _resolve_api_key(api_key)
        self.retry_count = retry_count
        self.pause = pause

        today = _dt.date.today()
        self.end = pd.Timestamp(end) if end is not None else pd.Timestamp(today)
        self.start = (
            pd.Timestamp(start)
            if start is not None
            else pd.Timestamp(today - _dt.timedelta(days=365 * 5))
        )

        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    @property
    def _start_str(self) -> str:
        return self.start.strftime("%Y-%m-%d")

    @property
    def _end_str(self) -> str:
        return self.end.strftime("%Y-%m-%d")

    def _base_params(self) -> dict:
        params: dict = {
            "start_date": self._start_str,
            "end_date": self._end_str,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def close(self):
        """Close the underlying requests session."""
        self.session.close()

    def read(self) -> pd.DataFrame:
        """Fetch data and return a pandas DataFrame."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Concrete readers
# ---------------------------------------------------------------------------


class FXMacroDataIndicatorReader(_FXMacroDataBaseReader):
    """
    Reader for macroeconomic indicator time series.

    Symbol format: ``"USD/inflation"`` or ``"USD_inflation"``

    Returns a DataFrame with a DatetimeIndex (``date``) and the following
    columns (where present):

    - ``val`` — the indicator value
    - ``announcement_datetime`` — Unix timestamp of the official release
    - ``pct_change`` — period-over-period percentage change (where applicable)
    - ``pct_change_12m`` — 12-month percentage change (where applicable)

    If multiple symbols are passed, returns a single DataFrame with one
    column per symbol named ``{CURRENCY}_{indicator}``.

    Parameters
    ----------
    symbols : str or list of str
        Indicator symbol(s) in ``"CURRENCY/indicator"`` format.
    start : str or datetime-like, optional
        Start date.  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End date.  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  USD indicators are free.
    """

    def read(self) -> pd.DataFrame:
        symbols = (
            [self.symbols] if isinstance(self.symbols, str) else list(self.symbols)
        )
        try:
            if len(symbols) == 1:
                return self._fetch_one(symbols[0])
            return self._fetch_many(symbols)
        finally:
            self.close()

    def _fetch_one(self, symbol: str) -> pd.DataFrame:
        currency, indicator = _parse_indicator_symbol(symbol)
        url = f"{_API_BASE}/announcements/{currency.lower()}/{indicator}"
        payload = _get(self.session, url, self._base_params())
        rows = payload.get("data", [])
        if not rows:
            return pd.DataFrame(
                columns=["val", "announcement_datetime", "pct_change", "pct_change_12m"]
            )
        return _rows_to_df(
            rows,
            keep_cols=["val", "announcement_datetime", "pct_change", "pct_change_12m"],
        )

    def _fetch_many(self, symbols: List[str]) -> pd.DataFrame:
        frames = {}
        for sym in symbols:
            currency, indicator = _parse_indicator_symbol(sym)
            col_name = f"{currency}_{indicator}"
            df = self._fetch_one(sym)
            if not df.empty and "val" in df.columns:
                frames[col_name] = df["val"]
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames).sort_index()


class FXMacroDataForexReader(_FXMacroDataBaseReader):
    """
    Reader for daily FX spot rates (ECB reference rates).

    Symbol format: ``"EURUSD"`` or ``"EUR/USD"``

    Returns a DataFrame with a DatetimeIndex (``date``) and a single column
    ``val`` containing the daily mid-market spot rate.

    If multiple symbols are passed, returns a single DataFrame with one column
    per pair named by the 6-character pair string (e.g. ``EURUSD``).

    Parameters
    ----------
    symbols : str or list of str
        FX pair(s) in ``"EURUSD"`` or ``"EUR/USD"`` format.
    start : str or datetime-like, optional
        Start date.  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End date.  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  Most major pairs are free.
    """

    def read(self) -> pd.DataFrame:
        symbols = (
            [self.symbols] if isinstance(self.symbols, str) else list(self.symbols)
        )
        try:
            if len(symbols) == 1:
                return self._fetch_one(symbols[0])
            return self._fetch_many(symbols)
        finally:
            self.close()

    def _fetch_one(self, symbol: str) -> pd.DataFrame:
        base, quote = _parse_forex_symbol(symbol)
        url = f"{_API_BASE}/forex/{base.lower()}/{quote.lower()}"
        payload = _get(self.session, url, self._base_params())
        rows = payload.get("data", [])
        if not rows:
            return pd.DataFrame(columns=["val"])
        return _rows_to_df(rows, keep_cols=["val"])

    def _fetch_many(self, symbols: List[str]) -> pd.DataFrame:
        frames = {}
        for sym in symbols:
            base, quote = _parse_forex_symbol(sym)
            col_name = f"{base}{quote}"
            df = self._fetch_one(sym)
            if not df.empty and "val" in df.columns:
                frames[col_name] = df["val"]
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames).sort_index()


class FXMacroDataCommoditiesReader(_FXMacroDataBaseReader):
    """
    Reader for precious metals spot prices.

    Symbol: ``"gold"``, ``"silver"``, or ``"platinum"``

    Returns a DataFrame with a DatetimeIndex (``date``) and the following
    columns (where present):

    - ``val`` — spot price in USD per troy ounce
    - ``pct_change`` — period-over-period percentage change
    - ``pct_change_12m`` — 12-month percentage change

    If multiple symbols are passed, returns a single DataFrame with one
    column per commodity named by its symbol.

    Parameters
    ----------
    symbols : str or list of str
        Commodity symbol(s): ``"gold"``, ``"silver"``, or ``"platinum"``.
    start : str or datetime-like, optional
        Start date.  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End date.  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  Precious metals are free.
    """

    def read(self) -> pd.DataFrame:
        symbols = (
            [self.symbols] if isinstance(self.symbols, str) else list(self.symbols)
        )
        try:
            if len(symbols) == 1:
                return self._fetch_one(symbols[0])
            return self._fetch_many(symbols)
        finally:
            self.close()

    def _fetch_one(self, symbol: str) -> pd.DataFrame:
        sym_lower = symbol.lower()
        if sym_lower not in _COMMODITY_SYMBOLS:
            raise ValueError(
                f"Unsupported commodity {symbol!r}. "
                f"Supported values: {sorted(_COMMODITY_SYMBOLS)}."
            )
        url = f"{_API_BASE}/commodities/{sym_lower}"
        payload = _get(self.session, url, self._base_params())
        rows = payload.get("data", [])
        if not rows:
            return pd.DataFrame(columns=["val", "pct_change", "pct_change_12m"])
        return _rows_to_df(
            rows,
            keep_cols=["val", "pct_change", "pct_change_12m"],
        )

    def _fetch_many(self, symbols: List[str]) -> pd.DataFrame:
        frames = {}
        for sym in symbols:
            df = self._fetch_one(sym)
            if not df.empty and "val" in df.columns:
                frames[sym.lower()] = df["val"]
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames).sort_index()


class FXMacroDataCOTReader(_FXMacroDataBaseReader):
    """
    Reader for CFTC Commitment of Traders (COT) weekly positioning data.

    Symbol: 3-letter currency code — ``"EUR"``, ``"GBP"``, ``"JPY"``, etc.

    Returns a DataFrame with a DatetimeIndex (``date``) and the following
    columns (where present):

    - ``net_noncommercial`` — net non-commercial positions (longs minus shorts)
    - ``long_noncommercial`` — gross non-commercial long contracts
    - ``short_noncommercial`` — gross non-commercial short contracts
    - ``open_interest`` — total open interest
    - ``long_commercial`` — gross commercial long contracts
    - ``short_commercial`` — gross commercial short contracts

    If multiple symbols are passed, returns a dict of ``{currency: DataFrame}``.

    Parameters
    ----------
    symbols : str or list of str
        Currency code(s) to fetch COT data for.
    start : str or datetime-like, optional
        Start date.  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End date.  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  **Required** for all COT data.
    """

    _COT_COLS = [
        "net_noncommercial",
        "long_noncommercial",
        "short_noncommercial",
        "open_interest",
        "long_commercial",
        "short_commercial",
    ]

    def read(self) -> pd.DataFrame:
        symbols = (
            [self.symbols] if isinstance(self.symbols, str) else list(self.symbols)
        )
        try:
            if len(symbols) == 1:
                return self._fetch_one(symbols[0])
            return self._fetch_many(symbols)
        finally:
            self.close()

    def _fetch_one(self, symbol: str) -> pd.DataFrame:
        currency = symbol.upper()
        url = f"{_API_BASE}/cot/{currency.lower()}"
        payload = _get(self.session, url, self._base_params())
        rows = payload.get("data", [])
        if not rows:
            return pd.DataFrame(columns=self._COT_COLS)
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["date"])
        df.index.name = "date"
        df = df.drop(columns=["date"], errors="ignore")
        present = [c for c in self._COT_COLS if c in df.columns]
        return df[present].sort_index()

    def _fetch_many(self, symbols: List[str]) -> dict:
        return {sym.upper(): self._fetch_one(sym) for sym in symbols}


# ---------------------------------------------------------------------------
# Unified convenience function
# ---------------------------------------------------------------------------


def get_data_fxmacrodata(
    name: Union[str, List[str]],
    start=None,
    end=None,
    api_key: Optional[str] = None,
    data_type: Optional[str] = None,
    retry_count: int = 3,
    pause: float = 0.1,
    session=None,
) -> pd.DataFrame:
    """
    Fetch data from the FXMacroData API into a pandas DataFrame.

    This is the primary entry point for the integration.  Pass a single
    symbol or a list of symbols and the function will auto-detect the data
    type from the symbol format unless ``data_type`` is specified explicitly.

    Auto-detection rules
    --------------------
    - ``"USD/inflation"`` or ``"USD_inflation"`` → macro indicator
    - ``"EURUSD"`` (6 chars) or ``"EUR/USD"`` → FX spot rate
    - ``"gold"`` / ``"silver"`` / ``"platinum"`` → precious metal
    - Otherwise treated as a macro indicator and the symbol must be in
      ``"CURRENCY/indicator"`` format.

    Parameters
    ----------
    name : str or list of str
        Symbol(s) to fetch.  See the symbol format notes above.
    start : str or datetime-like, optional
        Start of the date range.  Defaults to 5 years ago.
    end : str or datetime-like, optional
        End of the date range.  Defaults to today.
    api_key : str, optional
        FXMacroData Professional API key.  USD macro indicators and major FX
        pairs are free; all other data requires a Professional key.
        Falls back to the ``FXMACRODATA_API_KEY`` environment variable.
    data_type : {None, "indicator", "forex", "commodity", "cot"}, optional
        Override automatic type detection.
    retry_count : int, default 3
        Number of retry attempts on network failure.
    pause : float, default 0.1
        Seconds to wait between retries.
    session : requests.Session, optional
        Pre-configured requests Session.

    Returns
    -------
    pd.DataFrame

    Examples
    --------
    >>> import fxmacrodata_datareader as fxmd
    >>> df = fxmd.get_data_fxmacrodata("USD/inflation", "2020-01-01", "2024-12-31")
    >>> df.head()
                    val  announcement_datetime
    date
    2020-01-31  2.5     1580400000
    2020-02-29  2.3     1583078400

    >>> df = fxmd.get_data_fxmacrodata("EURUSD", "2022-01-01", "2024-12-31")
    >>> df.head()
                    val
    date
    2022-01-03  1.12895
    """
    kwargs = dict(
        start=start,
        end=end,
        api_key=api_key,
        retry_count=retry_count,
        pause=pause,
        session=session,
    )

    if data_type is None:
        data_type = _detect_type(name)

    if data_type == "indicator":
        return FXMacroDataIndicatorReader(name, **kwargs).read()
    if data_type == "forex":
        return FXMacroDataForexReader(name, **kwargs).read()
    if data_type == "commodity":
        return FXMacroDataCommoditiesReader(name, **kwargs).read()
    if data_type == "cot":
        return FXMacroDataCOTReader(name, **kwargs).read()
    raise ValueError(
        f"Unknown data_type {data_type!r}. "
        "Valid values: 'indicator', 'forex', 'commodity', 'cot'."
    )


def _detect_type(name: Union[str, List[str]]) -> str:
    """Infer the data type from the symbol string."""
    sample = name[0] if isinstance(name, list) else name
    sample_lower = sample.lower()

    if sample_lower in _COMMODITY_SYMBOLS:
        return "commodity"

    # 6-char alpha or slash-separated 3+3 → FX pair
    if "/" in sample:
        parts = sample.split("/")
        if len(parts) == 2 and all(len(p) == 3 for p in parts):
            return "forex"
    if len(sample) == 6 and sample.isalpha():
        return "forex"

    # "USD/inflation", "USD_inflation", "USD.inflation"
    for sep in ("/", "_"):
        if sep in sample:
            parts = sample.split(sep, 1)
            if len(parts) == 2 and len(parts[0]) == 3:
                return "indicator"

    return "indicator"


# ---------------------------------------------------------------------------
# pandas-datareader registration (monkey-patch)
# ---------------------------------------------------------------------------


def register() -> None:
    """
    Register FXMacroData as a data source in ``pandas_datareader.data.DataReader``.

    After calling this function, you can use the standard DataReader interface:

        import pandas_datareader as pdr
        import fxmacrodata_datareader as fxmd

        fxmd.register()

        df = pdr.DataReader("USD/inflation", "fxmacrodata", start, end)
        df = pdr.DataReader("EURUSD",        "fxmacrodata-forex", start, end)
        df = pdr.DataReader("gold",          "fxmacrodata-commodity", start, end)
        df = pdr.DataReader("EUR",           "fxmacrodata-cot", start, end,
                            api_key="YOUR_KEY")

    This patches ``pandas_datareader.data.DataReader`` in-place.  The patch is
    idempotent — calling ``register()`` multiple times is safe.

    Raises
    ------
    ImportError
        If ``pandas_datareader`` is not installed.
    """
    try:
        import pandas_datareader.data as pdr_data
    except ImportError as exc:
        raise ImportError(
            "pandas-datareader is not installed. "
            "Install it with: pip install pandas-datareader"
        ) from exc

    _FXMD_SOURCES = frozenset(
        {
            "fxmacrodata",
            "fxmacrodata-forex",
            "fxmacrodata-commodity",
            "fxmacrodata-cot",
        }
    )

    original_dr = pdr_data.DataReader

    def _patched_DataReader(
        name,
        data_source=None,
        start=None,
        end=None,
        retry_count=3,
        pause=0.1,
        session=None,
        api_key=None,
    ):
        if data_source not in _FXMD_SOURCES:
            return original_dr(
                name,
                data_source=data_source,
                start=start,
                end=end,
                retry_count=retry_count,
                pause=pause,
                session=session,
                api_key=api_key,
            )

        kwargs = dict(
            start=start,
            end=end,
            api_key=api_key,
            retry_count=retry_count,
            pause=pause,
            session=session,
        )

        if data_source == "fxmacrodata":
            return get_data_fxmacrodata(name, **kwargs)
        if data_source == "fxmacrodata-forex":
            return FXMacroDataForexReader(name, **kwargs).read()
        if data_source == "fxmacrodata-commodity":
            return FXMacroDataCommoditiesReader(name, **kwargs).read()
        if data_source == "fxmacrodata-cot":
            return FXMacroDataCOTReader(name, **kwargs).read()

    # Preserve docstring and name for introspection
    _patched_DataReader.__doc__ = original_dr.__doc__
    _patched_DataReader.__name__ = original_dr.__name__

    pdr_data.DataReader = _patched_DataReader
