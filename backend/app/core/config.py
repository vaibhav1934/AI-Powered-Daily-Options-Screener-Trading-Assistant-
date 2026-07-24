"""
Centralized Configuration Manager
==================================
Two isolated configuration blocks:
  1. AI Auth — driven by VERTEX_AI env flag (single conditional, not fallback chain)
  2. Market Data — Finnhub + Alpha Vantage with caching config

Isolation: AI auth config is NEVER used for DB, storage, or market data.
           DB/storage/market data use standard connection strings and API keys.
"""

from __future__ import annotations

import enum
import logging
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider enum — extensible without rewriting existing logic
# ---------------------------------------------------------------------------
class AIProvider(str, enum.Enum):
    """Supported AI providers. Only ANTHROPIC is implemented in v1."""

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"  # Reserved — not implemented. Adding logic would violate YAGNI.


class AuthMode(str, enum.Enum):
    """Auth mode resolved at startup from VERTEX_AI flag."""

    VERTEX_AI = "vertex_ai"  # ADC-only, routes through Vertex AI
    API_KEY = "api_key"  # Direct API key per provider


# ---------------------------------------------------------------------------
# AI Auth Configuration
# ---------------------------------------------------------------------------
class AIAuthConfig(BaseSettings):
    """
    AI model authentication. Isolated from all other auth.

    VERTEX_AI=true  → ADC exclusively (no API key fallback)
    VERTEX_AI=false → detect provider from which API key is set
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vertex_ai: bool = Field(default=False, description="Use Vertex AI (ADC) auth path")

    # API keys — only checked when vertex_ai=false
    anthropic_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)  # Reserved, unused in v1

    # Vertex AI settings — only checked when vertex_ai=true
    gcp_project_id: Optional[str] = Field(default=None)
    gcp_region: str = Field(default="us-east5")

    # Claude model config
    model_name: str = Field(default="claude-sonnet-4-20250514")
    max_tokens: int = Field(default=4096)

    @model_validator(mode="after")
    def validate_auth_path(self) -> "AIAuthConfig":
        """Single conditional — VERTEX_AI decides the path, no fallback chain."""
        if self.vertex_ai:
            # ADC path: validate that ADC can resolve at startup
            # Actual ADC resolution happens in agents/client.py
            if not self.gcp_project_id:
                raise ValueError(
                    "VERTEX_AI=true requires GCP_PROJECT_ID to be set. "
                    "ADC auth will not fall back to API keys."
                )
            logger.info("AI Auth: Vertex AI (ADC) path selected — project=%s", self.gcp_project_id)
        else:
            # API key path: detect which provider key is present
            if not self.anthropic_api_key and not self.gemini_api_key:
                raise ValueError(
                    "VERTEX_AI=false but no API key found. "
                    "Set ANTHROPIC_API_KEY (v1) or GEMINI_API_KEY (reserved)."
                )
            if self.gemini_api_key and not self.anthropic_api_key:
                raise ValueError(
                    "GEMINI provider is reserved but not implemented in v1. "
                    "Set ANTHROPIC_API_KEY for the working implementation."
                )
            logger.info("AI Auth: API key path selected — provider=ANTHROPIC")
        return self

    @property
    def auth_mode(self) -> AuthMode:
        return AuthMode.VERTEX_AI if self.vertex_ai else AuthMode.API_KEY

    @property
    def resolved_provider(self) -> AIProvider:
        """Detect provider from which key is set. v1: always ANTHROPIC."""
        if self.vertex_ai:
            return AIProvider.ANTHROPIC  # Vertex-hosted Claude
        if self.anthropic_api_key:
            return AIProvider.ANTHROPIC
        # Future: if self.gemini_api_key: return AIProvider.GEMINI
        raise ValueError("No provider could be resolved from available API keys.")


# ---------------------------------------------------------------------------
# Market Data Configuration (separate from AI auth)
# ---------------------------------------------------------------------------
class MarketDataConfig(BaseSettings):
    """
    Market data provider configuration. Completely isolated from AI auth.
    Uses standard API keys — never ADC, never VERTEX_AI flag.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Finnhub — primary quotes/news source (60 calls/min free tier)
    finnhub_api_key: str = Field(default="")

    # Alpha Vantage — technicals (25 calls/day free tier, binding constraint)
    alpha_vantage_api_key: str = Field(default="")

    # Cache TTLs (seconds)
    cache_ttl_finnhub: int = Field(default=300, description="Finnhub cache TTL in seconds")
    cache_ttl_alpha_vantage: int = Field(
        default=86400, description="Alpha Vantage cache TTL (1 day — preserve daily quota)"
    )

    # Rate limits
    finnhub_rate_limit: int = Field(default=60, description="Max calls per minute for Finnhub")
    alpha_vantage_rate_limit: int = Field(
        default=25, description="Max calls per day for Alpha Vantage"
    )

    @field_validator("finnhub_api_key", "alpha_vantage_api_key")
    @classmethod
    def warn_empty_keys(cls, v: str, info: object) -> str:
        if not v:
            logger.warning("Market data API key not set: %s — data fetches will fail", info)
        return v


# ---------------------------------------------------------------------------
# Database Configuration
# ---------------------------------------------------------------------------
class DatabaseConfig(BaseSettings):
    """PostgreSQL via async driver. Standard connection string — never ADC."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/options_screener"
    )

    # Connection pool
    pool_size: int = Field(default=10)
    pool_max_overflow: int = Field(default=20)
    pool_recycle: int = Field(default=3600)


# ---------------------------------------------------------------------------
# Storage Configuration (Screenshots → Supabase Storage)
# ---------------------------------------------------------------------------
class StorageConfig(BaseSettings):
    """Supabase Storage for screenshot uploads. Standard API key — never ADC."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = Field(default="")
    supabase_service_key: str = Field(default="")
    supabase_storage_bucket: str = Field(default="screenshots")


# ---------------------------------------------------------------------------
# App Configuration (timezone, cutoffs, scan schedule)
# ---------------------------------------------------------------------------
class AppConfig(BaseSettings):
    """Application-level settings. All times are server-authoritative CST."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_timezone: str = Field(default="America/Chicago")

    # Pre-market scan schedule (CST, 24h)
    scan_schedule_hour: int = Field(default=6)
    scan_schedule_minute: int = Field(default=30)

    # Cutoff times (CST) — framework rules
    cutoff_standard: str = Field(default="11:00")
    cutoff_friday: str = Field(default="10:30")
    cutoff_fomc: str = Field(default="12:45")

    # API auth (simple key for single-user v1)
    api_secret_key: str = Field(default="change-me-in-production")


# ---------------------------------------------------------------------------
# Root settings aggregator
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """Aggregates all config blocks. Use get_settings() for cached singleton."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ai: AIAuthConfig = Field(default_factory=AIAuthConfig)
    market_data: MarketDataConfig = Field(default_factory=MarketDataConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    app: AppConfig = Field(default_factory=AppConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — config is resolved once at startup."""
    settings = Settings()
    logger.info(
        "Configuration loaded — AI auth=%s, provider=%s, timezone=%s",
        settings.ai.auth_mode.value,
        settings.ai.resolved_provider.value,
        settings.app.app_timezone,
    )
    return settings
