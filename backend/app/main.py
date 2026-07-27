"""
FastAPI Application Factory
==============================
Main entry point. Registers middleware, routes, exception handlers,
and lifespan events (startup/shutdown).
"""

from __future__ import annotations

import logging
import os
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
from app.db.session import engine
from app.db.models import Base

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

    # Ensure database tables exist (e.g. users table for JWT auth)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database schema: %s", str(e))

    logger.info("Application ready")

    yield

    # Shutdown
    logger.info("Shutting down Options Screener")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="StockGlass AI — Institutional Options & Stock Screener",
        description=(
            "Automated 50-factor, 10-layer scanning framework with "
            "TradingView screenshot confirmation gate, risk bucketing, "
            "and GenAI chat panel."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    cors_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
    ]
    if os.getenv("CORS_ORIGINS"):
        cors_origins.extend([o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex="https://.*\\.vercel\\.app|https://.*\\.hf\\.space",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_request_flow(request: Request, call_next):
        import time
        start_time = time.time()
        query_str = f"?{request.url.query}" if request.url.query else ""
        logger.info(
            "[FLOW: Backend Request] ──> Incoming %s %s%s",
            request.method, request.url.path, query_str
        )
        try:
            response = await call_next(request)
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info(
                "[FLOW: Backend Response] <── Completed %s %s [%d] in %s ms",
                request.method, request.url.path, response.status_code, duration
            )
            return response
        except Exception as exc:
            duration = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "[FLOW: Backend Error] <── FAILED %s %s in %s ms: %s",
                request.method, request.url.path, duration, str(exc)
            )
            raise

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
    import sqlalchemy.exc
    import socket

    @app.exception_handler(sqlalchemy.exc.OperationalError)
    @app.exception_handler(sqlalchemy.exc.InterfaceError)
    @app.exception_handler(socket.gaierror)
    async def db_connection_error_handler(request: Request, exc: Exception) -> JSONResponse:
        import uuid
        trace_id = str(uuid.uuid4())
        logger.error(
            "Database connectivity error",
            error=str(exc),
            trace_id=trace_id,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database connection failed (Supabase instance may be paused or offline). Please check your DATABASE_URL in .env or resume the project in the Supabase dashboard.",
                    "trace_id": trace_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        import uuid
        trace_id = str(uuid.uuid4())
        err_str = str(exc).lower()
        if any(w in err_str for w in ("gaierror", "getaddrinfo", "operationalerror", "connection refused", "cannotconnectnowerror", "connection timed out", "could not translate host name")):
            return await db_connection_error_handler(request, exc)
            
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

    # Root endpoint for container health checks and status
    @app.get("/")
    @app.get("/v1")
    async def root_status():
        return {
            "name": "StockGlass AI Trading Assistant Backend",
            "status": "running",
            "version": "1.0.0",
            "docs_url": "/docs",
            "health_url": "/v1/health",
        }

    # Suppress harmless browser favicon requests
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return JSONResponse(status_code=204, content="")

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
