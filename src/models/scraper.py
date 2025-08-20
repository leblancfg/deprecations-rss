"""Data models for scraper configuration and caching."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ScraperConfig(BaseModel):
    """Configuration for base scraper."""

    rate_limit_delay: float = Field(default=1.0, description="Delay between requests in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    retry_delays: list[float] = Field(
        default=[1, 2, 4],
        description="Delays for each retry attempt in seconds"
    )
    cache_ttl_hours: int = Field(default=23, description="Cache TTL in hours for daily runs")
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")
    cache_dir: Path = Field(default=Path(".cache"), description="Directory for cache files")
    user_agent: str = Field(
        default="deprecations-rss/0.1.0 (+https://github.com/leblancfg/deprecations-rss)",
        description="User agent string for HTTP requests"
    )

    model_config = {"arbitrary_types_allowed": True}


class CacheEntry(BaseModel):
    """Cache entry with timestamp for TTL management."""

    data: dict[str, Any] = Field(description="Cached data")
    timestamp: datetime = Field(description="Cache entry timestamp")

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create cache entry with current UTC timestamp."""
        return cls(data=data, timestamp=datetime.now(UTC))

    def is_expired(self, ttl_hours: int) -> bool:
        """Check if cache entry is expired based on TTL."""
        now = datetime.now(UTC)
        age_hours = (now - self.timestamp).total_seconds() / 3600
        return age_hours > ttl_hours

