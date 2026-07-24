"""
FastAPI Application Factory
==============================
Main entry point. Registers middleware, routes, exception handlers,
and lifespan events (startup/shutdown).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.rate_limiter import init_rate_limiters

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    # Startup
    settings = get_settings()
    logger.info(
        "Starting Options Screener",
        ai_auth_mode=settings.ai.auth_mode.value,
        timezone=settings.app.app_timezone,
    )

    # Initialize rate limiters
    init_rate_limiters()

    logger.info("Application ready")

    yield

    # Shutdown
    logger.info("Shutting down Options Screener")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AI-Powered Daily Options Screener",
        description=(
            "Automated 50-factor, 10-layer scanning framework with "
            "TradingView screenshot confirmation gate, risk bucketing, "
            "and GenAI chat panel."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized exception handler
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.error(
            "Application error",
            error_code=exc.error_code,
            message=exc.message,
            trace_id=exc.trace_id,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        import uuid
        trace_id = str(uuid.uuid4())
        logger.error(
            "Unhandled exception",
            error=str(exc),
            trace_id=trace_id,
            path=str(request.url),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "trace_id": trace_id,
                }
            },
        )

    # Register routes
    app.include_router(api_router)

    # Health check
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "ai_auth_mode": settings.ai.auth_mode.value,
            "timezone": settings.app.app_timezone,
        }

    return app


# Application instance
app = create_app()
