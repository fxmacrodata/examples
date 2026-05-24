"""
FXMacroData — QuantConnect LEAN Custom Data Types
==================================================

Provides ``PythonData`` sub-classes for ingesting FXMacroData API time series
into LEAN backtests and live-trading algorithms.

Three data types are available:

* ``FXMacroIndicator`` — macroeconomic indicator series (policy rate, inflation,
  GDP, unemployment, PMI, …)  sourced from central banks and statistical agencies.
* ``FXMacroForex``     — daily FX spot-rate series (ECB reference rates).
* ``FXMacroCOT``       — CFTC Commitment of Traders weekly positioning data.

Quick start
-----------
::

    from fxmacrodata.lean import FXMacroIndicator, FXMacroForex, FXMacroCOT

    # Inside QCAlgorithm.initialize():
    usd_rate = self.add_data(FXMacroIndicator, "USD_POLICY_RATE").symbol
    eur_infl = self.add_data(FXMacroIndicator, "EUR_INFLATION").symbol
    eurusd   = self.add_data(FXMacroForex,     "EURUSD").symbol
    eur_cot  = self.add_data(FXMacroCOT,       "EUR").symbol

    # Inside on_data(slice):
    if slice.contains_key(usd_rate):
        rate = slice[usd_rate].value

Authentication
--------------
Set the ``FXMACRODATA_API_KEY`` environment variable to your Professional key.
USD announcement data is public — no key required.

    * QuantConnect Cloud:  Algorithm configuration → Environment variables
    * Local LEAN:          export FXMACRODATA_API_KEY=your_key_here

Full indicator catalogue: https://fxmacrodata.com/documentation
API key management:       https://fxmacrodata.com/api-management
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "requests is required.  Install it with:  pip install requests"
    ) from exc

try:
    from AlgorithmImports import (
        Globals,
        PythonData,
        SubscriptionDataSource,
        SubscriptionTransportMedium,
    )

    _LEAN_AVAILABLE = True
except ImportError:
    # Allow the module to be imported outside LEAN for tooling / unit-testing.
    _LEAN_AVAILABLE = False
    PythonData = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

_API_BASE = "https://fxmacrodata.com/api/v1"
_DEFAULT_START = "1990-01-01"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _api_key() -> Optional[str]:
    return os.environ.get("FXMACRODATA_API_KEY") or None


def _data_root() -> Path:
    """Return a directory for cached LEAN flat files."""
    if _LEAN_AVAILABLE:
        try:
            root = Path(Globals.data_folder) / "fxmacrodata"
        except Exception:  # noqa: BLE001
            root = Path(".cache") / "fxmacrodata"
    else:
        root = Path(".cache") / "fxmacrodata"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fetch_json(url: str, params: dict) -> dict:
    key = _api_key()
    if key:
        params = {**params, "api_key": key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# FXMacroIndicator
# ---------------------------------------------------------------------------


class FXMacroIndicator(PythonData):
    """Macroeconomic indicator time series from the FXMacroData API.

    **Symbol format:** ``{CURRENCY}_{INDICATOR}``  (case-insensitive).

    Examples::

        self.add_data(FXMacroIndicator, "USD_POLICY_RATE")
        self.add_data(FXMacroIndicator, "EUR_INFLATION")
        self.add_data(FXMacroIndicator, "AUD_GDP")
        self.add_data(FXMacroIndicator, "JPY_UNEMPLOYMENT")

    The ``value`` property holds the indicator reading for that release.
    The optional ``announcement_datetime`` dynamic property contains the Unix
    timestamp of the official release time (when known).

    USD announcement data is public; all other currencies require a Professional API key set
    via the ``FXMACRODATA_API_KEY`` environment variable.

    **Available indicators (subset):**
    ``policy_rate``, ``inflation``, ``core_inflation``, ``gdp``,
    ``gdp_quarterly``, ``unemployment``, ``non_farm_payrolls``,
    ``retail_sales``, ``pmi``, ``trade_balance``, ``ppi``, ``cpi``, and 40+
    more.  Full catalogue: https://fxmacrodata.com/documentation
    """

    def get_source(self, config, date, is_live_mode):
        symbol = config.symbol.value.lower()
        parts = symbol.split("_", 1)
        if len(parts) != 2:
            raise ValueError(
                f"FXMacroIndicator symbol must be '{{CURRENCY}}_{{INDICATOR}}'"
                f", got '{config.symbol.value}'.  Example: 'USD_POLICY_RATE'."
            )
        currency, indicator = parts

        cache_file = _data_root() / "indicators" / currency / f"{indicator}.csv"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if not cache_file.exists():
            _download_indicator(currency, indicator, cache_file)

        return SubscriptionDataSource(
            str(cache_file),
            SubscriptionTransportMedium.LOCAL_FILE,
        )

    def reader(self, config, line, date, is_live_mode):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("date"):
            return None

        try:
            parts = line.split(",")
            point = FXMacroIndicator()
            point.symbol = config.symbol
            point.time = datetime.strptime(parts[0], "%Y-%m-%d")
            point.end_time = point.time + timedelta(days=1)
            point.value = float(parts[1]) if parts[1] else float("nan")
            if len(parts) > 2 and parts[2]:
                point["announcement_datetime"] = int(parts[2])
            return point
        except Exception as exc:  # noqa: BLE001
            logger.debug("FXMacroIndicator.reader — skipping line: %s  (%s)", line, exc)
            return None


def _download_indicator(currency: str, indicator: str, cache_file: Path) -> None:
    """Fetch an indicator series from the API and write it as a LEAN flat CSV."""
    logger.info("FXMacroData: downloading %s/%s …", currency, indicator)
    url = f"{_API_BASE}/announcements/{currency}/{indicator}"
    payload = _fetch_json(url, {"start_date": _DEFAULT_START})
    rows = payload.get("data", [])

    with cache_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "value", "announcement_datetime"])
        for row in sorted(rows, key=lambda r: r["date"]):
            writer.writerow(
                [
                    row["date"],
                    row.get("val", ""),
                    row.get("announcement_datetime", ""),
                ]
            )
    logger.info("FXMacroData: cached %d rows → %s", len(rows), cache_file)


# ---------------------------------------------------------------------------
# FXMacroForex
# ---------------------------------------------------------------------------


class FXMacroForex(PythonData):
    """Daily FX spot-rate series from the FXMacroData API.

    **Symbol format:** ``{BASE}{QUOTE}``  (6-character pair, case-insensitive).

    Examples::

        self.add_data(FXMacroForex, "EURUSD")
        self.add_data(FXMacroForex, "AUDUSD")
        self.add_data(FXMacroForex, "USDJPY")
        self.add_data(FXMacroForex, "GBPUSD")

    The ``value`` property holds the closing spot rate.

    Supported bases/quotes: AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY,
    NZD, PLN, SEK, SGD, USD.
    """

    def get_source(self, config, date, is_live_mode):
        pair = config.symbol.value.upper()
        if len(pair) != 6:
            raise ValueError(
                f"FXMacroForex symbol must be a 6-char pair like 'EURUSD'"
                f", got '{pair}'."
            )
        base, quote = pair[:3], pair[3:]

        cache_file = _data_root() / "forex" / f"{pair.lower()}.csv"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if not cache_file.exists():
            _download_forex(base, quote, cache_file)

        return SubscriptionDataSource(
            str(cache_file),
            SubscriptionTransportMedium.LOCAL_FILE,
        )

    def reader(self, config, line, date, is_live_mode):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("date"):
            return None

        try:
            parts = line.split(",")
            point = FXMacroForex()
            point.symbol = config.symbol
            point.time = datetime.strptime(parts[0], "%Y-%m-%d")
            point.end_time = point.time + timedelta(days=1)
            point.value = float(parts[1]) if parts[1] else float("nan")
            return point
        except Exception as exc:  # noqa: BLE001
            logger.debug("FXMacroForex.reader — skipping line: %s  (%s)", line, exc)
            return None


def _download_forex(base: str, quote: str, cache_file: Path) -> None:
    """Fetch FX spot rates from the API and write as a LEAN flat CSV."""
    logger.info("FXMacroData: downloading forex %s/%s …", base, quote)
    url = f"{_API_BASE}/forex/{base}/{quote}"
    payload = _fetch_json(url, {"start_date": _DEFAULT_START})
    rows = payload.get("data", [])

    with cache_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "close"])
        for row in sorted(rows, key=lambda r: r["date"]):
            writer.writerow([row["date"], row.get("val", "")])
    logger.info("FXMacroData: cached %d rows → %s", len(rows), cache_file)


# ---------------------------------------------------------------------------
# FXMacroCOT
# ---------------------------------------------------------------------------


class FXMacroCOT(PythonData):
    """CFTC Commitment of Traders (COT) weekly positioning data.

    **Symbol format:** ``{CURRENCY}``  (3-char ISO code, case-insensitive).

    **Supported currencies:** AUD, CAD, CHF, EUR, GBP, JPY, NZD.

    Examples::

        self.add_data(FXMacroCOT, "EUR")
        self.add_data(FXMacroCOT, "JPY")
        self.add_data(FXMacroCOT, "GBP")

    ``value`` equals ``noncommercial_net`` (longs minus shorts for
    non-commercial / speculative traders).

    Additional dynamic properties:
        * ``long_positions``  — non-commercial long contracts
        * ``short_positions`` — non-commercial short contracts
        * ``open_interest``   — total open interest
        * ``announcement_datetime`` — Unix timestamp of the CFTC release

    A Professional API key (``FXMACRODATA_API_KEY``) is required.
    """

    def get_source(self, config, date, is_live_mode):
        currency = config.symbol.value.upper()

        cache_file = _data_root() / "cot" / f"{currency.lower()}.csv"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        if not cache_file.exists():
            _download_cot(currency, cache_file)

        return SubscriptionDataSource(
            str(cache_file),
            SubscriptionTransportMedium.LOCAL_FILE,
        )

    def reader(self, config, line, date, is_live_mode):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("date"):
            return None

        try:
            parts = line.split(",")
            point = FXMacroCOT()
            point.symbol = config.symbol
            point.time = datetime.strptime(parts[0], "%Y-%m-%d")
            point.end_time = point.time + timedelta(days=1)
            # value = noncommercial net (longs - shorts)
            point.value = float(parts[1]) if parts[1] else float("nan")
            if len(parts) > 2 and parts[2]:
                point["long_positions"] = float(parts[2])
            if len(parts) > 3 and parts[3]:
                point["short_positions"] = float(parts[3])
            if len(parts) > 4 and parts[4]:
                point["open_interest"] = float(parts[4])
            if len(parts) > 5 and parts[5]:
                point["announcement_datetime"] = int(parts[5])
            return point
        except Exception as exc:  # noqa: BLE001
            logger.debug("FXMacroCOT.reader — skipping line: %s  (%s)", line, exc)
            return None


def _download_cot(currency: str, cache_file: Path) -> None:
    """Fetch COT data from the API and write as a LEAN flat CSV."""
    logger.info("FXMacroData: downloading COT %s …", currency)
    url = f"{_API_BASE}/cot/{currency}"
    payload = _fetch_json(url, {"start_date": _DEFAULT_START})
    rows = payload.get("data", [])

    with cache_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "noncommercial_net",
                "long_positions",
                "short_positions",
                "open_interest",
                "announcement_datetime",
            ]
        )
        for row in sorted(rows, key=lambda r: r["date"]):
            writer.writerow(
                [
                    row["date"],
                    row.get("noncommercial_net", ""),
                    row.get("noncommercial_long", ""),
                    row.get("noncommercial_short", ""),
                    row.get("open_interest", ""),
                    row.get("announcement_datetime", ""),
                ]
            )
    logger.info("FXMacroData: cached %d rows → %s", len(rows), cache_file)
