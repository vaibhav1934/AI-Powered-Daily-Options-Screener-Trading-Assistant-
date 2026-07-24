"""
Fidelity Broker Export Stub
==============================
Concrete implementation placeholder.
Raises NotImplementedError until CSV format is confirmed.
"""

from __future__ import annotations

from app.services.broker_export.protocol import (
    ConcentrationReport,
    PositionRecord,
    TrimCandidate,
)


class FidelityExportParser:
    """
    Stub implementation for Fidelity CSV export parsing.
    NOT IMPLEMENTED — Fidelity CSV format not yet confirmed.
    Do not guess at column mappings.
    """

    def parse(self, file_content: bytes) -> list[PositionRecord]:
        raise NotImplementedError(
            "Fidelity CSV format not yet confirmed. "
            "Supply a sample CSV export to implement column mappings."
        )

    def detect_concentration(
        self, positions: list[PositionRecord]
    ) -> ConcentrationReport:
        raise NotImplementedError(
            "Cannot detect concentration without parsed positions. "
            "Implement parse() first."
        )

    def suggest_trim_candidates(
        self,
        positions: list[PositionRecord],
        scan_tickers: list[str],
    ) -> list[TrimCandidate]:
        raise NotImplementedError(
            "Cannot suggest trims without parsed positions. "
            "Implement parse() first."
        )
