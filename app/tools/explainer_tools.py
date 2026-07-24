"""
Tool schemas for explaining tickers and vetoes.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field

class ExplainTickerSchema(BaseModel):
    """Schema for the explain_ticker tool."""
    ticker: str = Field(
        description="The stock ticker to explain (e.g., 'AAPL')"
    )
    scan_date: str = Field(
        description="The date of the scan in YYYY-MM-DD format."
    )

class ExplainVetoSchema(BaseModel):
    """Schema for the explain_veto tool."""
    ticker: str = Field(
        description="The stock ticker to explain the veto for"
    )
    scan_date: str = Field(
        description="The date of the scan in YYYY-MM-DD format."
    )

def execute_explain_ticker(args: Dict[str, Any], session: Any) -> str:
    """Explains why a ticker was ranked or vetoed based on factor logs."""
    return f"Explanation for {args['ticker']} retrieved."

def execute_explain_veto(args: Dict[str, Any], session: Any) -> str:
    """Provides detailed explanation for a specific veto rule."""
    return f"Veto explanation for {args['ticker']} retrieved."
