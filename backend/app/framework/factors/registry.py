"""
Factor Registry
=================
Maps F1–F50 to their implementations.
Exposes get_live_factors() / get_stubbed_factors() so scan output
is never silently incomplete.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.framework.factors.base import BaseFactor, FactorStatus
from app.framework.factors.f40_no_clean_setup import F40NoCleanSetup
from app.framework.factors.f41_bear_case_first import F41BearCaseFirst
from app.framework.factors.f42_entry_cutoff import F42EntryCutoff
from app.framework.factors.f43_ath_record_earnings import F43ATHRecordEarnings
from app.framework.factors.f44_analyst_tier_weighting import F44AnalystTierWeighting
from app.framework.factors.f45_fomc_reduction import F45FOMCReduction
from app.framework.factors.f46_edgar_shelf_check import F46EDGARShelfCheck
from app.framework.factors.f47_pre_earnings_exit import F47PreEarningsBinaryExit
from app.framework.factors.f48_gap_hold_protocol import F48GapHoldProtocol
from app.framework.factors.f49_boj_kospi_rule import F49BOJKOSPIRule
from app.framework.factors.f50_war_tape_rule import F50WarTapeRule
from app.framework.factors.f1_to_f39_spec import build_f1_to_f39

logger = logging.getLogger(__name__)


class FactorRegistry:
    """
    Central registry of all 50 factors (F1–F50).
    F40–F50: live implementations with real trigger/action logic.
    F1–F39: framework-aligned definitions. Factors without wired inputs are
    explicitly marked UNCONFIGURED at evaluation time.

    Provides introspection methods to query live vs. stubbed factors.
    """

    def __init__(self) -> None:
        self._factors: dict[str, BaseFactor] = {}
        self._register_all()

    def _register_all(self) -> None:
        """Register all 50 factors."""
        # F1–F39: Framework-aligned definitions
        for factor in build_f1_to_f39():
            self._factors[factor.factor_id] = factor

        # F40–F50: Live implementations
        live_factors: list[BaseFactor] = [
            F40NoCleanSetup(),
            F41BearCaseFirst(),
            F42EntryCutoff(),
            F43ATHRecordEarnings(),
            F44AnalystTierWeighting(),
            F45FOMCReduction(),
            F46EDGARShelfCheck(),
            F47PreEarningsBinaryExit(),
            F48GapHoldProtocol(),
            F49BOJKOSPIRule(),
            F50WarTapeRule(),
        ]

        for factor in live_factors:
            self._factors[factor.factor_id] = factor

        for fid, f in self._factors.items():
            try:
                num = int(fid.replace("F", ""))
                f.layer = (num - 1) // 5 + 1
            except ValueError:
                pass

        live_count = len(self.get_live_factors())
        stub_count = len(self.get_stubbed_factors())
        logger.info(
            "Factor registry initialized: %d total (%d live, %d stubbed)",
            len(self._factors),
            live_count,
            stub_count,
        )

    def get(self, factor_id: str) -> Optional[BaseFactor]:
        """Get a factor by ID."""
        return self._factors.get(factor_id)

    def get_all(self) -> list[BaseFactor]:
        """Get all 50 factors, ordered by ID."""
        return sorted(self._factors.values(), key=lambda f: f.factor_id)

    def get_live_factors(self) -> list[BaseFactor]:
        """Get only live (implemented) factors."""
        return [f for f in self._factors.values() if f.status == FactorStatus.LIVE]

    def get_stubbed_factors(self) -> list[BaseFactor]:
        """Get only stubbed (unconfigured) factors."""
        return [f for f in self._factors.values() if f.status == FactorStatus.UNCONFIGURED]

    def get_factors_for_layer(self, layer: int) -> list[BaseFactor]:
        """Get all factors that belong to a specific layer."""
        return [f for f in self._factors.values() if f.layer == layer]

    def coverage_report(self) -> dict[str, int | list[str]]:
        """
        Generate a coverage report showing live vs. stubbed factors.
        Ensures scan output is never silently incomplete.
        """
        live = self.get_live_factors()
        stubbed = self.get_stubbed_factors()
        return {
            "total": len(self._factors),
            "live_count": len(live),
            "stubbed_count": len(stubbed),
            "live_ids": sorted([f.factor_id for f in live]),
            "stubbed_ids": sorted([f.factor_id for f in stubbed]),
        }


# Module-level singleton
factor_registry = FactorRegistry()
