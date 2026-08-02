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
import os
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

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

    # Model configuration
    model_name: Optional[str] = Field(default=None, description="Override the default model name from environment")
    max_tokens: int = Field(default=4096)

    @model_validator(mode="after")
    def validate_auth_path(self) -> "AIAuthConfig":
        """Single conditional — VERTEX_AI decides the path, no fallback chain."""
        if self.vertex_ai:
            # ADC path: validate that ADC can resolve at startup
            if not self.gcp_project_id:
                raise ValueError(
                    "VERTEX_AI=true requires GCP_PROJECT_ID to be set. "
                    "ADC auth will not fall back to API keys."
                )
            logger.info("AI Auth: Vertex AI (ADC) path selected — project=%s", self.gcp_project_id)
        else:
            # API key path: detect which provider key is present
            if not self.anthropic_api_key and not self.gemini_api_key:
                logger.warning("AI Auth: VERTEX_AI=false but no API key found. Anthropic calls will fail.")
            elif self.anthropic_api_key == "your_anthropic_api_key_here":
                logger.warning("AI Auth: ANTHROPIC_API_KEY is still set to placeholder. Anthropic calls will fail.")
            elif self.gemini_api_key and not self.anthropic_api_key:
                logger.info("AI Auth: API key path selected — provider=GEMINI")
            else:
                logger.info("AI Auth: API key path selected — provider=ANTHROPIC")
        return self

    @property
    def auth_mode(self) -> AuthMode:
        return AuthMode.VERTEX_AI if self.vertex_ai else AuthMode.API_KEY

    @property
    def resolved_provider(self) -> AIProvider:
        """Detect provider from which key is set."""
        if self.vertex_ai:
            return AIProvider.GEMINI  # Default to Gemini on Vertex AI as requested
        if self.gemini_api_key:
            return AIProvider.GEMINI
        if self.anthropic_api_key and self.anthropic_api_key != "your_anthropic_api_key_here":
            return AIProvider.ANTHROPIC
        # Fallback default so migrations/config runs without breaking during initial local setup
        return AIProvider.ANTHROPIC

    @property
    def resolved_model_name(self) -> str:
        """Returns the model name from env if set, otherwise smart defaults."""
        if self.model_name:
            return self.model_name
        
        # Smart defaults based on auth mode and provider
        if self.resolved_provider == AIProvider.GEMINI:
            if self.vertex_ai:
                return "gemini-3.5-flash-lite"
            return "gemini-3.5-flash-lite"
        elif self.resolved_provider == AIProvider.ANTHROPIC:
            return "claude-3-5-sonnet-20241022"      # Anthropic direct format
            
        return "claude-3-5-sonnet-20241022"


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

    # FRED — macro/rates series (free official API)
    fred_api_key: str = Field(default="")

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
        default=os.getenv("DATABASE_URL", "").strip() or "sqlite+aiosqlite:///./stockglass.db"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def sanitize_db_url(cls, v: str) -> str:
        """Strip whitespace and accidental trailing newlines from database URL secret."""
        return v.strip() if isinstance(v, str) and v.strip() else "sqlite+aiosqlite:///./stockglass.db"

    @model_validator(mode="after")
    def validate_supabase_pooler_mode(self) -> "DatabaseConfig":
        url = (self.database_url or "").strip().lower()
        if url.startswith("sqlite"):
            return self

        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port

        # Supabase session mode (5432) often hits EMAXCONNSESSION on API workloads.
        # Force transaction mode configuration early with a clear actionable message.
        if "pooler.supabase.com" in host and port == 5432:
            raise ValueError(
                "DATABASE_URL points to Supabase session pooler (port 5432). "
                "Use transaction pooler port 6543 with sslmode=require to avoid EMAXCONNSESSION."
            )

        return self

    # Connection pool
    # Moderate defaults to reduce local/API burst starvation while still being tunable via env.
    pool_size: int = Field(default=8)
    pool_max_overflow: int = Field(default=8)
    pool_recycle: int = Field(default=3600)
    pool_timeout: int = Field(default=45)


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

    # Portfolio maintenance schedule (CST)
    portfolio_scheduler_enabled: bool = Field(default=True)
    portfolio_daily_score_hour: int = Field(default=18)
    portfolio_daily_score_minute: int = Field(default=5)
    portfolio_weekly_optimize_day_of_week: str = Field(default="sun")
    portfolio_weekly_optimize_hour: int = Field(default=18)
    portfolio_weekly_optimize_minute: int = Field(default=15)

    # Default portfolio score weights (must sum to 1.0)
    portfolio_weight_concentration: float = Field(default=0.15)
    portfolio_weight_risk_adjusted_return: float = Field(default=0.15)
    portfolio_weight_diversification: float = Field(default=0.12)
    portfolio_weight_drawdown: float = Field(default=0.12)
    portfolio_weight_greeks: float = Field(default=0.12)
    portfolio_weight_liquidity: float = Field(default=0.10)
    portfolio_weight_conviction: float = Field(default=0.12)
    portfolio_weight_tax_efficiency: float = Field(default=0.12)

    # Cutoff times (CST) — framework rules
    cutoff_standard: str = Field(default="11:00")
    cutoff_friday: str = Field(default="10:30")
    cutoff_fomc: str = Field(default="12:45")

    # API auth (simple key for single-user v1)
    api_secret_key: str = Field(default="change-me-in-production")
    public_registration_enabled: bool = Field(default=True)

    @model_validator(mode="after")
    def validate_portfolio_settings(self) -> "AppConfig":
        for field_name in (
            "portfolio_daily_score_hour",
            "portfolio_weekly_optimize_hour",
        ):
            value = int(getattr(self, field_name))
            if value < 0 or value > 23:
                raise ValueError(f"{field_name} must be in range 0..23")

        for field_name in (
            "portfolio_daily_score_minute",
            "portfolio_weekly_optimize_minute",
        ):
            value = int(getattr(self, field_name))
            if value < 0 or value > 59:
                raise ValueError(f"{field_name} must be in range 0..59")

        allowed_days = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        if self.portfolio_weekly_optimize_day_of_week.lower() not in allowed_days:
            raise ValueError("portfolio_weekly_optimize_day_of_week must be one of mon,tue,wed,thu,fri,sat,sun")

        weights = [
            float(self.portfolio_weight_concentration),
            float(self.portfolio_weight_risk_adjusted_return),
            float(self.portfolio_weight_diversification),
            float(self.portfolio_weight_drawdown),
            float(self.portfolio_weight_greeks),
            float(self.portfolio_weight_liquidity),
            float(self.portfolio_weight_conviction),
            float(self.portfolio_weight_tax_efficiency),
        ]

        if any(w < 0 for w in weights):
            raise ValueError("Portfolio weights cannot be negative")

        total = sum(weights)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Portfolio weights must sum to 1.0, got {total:.6f}")

        secret = (self.api_secret_key or "").strip()
        if not secret or secret == "change-me-in-production":
            logger.warning("JWT secret key is using a default/placeholder value. Set APP_API_SECRET_KEY to a random >=32-byte secret.")
        elif len(secret.encode("utf-8")) < 32:
            logger.warning("JWT secret key is shorter than 32 bytes; use a longer secret to avoid weak HMAC key warnings.")

        return self


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
