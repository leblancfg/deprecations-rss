"""Cache models for storing HTTP responses."""

from datetime import UTC, datetime

from pydantic import BaseModel, HttpUrl, field_validator


class CacheEntry(BaseModel):
    """Represents a cached HTTP response."""

    url: HttpUrl
    content: bytes
    headers: dict[str, str]
    timestamp: datetime
    etag: str | None = None
    last_modified: str | None = None
    max_age: int | None = None  # in seconds

    @field_validator("timestamp")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the cache entry has expired."""
        if now is None:
            now = datetime.now(UTC)

        # Use max_age if available, otherwise default to 23 hours
        cache_duration = self.max_age if self.max_age is not None else 23 * 3600

        age = (now - self.timestamp).total_seconds()
        return age > cache_duration

    def get_conditional_headers(self) -> dict[str, str]:
        """Get headers for conditional HTTP requests."""
        headers = {}

        if self.etag:
            headers["If-None-Match"] = self.etag

        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified

        return headers
