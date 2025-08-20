"""Tests for cache management."""

import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.cache import CacheEntry, CacheManager


def describe_CacheEntry():
    """Test the CacheEntry data class."""

    def it_creates_with_all_fields():
        """Should create CacheEntry with all fields."""
        data = [{"model": "gpt-4", "deprecation_date": "2024-01-01"}]
        entry = CacheEntry(
            provider="openai",
            data=data,
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=23),
            url="https://example.com",
            etag="abc123",
        )
        assert entry.provider == "openai"
        assert entry.data == data
        assert entry.etag == "abc123"

    def it_checks_expiry():
        """Should correctly check if entry is expired."""
        now = datetime.now()

        # Not expired
        entry = CacheEntry(
            provider="openai",
            data=[],
            timestamp=now,
            expires_at=now + timedelta(hours=1),
        )
        assert entry.is_expired() is False

        # Expired
        entry = CacheEntry(
            provider="openai",
            data=[],
            timestamp=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
        )
        assert entry.is_expired() is True

    def it_converts_to_scraper_result():
        """Should convert to ScraperResult."""
        now = datetime.now()
        data = [{"model": "gpt-4", "deprecation_date": "2024-01-01"}]
        entry = CacheEntry(
            provider="openai",
            data=data,
            timestamp=now,
            expires_at=now + timedelta(hours=23),
        )

        result = entry.to_scraper_result()
        assert result.success is True
        assert result.provider == "openai"
        assert result.data == data
        assert result.from_cache is True
        assert result.cache_timestamp == now


class TestCacheManager:
    """Test the CacheManager class."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        cache_path = tmp_path / "cache"
        cache_path.mkdir()
        return cache_path

    @pytest.fixture
    def cache_manager(self, cache_dir):
        """Create a CacheManager instance."""
        return CacheManager(cache_dir=cache_dir)

    def test_init_creates_directory(self, tmp_path):
        """Should create cache directory if it doesn't exist."""
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()

        manager = CacheManager(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_get_cache_path(self, cache_manager):
        """Should generate correct cache file path."""
        path = cache_manager.get_cache_path("openai")
        assert path.name == "openai.json"
        assert path.parent == cache_manager.cache_dir

    def test_save_cache(self, cache_manager):
        """Should save cache entry to file."""
        data = [{"model": "gpt-4", "deprecation_date": "2024-01-01"}]
        entry = CacheEntry(
            provider="openai",
            data=data,
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=23),
        )

        cache_manager.save(entry)

        cache_file = cache_manager.get_cache_path("openai")
        assert cache_file.exists()

        with open(cache_file) as f:
            saved_data = json.load(f)

        assert saved_data["provider"] == "openai"
        assert saved_data["data"] == data

    def test_load_cache_existing(self, cache_manager):
        """Should load existing cache entry."""
        now = datetime.now()
        data = [{"model": "gpt-4", "deprecation_date": "2024-01-01"}]
        entry = CacheEntry(
            provider="openai",
            data=data,
            timestamp=now,
            expires_at=now + timedelta(hours=23),
        )

        cache_manager.save(entry)
        loaded = cache_manager.load("openai")

        assert loaded is not None
        assert loaded.provider == "openai"
        assert loaded.data == data

    def test_load_cache_missing(self, cache_manager):
        """Should return None for missing cache."""
        loaded = cache_manager.load("nonexistent")
        assert loaded is None

    def test_load_cache_expired(self, cache_manager):
        """Should return None for expired cache."""
        past = datetime.now() - timedelta(hours=25)
        entry = CacheEntry(
            provider="openai",
            data=[],
            timestamp=past,
            expires_at=past + timedelta(hours=23),
        )

        cache_manager.save(entry)
        loaded = cache_manager.load("openai")

        assert loaded is None

    def test_load_cache_corrupted(self, cache_manager):
        """Should handle corrupted cache file gracefully."""
        cache_file = cache_manager.get_cache_path("openai")
        cache_file.write_text("invalid json {[}")

        loaded = cache_manager.load("openai")
        assert loaded is None

    def test_invalidate_cache(self, cache_manager):
        """Should remove cache file."""
        entry = CacheEntry(
            provider="openai",
            data=[],
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=23),
        )

        cache_manager.save(entry)
        cache_file = cache_manager.get_cache_path("openai")
        assert cache_file.exists()

        cache_manager.invalidate("openai")
        assert not cache_file.exists()

    def test_invalidate_nonexistent(self, cache_manager):
        """Should handle invalidating nonexistent cache."""
        cache_manager.invalidate("nonexistent")  # Should not raise

    def test_get_all_cached_providers(self, cache_manager):
        """Should list all cached providers."""
        providers = ["openai", "anthropic", "cohere"]
        now = datetime.now()

        for provider in providers:
            entry = CacheEntry(
                provider=provider,
                data=[],
                timestamp=now,
                expires_at=now + timedelta(hours=23),
            )
            cache_manager.save(entry)

        cached = cache_manager.get_all_cached_providers()
        assert set(cached) == set(providers)

    def test_clear_all_cache(self, cache_manager):
        """Should clear all cache files."""
        providers = ["openai", "anthropic"]
        now = datetime.now()

        for provider in providers:
            entry = CacheEntry(
                provider=provider,
                data=[],
                timestamp=now,
                expires_at=now + timedelta(hours=23),
            )
            cache_manager.save(entry)

        cache_manager.clear_all()

        for provider in providers:
            cache_file = cache_manager.get_cache_path(provider)
            assert not cache_file.exists()

    def test_get_cache_stats(self, cache_manager):
        """Should return cache statistics."""
        now = datetime.now()

        # Add valid cache
        valid_entry = CacheEntry(
            provider="openai",
            data=[{"model": "gpt-4"}],
            timestamp=now,
            expires_at=now + timedelta(hours=23),
        )
        cache_manager.save(valid_entry)

        # Add expired cache
        expired_entry = CacheEntry(
            provider="anthropic",
            data=[],
            timestamp=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
        )
        cache_manager.save(expired_entry)

        stats = cache_manager.get_stats()

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 1
        assert stats["expired_entries"] == 1
        assert "openai" in stats["providers"]

    def test_cache_with_etag(self, cache_manager):
        """Should store and retrieve etag."""
        entry = CacheEntry(
            provider="openai",
            data=[],
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=23),
            etag="W/\"abc123\"",
        )

        cache_manager.save(entry)
        loaded = cache_manager.load("openai")

        assert loaded is not None
        assert loaded.etag == "W/\"abc123\""

    def test_update_cache_if_newer(self, cache_manager):
        """Should only update cache if data is newer."""
        now = datetime.now()

        # Save initial cache
        old_entry = CacheEntry(
            provider="openai",
            data=[{"model": "gpt-3.5"}],
            timestamp=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=22),
        )
        cache_manager.save(old_entry)

        # Try to save older data (should not update)
        older_entry = CacheEntry(
            provider="openai",
            data=[{"model": "gpt-3"}],
            timestamp=now - timedelta(hours=2),
            expires_at=now + timedelta(hours=21),
        )
        updated = cache_manager.save_if_newer(older_entry)
        assert updated is False

        loaded = cache_manager.load("openai")
        assert loaded.data == [{"model": "gpt-3.5"}]

        # Save newer data (should update)
        newer_entry = CacheEntry(
            provider="openai",
            data=[{"model": "gpt-4"}],
            timestamp=now,
            expires_at=now + timedelta(hours=23),
        )
        updated = cache_manager.save_if_newer(newer_entry)
        assert updated is True

        loaded = cache_manager.load("openai")
        assert loaded.data == [{"model": "gpt-4"}]
