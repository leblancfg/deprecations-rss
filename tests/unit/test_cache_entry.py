"""Tests for CacheEntry model."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.cache.models import CacheEntry


class DescribeCacheEntry:
    """Tests for CacheEntry model."""

    def it_creates_valid_cache_entry(self):
        """Should create a valid cache entry with required fields."""
        url = "https://example.com/api"
        content = b"test content"
        headers = {"Content-Type": "application/json"}
        timestamp = datetime.now(UTC)

        entry = CacheEntry(
            url=url,
            content=content,
            headers=headers,
            timestamp=timestamp,
        )

        assert str(entry.url) == url
        assert entry.content == content
        assert entry.headers == headers
        assert entry.timestamp == timestamp
        assert entry.etag is None
        assert entry.last_modified is None
        assert entry.max_age is None

    def it_stores_etag_and_last_modified(self):
        """Should store ETag and Last-Modified headers when provided."""
        entry = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={
                "ETag": '"33a64df551425fcc55e4d42a148795d9f25f89d4"',
                "Last-Modified": "Wed, 21 Oct 2024 07:28:00 GMT",
            },
            timestamp=datetime.now(UTC),
            etag='"33a64df551425fcc55e4d42a148795d9f25f89d4"',
            last_modified="Wed, 21 Oct 2024 07:28:00 GMT",
        )

        assert entry.etag == '"33a64df551425fcc55e4d42a148795d9f25f89d4"'
        assert entry.last_modified == "Wed, 21 Oct 2024 07:28:00 GMT"

    def it_stores_max_age_from_cache_control(self):
        """Should extract and store max-age from Cache-Control header."""
        entry = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={"Cache-Control": "public, max-age=3600"},
            timestamp=datetime.now(UTC),
            max_age=3600,
        )

        assert entry.max_age == 3600

    def it_determines_if_cache_is_expired(self):
        """Should determine if cache entry is expired based on max_age."""
        now = datetime.now(UTC)

        # Entry with max_age that hasn't expired
        fresh_entry = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=now - timedelta(seconds=1800),
            max_age=3600,
        )
        assert not fresh_entry.is_expired()

        # Entry with max_age that has expired
        expired_entry = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=now - timedelta(seconds=7200),
            max_age=3600,
        )
        assert expired_entry.is_expired()

        # Entry without max_age defaults to 23 hours
        default_fresh = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=now - timedelta(hours=22),
        )
        assert not default_fresh.is_expired()

        default_expired = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=now - timedelta(hours=24),
        )
        assert default_expired.is_expired()

    def it_validates_url_format(self):
        """Should validate URL format."""
        with pytest.raises(ValidationError):
            CacheEntry(
                url="not-a-valid-url",
                content=b"test content",
                headers={},
                timestamp=datetime.now(UTC),
            )

    def it_requires_timestamp_to_be_timezone_aware(self):
        """Should require timestamp to be timezone-aware."""
        with pytest.raises(ValidationError):
            CacheEntry(
                url="https://example.com/api",
                content=b"test content",
                headers={},
                timestamp=datetime.now(),  # Naive datetime
            )

    def it_creates_conditional_request_headers(self):
        """Should create headers for conditional requests."""
        entry = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=datetime.now(UTC),
            etag='"abc123"',
            last_modified="Wed, 21 Oct 2024 07:28:00 GMT",
        )

        conditional_headers = entry.get_conditional_headers()

        assert conditional_headers["If-None-Match"] == '"abc123"'
        assert conditional_headers["If-Modified-Since"] == "Wed, 21 Oct 2024 07:28:00 GMT"

        # Entry without ETag/Last-Modified
        entry_no_headers = CacheEntry(
            url="https://example.com/api",
            content=b"test content",
            headers={},
            timestamp=datetime.now(UTC),
        )

        assert entry_no_headers.get_conditional_headers() == {}
