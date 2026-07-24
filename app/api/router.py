"""
Central Router
================
Aggregates all API route modules into a single router.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.scans import router as scans_router
from app.api.screenshots import router as screenshots_router
from app.api.watchlist import router as watchlist_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(scans_router)
api_router.include_router(screenshots_router)
api_router.include_router(watchlist_router)
api_router.include_router(chat_router)
api_router.include_router(admin_router)
