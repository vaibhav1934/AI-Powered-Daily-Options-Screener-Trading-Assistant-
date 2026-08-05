"""
FastAPI Application Factory
==============================
Main entry point. Registers middleware, routes, exception handlers,
and lifespan events (startup/shutdown).
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncio
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.api.router import api_router, root_api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.rate_limiter import init_rate_limiters, rate_limiter_registry
from app.services.scan_service import trigger_scan
from app.db.models import User
from app.db.session import engine
from app.db.models import Base
from app.db.session import async_session_factory
from app.services import portfolio_management_service

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


LOCAL_ORIGIN_PATTERN = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$")


def _is_allowed_dev_origin(origin: str) -> bool:
    return bool(LOCAL_ORIGIN_PATTERN.match(origin or ""))


def _apply_dev_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Ensure localhost origins receive CORS headers even on handled exceptions."""
    origin = request.headers.get("origin", "")
    if origin and _is_allowed_dev_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        vary = response.headers.get("Vary", "")
        if "Origin" not in vary:
            response.headers["Vary"] = f"{vary}, Origin".strip(", ")
    return response


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

    scheduler: AsyncIOScheduler | None = None

    # Ensure database tables exist (e.g. users table for JWT auth)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Guard against migration drift: ensure positions.user_id exists before
            # any portfolio query path that filters by user ownership.
            await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'positions'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'positions' AND column_name = 'user_id'
                ) THEN
                    ALTER TABLE public.positions ADD COLUMN user_id integer NULL;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'positions' AND column_name = 'user_id'
                ) THEN
                    CREATE INDEX IF NOT EXISTS ix_positions_user_id ON public.positions (user_id);
                END IF;
            END
            $$;
            """))
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database schema: %s", str(e))

    async def _run_continuous_scanner() -> None:
        """Run scanning continuously while respecting API rate limits."""
        logger.info(
            "Continuous scanner started",
            batch_size=settings.app.scan_batch_size,
            interval=settings.app.scan_interval_seconds,
        )
        while True:
            try:
                async with async_session_factory() as session:
                    res = await trigger_scan(session, batch_size=settings.app.scan_batch_size)
                    
                status = res.get("status")
                tickers_scanned = res.get("tickers_scanned", 0)
                
                logger.info(f"Continuous scanner batch completed. Status: {status}, Scanned: {tickers_scanned}")
                
                if status == "ALL_SCANNED":
                    # Rest for a while once the daily universe is fully scanned
                    await asyncio.sleep(3600)
                    continue
                    
                if status == "SCAN_ALREADY_RUNNING":
                    await asyncio.sleep(30)
                    continue

                # Check rate limits to compute dynamic backoff
                limit_status = rate_limiter_registry.status()
                finnhub_status = limit_status.get("finnhub", {})
                retry_after = finnhub_status.get("retry_after_seconds", 0)
                
                # Sleep enough to guarantee we stay within limits, plus interval buffer
                sleep_time = max(settings.app.scan_interval_seconds, retry_after)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error("Continuous scanner encountered an error", error=str(e))
                await asyncio.sleep(settings.app.scan_interval_seconds)

    async def _run_portfolio_maintenance(cadence: str) -> None:
        """Run scheduled portfolio scoring/optimization for all active users."""
        try:
            async with async_session_factory() as session:
                users = (
                    await session.execute(select(User.id).where(User.is_active == True))
                ).all()

                processed = 0
                failed = 0
                for row in users:
                    user_id = int(row.id)
                    try:
                        if cadence == "weekly":
                            await portfolio_management_service.get_portfolio_optimization(
                                session=session,
                                user_id=user_id,
                                cadence="weekly",
                            )
                        else:
                            await portfolio_management_service.get_portfolio_score(
                                session=session,
                                user_id=user_id,
                            )
                        processed += 1
                    except Exception as user_exc:
                        failed += 1
                        logger.error(
                            "Scheduled portfolio maintenance failed for user",
                            cadence=cadence,
                            user_id=user_id,
                            error=str(user_exc),
                        )

                logger.info(
                    "Scheduled portfolio maintenance completed",
                    cadence=cadence,
                    processed=processed,
                    failed=failed,
                )
        except Exception as exc:
            logger.error(
                "Scheduled portfolio maintenance job failed",
                cadence=cadence,
                error=str(exc),
            )

    if settings.app.portfolio_scheduler_enabled:
        scheduler = AsyncIOScheduler(timezone=settings.app.app_timezone)
        scheduler.add_job(
            _run_portfolio_maintenance,
            CronTrigger(
                hour=settings.app.portfolio_daily_score_hour,
                minute=settings.app.portfolio_daily_score_minute,
                timezone=settings.app.app_timezone,
            ),
            args=["daily"],
            id="portfolio_daily_score",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            _run_portfolio_maintenance,
            CronTrigger(
                day_of_week=settings.app.portfolio_weekly_optimize_day_of_week,
                hour=settings.app.portfolio_weekly_optimize_hour,
                minute=settings.app.portfolio_weekly_optimize_minute,
                timezone=settings.app.app_timezone,
            ),
            args=["weekly"],
            id="portfolio_weekly_optimize",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        logger.info(
            "Portfolio scheduler started",
            daily_hour=settings.app.portfolio_daily_score_hour,
            daily_minute=settings.app.portfolio_daily_score_minute,
            weekly_day=settings.app.portfolio_weekly_optimize_day_of_week,
            weekly_hour=settings.app.portfolio_weekly_optimize_hour,
            weekly_minute=settings.app.portfolio_weekly_optimize_minute,
        )

    logger.info("Application ready")

    continuous_scanner_task = None
    if settings.app.scan_continuous_enabled:
        continuous_scanner_task = asyncio.create_task(_run_continuous_scanner())

    yield

    # Shutdown
    if continuous_scanner_task:
        continuous_scanner_task.cancel()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("Portfolio scheduler stopped")
    await engine.dispose()
    logger.info("Database engine disposed")
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
        allow_origin_regex=(
            r"https://.*\\.vercel\\.app"
            r"|https://.*\\.hf\\.space"
            r"|http://localhost(:[0-9]+)?"
            r"|http://127\\.0\\.0\\.1(:[0-9]+)?"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_request_flow(request: Request, call_next):
        import time
        start_time = time.time()
        query_str = f"?{request.url.query}" if request.url.query else ""
        origin = request.headers.get("origin", "")
        logger.info(
            "[FLOW: Backend Request] ──> Incoming %s %s%s",
            request.method, request.url.path, query_str
        )
        try:
            response = await call_next(request)
            # Defensive CORS hardening for local development: ensure error/edge
            # responses still include ACAO when Origin is localhost/127.0.0.1.
            if origin and _is_allowed_dev_origin(origin):
                if "access-control-allow-origin" not in response.headers:
                    response.headers["Access-Control-Allow-Origin"] = origin
                if "access-control-allow-credentials" not in response.headers:
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                vary = response.headers.get("Vary", "")
                if "Origin" not in vary:
                    response.headers["Vary"] = f"{vary}, Origin".strip(", ")
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
        return _apply_dev_cors_headers(request, JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response(),
        ))
    import sqlalchemy.exc
    import socket

    @app.exception_handler(sqlalchemy.exc.OperationalError)
    @app.exception_handler(sqlalchemy.exc.InterfaceError)
    @app.exception_handler(sqlalchemy.exc.TimeoutError)
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
        return _apply_dev_cors_headers(request, JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database connection failed (Supabase instance may be paused or offline). Please check your DATABASE_URL in .env or resume the project in the Supabase dashboard.",
                    "trace_id": trace_id,
                }
            },
        ))

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        import uuid
        trace_id = str(uuid.uuid4())
        err_str = str(exc).lower()
        if any(w in err_str for w in (
            "gaierror",
            "getaddrinfo",
            "operationalerror",
            "interfaceerror",
            "timeouterror",
            "connection refused",
            "cannotconnectnowerror",
            "connection timed out",
            "could not translate host name",
            "too many clients",
            "max clients reached",
            "emaxconnsession",
            "max_client_conn",
            "queuepool limit",
        )):
            return await db_connection_error_handler(request, exc)
            
        logger.error(
            "Unhandled exception",
            error=str(exc),
            trace_id=trace_id,
            path=str(request.url),
            exc_info=True,
        )
        return _apply_dev_cors_headers(request, JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "trace_id": trace_id,
                }
            },
        ))

    # Register versioned API routes
    app.include_router(api_router)
    app.include_router(root_api_router)

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
