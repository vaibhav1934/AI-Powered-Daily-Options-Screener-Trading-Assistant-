"""
Central Router
================
Aggregates all API route modules into a single router.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from app.core.security import verify_api_key

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.debug import router as debug_router
from app.api.portfolio import router as portfolio_router
from app.api.scans import router as scans_router
from app.api.screenshots import router as screenshots_router
from app.api.stockglass import router as stockglass_router
from app.api.watchlist import router as watchlist_router

api_router = APIRouter(prefix="/v1")
internal_router = APIRouter(dependencies=[Depends(verify_api_key)])

internal_router.include_router(scans_router)
internal_router.include_router(debug_router)
internal_router.include_router(screenshots_router)
internal_router.include_router(watchlist_router)
internal_router.include_router(chat_router)
internal_router.include_router(admin_router)
internal_router.include_router(portfolio_router)

api_router.include_router(internal_router)
api_router.include_router(stockglass_router)
