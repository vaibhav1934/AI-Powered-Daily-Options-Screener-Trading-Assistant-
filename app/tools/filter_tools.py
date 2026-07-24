"""
Tool schemas for filtering the watchlist.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field

class ApplyFilterSchema(BaseModel):
    """Schema for the apply_filter tool."""
    filter_type: str = Field(
        description="The type of filter to apply (e.g., 'price_under', 'exclude_sector', 'list_type')"
    )
    filter_value: str = Field(
        description="The value for the filter (e.g., '50', 'IT', 'LIST_2')"
    )

class RemoveFilterSchema(BaseModel):
    """Schema for the remove_filter tool."""
    filter_type: str = Field(
        description="The type of filter to remove"
    )

class GetActiveFiltersSchema(BaseModel):
    """Schema for the get_active_filters tool."""
    pass

def execute_apply_filter(args: Dict[str, Any], session: Any) -> str:
    """Applies a filter to the current view."""
    return f"Filter {args['filter_type']}={args['filter_value']} applied."

def execute_remove_filter(args: Dict[str, Any], session: Any) -> str:
    """Removes an active filter."""
    return f"Filter {args['filter_type']} removed."

def execute_get_active_filters(args: Dict[str, Any], session: Any) -> str:
    """Retrieves all active filters."""
    return "Active filters retrieved."
