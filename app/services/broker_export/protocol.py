"""
Broker Export Protocol (Interface Only)
========================================
FR-21/22: Fidelity export cross-reference.
No concrete implementation until CSV format is confirmed.
Do not guess at column mappings.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class PositionRecord(BaseModel):
    """A single position from a broker export."""

    ticker: str
    quantity: float
    average_cost: float
    current_value: float
    gain_loss: float
    gain_loss_percent: float
    sector: str = ""
    account: str = ""


class ConcentrationReport(BaseModel):
    """Sector/position concentration analysis."""

    total_value: float
    sector_breakdown: dict[str, float]  # sector → percentage
    top_positions: list[dict[str, float]]  # [{ticker, percentage}]
    concentration_warnings: list[str]  # e.g., "IT concentration at 48%"


class TrimCandidate(BaseModel):
    """A position suggested for trimming or tax-loss harvesting."""

    ticker: str
    reason: str  # "concentration", "tax_loss_harvest", "duplicate_exposure"
    current_weight: float
    suggested_action: str


class BrokerExportParser(Protocol):
    """
    Interface for broker export ingestion.
    No concrete implementation until Fidelity CSV format is confirmed.
    Do not guess at column mappings.
    """

    def parse(self, file_content: bytes) -> list[PositionRecord]:
        """Parse raw file content into structured position records."""
        ...

    def detect_concentration(
        self, positions: list[PositionRecord]
    ) -> ConcentrationReport:
        """Analyze positions for sector/position concentration."""
        ...

    def suggest_trim_candidates(
        self,
        positions: list[PositionRecord],
        scan_tickers: list[str],
    ) -> list[TrimCandidate]:
        """
        Cross-reference positions against scan output.
        Identify duplicates, concentration issues, and TLH candidates.
        """
        ...
