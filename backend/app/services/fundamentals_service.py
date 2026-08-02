"""
Fundamentals Service
====================
Fetches long-term fundamental metrics from live data feeds.
Returns None for missing fields rather than fabricating values.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.market_data.edgar import (
    EdgarClient,
    extract_latest_company_fact,
    extract_latest_two_annual_facts,
)


def _to_float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _fetch_fundamentals_sync(ticker: str) -> dict[str, float | None]:
    import yfinance as yf

    info = yf.Ticker(ticker).info or {}

    return {
        "revenue_growth": _to_float_or_none(info.get("revenueGrowth")),
        "gross_margin": _to_float_or_none(info.get("grossMargins")),
        "operating_margin": _to_float_or_none(info.get("operatingMargins")),
        "free_cash_flow": _to_float_or_none(info.get("freeCashflow")),
        "debt_to_equity": _to_float_or_none(info.get("debtToEquity")),
        "interest_coverage": _to_float_or_none(info.get("interestCoverage")),
        "insider_ownership": _to_float_or_none(info.get("heldPercentInsiders")),
        "institutional_ownership": _to_float_or_none(info.get("heldPercentInstitutions")),
        "return_on_equity": _to_float_or_none(info.get("returnOnEquity")),
        "return_on_assets": _to_float_or_none(info.get("returnOnAssets")),
        "shares_outstanding_change": _to_float_or_none(info.get("sharesOutstandingChange")),
        "short_ratio": _to_float_or_none(info.get("shortRatio")),
        "short_percent_float": _to_float_or_none(info.get("shortPercentOfFloat")),
        "trailing_pe": _to_float_or_none(info.get("trailingPE")),
        "forward_pe": _to_float_or_none(info.get("forwardPE")),
        "peg_ratio": _to_float_or_none(info.get("pegRatio")),
    }


async def get_fundamentals(ticker: str) -> dict[str, float | None]:
    yfinance_data: dict[str, float | None]
    try:
        yfinance_data = await asyncio.to_thread(_fetch_fundamentals_sync, ticker)
    except Exception:
        yfinance_data = {
            "revenue_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "free_cash_flow": None,
            "debt_to_equity": None,
            "interest_coverage": None,
            "insider_ownership": None,
            "institutional_ownership": None,
            "return_on_equity": None,
            "return_on_assets": None,
            "shares_outstanding_change": None,
            "short_ratio": None,
            "short_percent_float": None,
            "trailing_pe": None,
            "forward_pe": None,
            "peg_ratio": None,
        }

    result = dict(yfinance_data)

    edgar_client = EdgarClient()
    try:
        _cik, company_facts = await edgar_client.get_company_facts_by_ticker(ticker=ticker)
    except Exception:
        company_facts = None
    finally:
        await edgar_client.close()

    if not company_facts:
        return result

    revenue_latest, revenue_prev = extract_latest_two_annual_facts(
        company_facts,
        concept="Revenues",
        unit_preferences=("USD",),
    )

    if (revenue_latest is None or revenue_prev is None):
        revenue_latest, revenue_prev = extract_latest_two_annual_facts(
            company_facts,
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
            unit_preferences=("USD",),
        )

    cost_of_revenue = extract_latest_company_fact(company_facts, concept="CostOfRevenue", unit_preferences=("USD",))
    operating_income = extract_latest_company_fact(company_facts, concept="OperatingIncomeLoss", unit_preferences=("USD",))
    cfo = extract_latest_company_fact(company_facts, concept="NetCashProvidedByUsedInOperatingActivities", unit_preferences=("USD",))
    capex = extract_latest_company_fact(company_facts, concept="PaymentsToAcquirePropertyPlantAndEquipment", unit_preferences=("USD",))
    long_term_debt = extract_latest_company_fact(company_facts, concept="LongTermDebt", unit_preferences=("USD",))
    current_debt = extract_latest_company_fact(company_facts, concept="DebtCurrent", unit_preferences=("USD",))
    stockholders_equity = extract_latest_company_fact(company_facts, concept="StockholdersEquity", unit_preferences=("USD",))
    interest_expense = extract_latest_company_fact(company_facts, concept="InterestExpense", unit_preferences=("USD",))

    edgar_revenue_growth: float | None = None
    if revenue_latest is not None and revenue_prev not in (None, 0.0):
        edgar_revenue_growth = (revenue_latest - revenue_prev) / revenue_prev

    edgar_gross_margin: float | None = None
    if revenue_latest not in (None, 0.0) and cost_of_revenue is not None:
        edgar_gross_margin = (revenue_latest - cost_of_revenue) / revenue_latest

    edgar_operating_margin: float | None = None
    if revenue_latest not in (None, 0.0) and operating_income is not None:
        edgar_operating_margin = operating_income / revenue_latest

    edgar_free_cash_flow: float | None = None
    if cfo is not None and capex is not None:
        edgar_free_cash_flow = cfo - abs(capex)

    edgar_debt_to_equity: float | None = None
    if stockholders_equity not in (None, 0.0):
        total_debt = (long_term_debt or 0.0) + (current_debt or 0.0)
        edgar_debt_to_equity = total_debt / stockholders_equity

    edgar_interest_coverage: float | None = None
    if operating_income is not None and interest_expense not in (None, 0.0):
        edgar_interest_coverage = operating_income / abs(interest_expense)

    # Prefer direct market-source values where available; fill nulls with SEC-derived facts.
    if result.get("revenue_growth") is None:
        result["revenue_growth"] = edgar_revenue_growth
    if result.get("gross_margin") is None:
        result["gross_margin"] = edgar_gross_margin
    if result.get("operating_margin") is None:
        result["operating_margin"] = edgar_operating_margin
    if result.get("free_cash_flow") is None:
        result["free_cash_flow"] = edgar_free_cash_flow
    if result.get("debt_to_equity") is None:
        result["debt_to_equity"] = edgar_debt_to_equity
    if result.get("interest_coverage") is None:
        result["interest_coverage"] = edgar_interest_coverage

    return result
