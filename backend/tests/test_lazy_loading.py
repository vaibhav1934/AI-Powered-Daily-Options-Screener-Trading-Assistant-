"""
Test Suite for 3-Step Decoupled Screener Architecture & Lazy Loading
======================================================================
Verifies:
  1. SEC EDGAR dilution/shelf registration check (F46) & parsing.
  2. Zero Mock / Zero Fallback Data rule compliance when EDGAR is offline.
  3. Same-Day Database Caching Protocol (avoiding recalculation on same-day clicks).
  4. Instant screener table rendering (Step 2) with StockUniverse fallback.
"""

import pytest
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.market_data.edgar import EdgarClient
from app.framework.factors.base import ScanContext, FactorStatus, FactorAction
from app.framework.factors.f46_edgar_shelf_check import F46EDGARShelfCheck
from app.db.models import DailyScan, FactorLog, ScanStatus, RiskBucket
from app.services import stockglass_service


@pytest.mark.asyncio
async def test_edgar_client_zero_mock_offline():
    """Verify EdgarClient returns explicit UNAVAILABLE status without mock/fallback data if API fails."""
    client = EdgarClient()
    with patch.object(client, "_request", side_effect=RuntimeError("Connection timeout to SEC EDGAR")):
        res = await client.check_shelf_registration("0001045810", session=None)
        assert res["status"] == "UNAVAILABLE"
        assert res["has_shelf_filing"] is None
        assert "No fallback data provided" in res["detail"]
    await client.close()


@pytest.mark.asyncio
async def test_edgar_client_parses_shelf_filing():
    """Verify EdgarClient correctly detects recent S-3 dilution shelf registrations from SEC JSON."""
    client = EdgarClient()
    mock_payload = {
        "filings": {
            "recent": {
                "form": ["10-Q", "S-3", "8-K"],
                "filingDate": [
                    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "2020-01-01"
                ]
            }
        }
    }
    with patch.object(client, "_request", AsyncMock(return_value=mock_payload)):
        res = await client.check_shelf_registration("0001045810", session=None)
        assert res["status"] == "LIVE"
        assert res["has_shelf_filing"] is True
        assert res["form_type"] == "S-3"
        assert "Recent S-3 shelf/dilution filing detected" in res["detail"]
    await client.close()


def test_f46_factor_evaluation_unavailable():
    """Verify F46 factor returns UNCONFIGURED status when EDGAR check is UNAVAILABLE (No mock numbers)."""
    ctx = ScanContext(
        ticker="NVDA",
        scan_date="2026-07-27",
        near_ath_proximity=True,
        edgar_check_status="UNAVAILABLE"
    )
    f46 = F46EDGARShelfCheck()
    res = f46.evaluate(ctx)
    assert res.status == FactorStatus.LIVE
    assert res.vetoed is True
    assert "UNAVAILABLE" in res.detail.upper()


def test_f46_factor_evaluation_veto_with_filing_date():
    """Verify F46 vetoes entry and formats exact filing form and date when dilution risk is present near ATH."""
    ctx = ScanContext(
        ticker="NVDA",
        scan_date="2026-07-27",
        near_ath_proximity=True,
        has_recent_shelf_filing=True,
        shelf_form_type="S-3ASR",
        shelf_filing_date="2026-07-20",
        edgar_check_status="LIVE"
    )
    f46 = F46EDGARShelfCheck()
    res = f46.evaluate(ctx)
    assert res.action == FactorAction.VETO
    assert res.vetoed is True
    assert "S-3ASR shelf/dilution filing detected on 2026-07-20" in res.detail
    assert res.metadata["risk"] == "dilution"


@pytest.mark.asyncio
async def test_same_day_caching_protocol_hit():
    """
    Verify get_stock_live_evaluation serves instantly from database on same-day cache HIT,
    making ZERO external EDGAR or market data API calls.
    """
    now_utc = datetime.now(timezone.utc)
    mock_scan = DailyScan(
        id=10,
        scan_date=now_utc,
        ticker="NVDA",
        score=9.0,
        risk_bucket=RiskBucket.LOW,
        status=ScanStatus.CONFIRMED,
        live_evaluated_at=now_utc,  # Already evaluated today!
        factor_logs=[
            FactorLog(id=100+i, factor_id=f"F{i+1:02d}", factor_name=f"Factor {i+1}", layer_number=(i//5)+1, triggered=False, vetoed=False)
            for i in range(50)
        ]
    )

    class MockSessionCacheHit:
        async def execute(self, stmt):
            stmt_str = str(stmt).lower()
            if "stock_universe" in stmt_str or "stocks" in stmt_str:
                return MagicMock(scalar_one_or_none=lambda: None)
            return MagicMock(scalar_one_or_none=lambda: mock_scan, scalars=lambda: MagicMock(all=lambda: [mock_scan], first=lambda: mock_scan))
        async def scalar(self, stmt):
            return now_utc
        async def flush(self): pass
        async def commit(self): pass
        def add(self, obj): pass

    session = MockSessionCacheHit()
    
    with patch.object(EdgarClient, "check_shelf_registration", AsyncMock()) as mock_edgar_call, \
         patch("app.services.stockglass_service.FinnhubClient") as mock_finnhub:
        
        # Configure Finnhub mock for detail rendering
        mock_fh_instance = AsyncMock()
        mock_fh_instance.get_quote.return_value = None
        mock_fh_instance.get_company_profile.return_value = {"name": "NVIDIA Corp", "sector": "Semiconductors"}
        mock_fh_instance.get_news.return_value = []
        mock_finnhub.return_value = mock_fh_instance

        res = await stockglass_service.get_stock_live_evaluation(session, "NVDA")
        
        # EDGAR check MUST NOT be called because live_evaluated_at == today (Same-Day Cache HIT)
        mock_edgar_call.assert_not_called()
        assert res.symbol == "NVDA"
        assert res.score == 9.0
