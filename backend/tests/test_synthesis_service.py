"""
Unit tests for AI Synthesis Agent and Compliance Checker.
Verifies Section 3 rules and zero buy/sell advisory language.
"""

import pytest
from app.services.synthesis_service import check_compliance, synthesize_reasons
from app.db.models import FactorLog
from app.db.schemas import NewsItemSchema


def test_compliance_checker_passes_clean_text():
    text = "Setup structure is supported by positive volume momentum and MA stack."
    assert check_compliance(text) is True


def test_compliance_checker_rejects_advisory_text():
    bad_texts = [
        "Buy this stock immediately before earnings.",
        "Strong sell recommended due to high risk.",
        "Our target price is $150 based on analyst models.",
        "Investors should enter long position now.",
    ]
    for t in bad_texts:
        assert check_compliance(t) is False


@pytest.mark.asyncio
async def test_synthesize_reasons_fallback_without_mock_data():
    """Verify that when LLM is offline or unconfigured, we fall back to safe deterministic factor descriptions without mock data."""
    flog = FactorLog(
        scan_id=1,
        factor_id="F47",
        factor_name="Pre-Earnings Binary Exit",
        layer_number=5,
        triggered=True,
        vetoed=True,
        stubbed=False,
    )
    reasons = await synthesize_reasons("NVDA", 8.5, [flog], [])
    assert len(reasons) == 1
    assert reasons[0].type == "bear"
    assert reasons[0].code == "F47"
    assert "restricted by risk rule" in reasons[0].text
