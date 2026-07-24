"""
Centralized Exception Classes
==============================
Structured JSON error responses with trace IDs and context.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional


class AppError(Exception):
    """Base application error. All custom exceptions inherit from this."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        detail: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.message = message
        self.detail = detail or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        super().__init__(self.message)

    def to_response(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "detail": self.detail,
                "trace_id": self.trace_id,
            }
        }


# --- Auth Errors ---


class AuthenticationError(AppError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class ADCResolutionError(AppError):
    """Raised when VERTEX_AI=true but ADC cannot resolve credentials."""

    status_code = 500
    error_code = "ADC_RESOLUTION_FAILED"

    def __init__(self, message: str = "Google ADC resolution failed. Check service account setup.") -> None:
        super().__init__(message)


class ProviderNotImplementedError(AppError):
    """Raised when a reserved but unimplemented provider is requested."""

    status_code = 501
    error_code = "PROVIDER_NOT_IMPLEMENTED"


# --- Scan Errors ---


class ScanError(AppError):
    status_code = 500
    error_code = "SCAN_ERROR"


class ScanNotFoundError(AppError):
    status_code = 404
    error_code = "SCAN_NOT_FOUND"


# --- Time Gate Errors ---


class CutoffExceededError(AppError):
    """Raised when an action is attempted past the entry cutoff time."""

    status_code = 403
    error_code = "CUTOFF_EXCEEDED"

    def __init__(self, cutoff_time: str, current_time: str) -> None:
        super().__init__(
            message=f"Entry cutoff exceeded. Cutoff: {cutoff_time} CST, current: {current_time} CST.",
            detail={"cutoff_time": cutoff_time, "current_time": current_time},
        )


# --- Screenshot Errors ---


class ScreenshotNotFoundError(AppError):
    status_code = 404
    error_code = "SCREENSHOT_NOT_FOUND"


class ScreenshotRequiredError(AppError):
    """Raised when execution details are requested for an unconfirmed ticker."""

    status_code = 403
    error_code = "SCREENSHOT_REQUIRED"

    def __init__(self, ticker: str) -> None:
        super().__init__(
            message=f"Screenshot confirmation required for {ticker} before execution details are visible.",
            detail={"ticker": ticker},
        )


# --- State Transition Errors ---


class InvalidStateTransitionError(AppError):
    status_code = 409
    error_code = "INVALID_STATE_TRANSITION"

    def __init__(self, ticker: str, current_status: str, target_status: str) -> None:
        super().__init__(
            message=f"Cannot transition {ticker} from {current_status} to {target_status}.",
            detail={
                "ticker": ticker,
                "current_status": current_status,
                "target_status": target_status,
            },
        )


# --- Market Data Errors ---


class MarketDataError(AppError):
    status_code = 502
    error_code = "MARKET_DATA_ERROR"


class RateLimitExceededError(AppError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, provider: str, limit: int) -> None:
        super().__init__(
            message=f"Rate limit exceeded for {provider}. Limit: {limit}.",
            detail={"provider": provider, "limit": limit},
        )


# --- Factor Errors ---


class FactorNotConfiguredError(AppError):
    """Not a runtime error — informational. Factor F1–F39 is stubbed."""

    status_code = 200  # Not an error per se
    error_code = "FACTOR_NOT_CONFIGURED"

    def __init__(self, factor_id: str) -> None:
        super().__init__(
            message=f"Factor {factor_id} is not yet configured. Supply trigger conditions to activate.",
            detail={"factor_id": factor_id, "status": "unconfigured"},
        )
