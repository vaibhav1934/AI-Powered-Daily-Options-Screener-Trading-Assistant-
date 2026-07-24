"""
Tool schemas for retrieving watchlist views and risk buckets.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field

class GetWatchlistSchema(BaseModel):
    """Schema for the get_watchlist tool."""
    list_type: str = Field(
        None, description="LIST_1 (daily) or LIST_2 (monthly)"
    )
    risk_bucket: str = Field(
        None, description="LOW, MODERATE, or HIGH_RISK_HALO"
    )

class GetRiskBucketsSchema(BaseModel):
    """Schema for the get_risk_buckets tool."""
    scan_date: str = Field(
        description="The date of the scan in YYYY-MM-DD format."
    )

def execute_get_watchlist(args: Dict[str, Any], session: Any) -> str:
    """Retrieves the watchlist."""
    return "Watchlist retrieved."

def execute_get_risk_buckets(args: Dict[str, Any], session: Any) -> str:
    """Retrieves risk bucket distribution."""
    return "Risk buckets retrieved."
