"""
Layer Base Protocol
====================
Each scanning layer implements the LayerProtocol.
Layers are executed sequentially (L1→L10) by the engine.
Each layer can pass, flag, downgrade, or veto tickers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.framework.factors.base import BaseFactor, FactorResult, ScanContext


class BaseLayer(ABC):
    """
    Abstract base class for all scanning layers.
    Each layer operates on a ScanContext and applies its factors.
    """

    layer_number: int
    name: str
    description: str

    @abstractmethod
    def get_factors(self) -> list[BaseFactor]:
        """Return the factors that belong to this layer."""
        ...

    def process(self, ctx: ScanContext) -> ScanContext:
        """
        Process a ticker through this layer.
        Evaluates all layer-specific factors and updates the ScanContext.
        Layers run sequentially — if a previous layer vetoed, this layer
        still runs but records results for audit/explainability.
        """
        factors = self.get_factors()

        for factor in factors:
            result: FactorResult = factor.evaluate(ctx)

            # Record result for audit trail
            ctx.factor_results.append(result)

            if result.triggered:
                ctx.triggered_factors.append(result.factor_id)

            # Apply veto if the factor vetoes
            if result.vetoed and not ctx.is_vetoed:
                ctx.is_vetoed = True
                ctx.veto_rule = result.factor_id
                ctx.veto_reason = result.detail

        return ctx
