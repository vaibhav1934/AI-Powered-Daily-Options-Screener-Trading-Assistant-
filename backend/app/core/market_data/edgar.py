"""
SEC EDGAR Market Data Client
==============================
Queries official SEC EDGAR submissions API for dilution/shelf registration filings (F46).
Enforces SEC User-Agent requirements and 10 req/s rate limits.
No mock or fallback data: raises error or reports explicit UNAVAILABLE status if API fails.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.core.cache import get_cached_response, set_cached_response
from app.core.rate_limiter import rate_limiter_registry

logger = logging.getLogger(__name__)

SEC_SUBMISSION_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT = "StockGlassAI/1.0 (contact@stockglass.ai)"
SHELF_FORMS = {"S-3", "S-3/A", "S-3ASR", "424B5", "S-1", "S-1/A"}
LOOKBACK_DAYS = 90


class EdgarClient:
    """
    Client for SEC EDGAR submissions and filing inspections.
    Uses rate limiter (sec_edgar: 10 req/s) and Postgres caching.
    """

    provider_name: str = "sec_edgar"

    def __init__(self) -> None:
        self._cache_ttl = 21600  # 6 hours TTL for EDGAR filing lists
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        )
        # Ensure sec_edgar is registered in rate limiter if not already
        try:
            rate_limiter_registry.get(self.provider_name)
        except ValueError:
            rate_limiter_registry.register(self.provider_name, max_calls=10, window_seconds=1.0)

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        session: Any = None,
    ) -> dict[str, Any]:
        """Make rate-limited, cached request to SEC EDGAR."""
        if session:
            cached = await get_cached_response(
                session=session,
                provider=self.provider_name,
                endpoint=endpoint,
                params=params,
            )
            if cached is not None:
                is_stale = cached.get("_cache_stale", False) if isinstance(cached, dict) else False
                if not is_stale:
                    logger.debug("Cache hit for EDGAR %s", endpoint)
                    return cached

        await rate_limiter_registry.acquire(self.provider_name)

        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

        if session:
            await set_cached_response(
                session=session,
                provider=self.provider_name,
                endpoint=endpoint,
                params=params,
                response_json=data,
                ttl_seconds=self._cache_ttl,
            )

        return data

    async def check_shelf_registration(
        self, cik: Optional[str], session: Any = None
    ) -> dict[str, Any]:
        """
        Check if the CIK has recent shelf registration / dilution filings (last 90 days).
        Returns dict with has_shelf_filing, form_type, recent_filing_date, and status.
        Raises exception or reports UNAVAILABLE if SEC EDGAR is unreachable (No mock data rule).
        """
        if not cik:
            logger.warning("No CIK provided for shelf registration check.")
            return {
                "status": "UNCONFIGURED",
                "has_shelf_filing": False,
                "form_type": None,
                "recent_filing_date": None,
                "detail": "No SEC CIK mapped for this ticker in database.",
            }

        cik_str = str(cik).strip().zfill(10)
        url = SEC_SUBMISSION_URL.format(cik=cik_str)

        try:
            data = await self._request(url, params={}, session=session)
        except Exception as e:
            logger.error("SEC EDGAR filing check failed for CIK %s: %s", cik_str, e)
            return {
                "status": "UNAVAILABLE",
                "has_shelf_filing": None,
                "form_type": None,
                "recent_filing_date": None,
                "error": str(e),
                "detail": f"SEC EDGAR API unreachable or rate limited ({e}). No fallback data provided.",
            }

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])

        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

        for idx, form in enumerate(forms):
            filing_date = dates[idx] if idx < len(dates) else ""
            if filing_date < cutoff_date:
                # Filings are chronologically ordered (newest first in recent), so we can break early
                break
            if form in SHELF_FORMS:
                logger.info("Shelf dilution filing %s found for CIK %s on %s", form, cik_str, filing_date)
                return {
                    "status": "LIVE",
                    "has_shelf_filing": True,
                    "form_type": form,
                    "recent_filing_date": filing_date,
                    "detail": f"Recent {form} shelf/dilution filing detected on {filing_date} (within {LOOKBACK_DAYS} days).",
                }

        return {
            "status": "LIVE",
            "has_shelf_filing": False,
            "form_type": None,
            "recent_filing_date": None,
            "detail": f"SEC EDGAR checked: no S-3/424B5 shelf dilution filings in last {LOOKBACK_DAYS} days.",
        }

    async def resolve_cik_for_ticker(self, ticker: str, session: Any = None) -> Optional[str]:
        """Resolve a ticker symbol to 10-digit SEC CIK using the official SEC ticker map."""
        ticker_u = (ticker or "").strip().upper()
        if not ticker_u:
            return None

        data = await self._request(SEC_TICKERS_URL, params={}, session=session)
        if not isinstance(data, dict):
            return None

        for row in data.values():
            if not isinstance(row, dict):
                continue
            if str(row.get("ticker", "")).upper() == ticker_u:
                cik_val = row.get("cik_str")
                if isinstance(cik_val, int):
                    return str(cik_val).zfill(10)
                if isinstance(cik_val, str) and cik_val.strip().isdigit():
                    return cik_val.strip().zfill(10)
        return None

    async def get_company_facts(self, cik: str, session: Any = None) -> dict[str, Any]:
        """Fetch SEC XBRL company facts payload for a CIK."""
        cik_str = str(cik).strip().zfill(10)
        url = SEC_COMPANY_FACTS_URL.format(cik=cik_str)
        return await self._request(url, params={}, session=session)

    async def get_company_facts_by_ticker(self, ticker: str, session: Any = None) -> tuple[Optional[str], Optional[dict[str, Any]]]:
        """Resolve ticker -> CIK and return company facts in one call path."""
        cik = await self.resolve_cik_for_ticker(ticker=ticker, session=session)
        if not cik:
            return None, None
        try:
            facts = await self.get_company_facts(cik=cik, session=session)
            return cik, facts if isinstance(facts, dict) else None
        except Exception:
            return cik, None

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self._client.aclose()


def _safe_float(val: Any) -> Optional[float]:
    if isinstance(val, (int, float)):
        return float(val)
    return None


def extract_latest_company_fact(
    company_facts: dict[str, Any],
    concept: str,
    unit_preferences: tuple[str, ...] = ("USD",),
    taxonomy: str = "us-gaap",
) -> Optional[float]:
    """Extract the latest numeric value for a given XBRL concept."""
    facts_root = ((company_facts or {}).get("facts") or {}).get(taxonomy, {})
    concept_obj = facts_root.get(concept, {}) if isinstance(facts_root, dict) else {}
    units = concept_obj.get("units", {}) if isinstance(concept_obj, dict) else {}
    if not isinstance(units, dict) or not units:
        return None

    series: list[dict[str, Any]] = []
    for unit_name in unit_preferences:
        unit_rows = units.get(unit_name)
        if isinstance(unit_rows, list) and unit_rows:
            series = unit_rows
            break

    if not series:
        first_rows = next(iter(units.values()), None)
        if isinstance(first_rows, list):
            series = first_rows

    numeric_rows: list[dict[str, Any]] = [r for r in series if _safe_float(r.get("val")) is not None]
    if not numeric_rows:
        return None

    def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row.get("end", "")), str(row.get("filed", ""))

    latest = sorted(numeric_rows, key=_sort_key, reverse=True)[0]
    return _safe_float(latest.get("val"))


def extract_latest_two_annual_facts(
    company_facts: dict[str, Any],
    concept: str,
    unit_preferences: tuple[str, ...] = ("USD",),
    taxonomy: str = "us-gaap",
) -> tuple[Optional[float], Optional[float]]:
    """Extract latest and prior annual values (10-K/20-F/40-F) for a concept."""
    facts_root = ((company_facts or {}).get("facts") or {}).get(taxonomy, {})
    concept_obj = facts_root.get(concept, {}) if isinstance(facts_root, dict) else {}
    units = concept_obj.get("units", {}) if isinstance(concept_obj, dict) else {}
    if not isinstance(units, dict) or not units:
        return None, None

    series: list[dict[str, Any]] = []
    for unit_name in unit_preferences:
        unit_rows = units.get(unit_name)
        if isinstance(unit_rows, list) and unit_rows:
            series = unit_rows
            break

    if not series:
        first_rows = next(iter(units.values()), None)
        if isinstance(first_rows, list):
            series = first_rows

    annual_forms = {"10-K", "20-F", "40-F"}
    annual_rows: list[dict[str, Any]] = []
    for row in series:
        val = _safe_float(row.get("val"))
        form = str(row.get("form", ""))
        if val is None or form not in annual_forms:
            continue
        annual_rows.append(row)

    if not annual_rows:
        return None, None

    def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row.get("end", "")), str(row.get("filed", ""))

    ordered = sorted(annual_rows, key=_sort_key, reverse=True)
    latest = _safe_float(ordered[0].get("val"))
    previous = _safe_float(ordered[1].get("val")) if len(ordered) > 1 else None
    return latest, previous
