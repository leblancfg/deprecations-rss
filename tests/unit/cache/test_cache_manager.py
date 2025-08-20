"""Tests for cache manager with fallback support."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cache.manager import CacheEntry, CacheManager
from src.cache.storage.filesystem import FileSystemStorage


@pytest.fixture
async def mock_storage():
    """Create a mock storage backend."""
    storage = AsyncMock(spec=FileSystemStorage)
    storage.generate_key = MagicMock(
        side_effect=lambda p, i, d=None: f"{p}:{i}:{d.strftime('%Y-%m-%d')}" if d else f"{p}:{i}"
    )
    return storage


@pytest.fixture
async def cache_manager(mock_storage):
    """Create a CacheManager instance with mock storage."""
    return CacheManager(storage=mock_storage)


class DescribeCacheEntry:
    """Test the CacheEntry model."""

    def it_creates_entry_with_defaults(self):
        entry = CacheEntry(key="test", data={"value": "test"}, created_at=datetime.now(UTC))
        assert entry.source == "scraper"
        assert entry.expires_at is None
        assert not entry.is_expired()

    def it_checks_expiration_correctly(self):
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)

        expired_entry = CacheEntry(
            key="test", data={}, created_at=datetime.now(UTC), expires_at=past
        )
        assert expired_entry.is_expired()

        valid_entry = CacheEntry(
            key="test", data={}, created_at=datetime.now(UTC), expires_at=future
        )
        assert not valid_entry.is_expired()


class DescribeCacheManager:
    """Test the CacheManager class."""

    @pytest.mark.asyncio
    async def it_gets_data_with_fallback(self, cache_manager, mock_storage):
        cached_data = {
            "data": {"test": "value"},
            "created_at": datetime.now(UTC).isoformat(),
            "ttl": 3600,
        }
        mock_storage.get.return_value = json.dumps(cached_data).encode()

        result = await cache_manager.get_with_fallback("test:key")
        assert result == {"test": "value"}
        mock_storage.get.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def it_fetches_fresh_data_when_cache_miss(self, cache_manager, mock_storage):
        mock_storage.get.return_value = None
        mock_storage.set.return_value = True

        async def fetch_func():
            return {"fresh": "data"}

        result = await cache_manager.get_with_fallback("test:key", fetch_func=fetch_func, ttl=3600)

        assert result == {"fresh": "data"}
        mock_storage.set.assert_called_once()

    @pytest.mark.asyncio
    async def it_uses_stale_cache_on_fetch_error(self, cache_manager, mock_storage):
        stale_data = {
            "data": {"stale": "value"},
            "created_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "ttl": 3600,
        }
        mock_storage.get.return_value = json.dumps(stale_data).encode()

        async def failing_fetch():
            raise Exception("Fetch failed")

        result = await cache_manager.get_with_fallback(
            "test:key", fetch_func=failing_fetch, ttl=3600, use_stale_on_error=True
        )

        assert result == {"stale": "value"}

    @pytest.mark.asyncio
    async def it_saves_deprecation_data(self, cache_manager, mock_storage):
        mock_storage.set.return_value = True

        data = {"models": ["gpt-3", "davinci"]}
        date = datetime(2024, 1, 15, tzinfo=UTC)

        result = await cache_manager.save_deprecation_data("openai", data, date)

        assert result is True
        mock_storage.set.assert_called_once()

        call_args = mock_storage.set.call_args
        saved_key = call_args[0][0]
        saved_data = json.loads(call_args[0][1].decode())

        assert saved_key == "deprecations:openai:2024-01-15"
        assert saved_data["provider"] == "openai"
        assert saved_data["data"] == data

    @pytest.mark.asyncio
    async def it_gets_deprecation_data_with_fallback(self, cache_manager, mock_storage):
        cached_data = {
            "data": {"models": ["old-model"]},
            "provider": "anthropic",
            "date": "2024-01-15T00:00:00",
        }

        mock_storage.get.side_effect = [
            None,  # Today - no data
            None,  # Yesterday - no data
            json.dumps(cached_data).encode(),  # 2 days ago - found
        ]

        date = datetime(2024, 1, 17, tzinfo=UTC)
        result = await cache_manager.get_deprecation_data("anthropic", date, max_age_days=3)

        assert result == {"models": ["old-model"]}
        assert mock_storage.get.call_count == 3

    @pytest.mark.asyncio
    async def it_gets_all_providers_data(self, cache_manager, mock_storage):
        openai_data = {"data": {"openai": "data"}}
        anthropic_data = {"data": {"anthropic": "data"}}

        # get_deprecation_data makes multiple calls for each provider
        # (searching back in time up to max_age_days)
        # We'll return data on first call for openai and anthropic, None for others
        def side_effect(key):
            if "openai" in key:
                return json.dumps(openai_data).encode()
            elif "anthropic" in key:
                return json.dumps(anthropic_data).encode()
            else:
                return None

        mock_storage.get.side_effect = side_effect

        result = await cache_manager.get_all_providers_data()

        assert "openai" in result
        assert "anthropic" in result
        assert "google" not in result
        assert result["openai"] == {"openai": "data"}
        assert result["anthropic"] == {"anthropic": "data"}

    def it_selects_correct_storage_backend(self):
        with patch.dict("os.environ", {}, clear=True):
            manager = CacheManager()
            assert isinstance(manager.storage, FileSystemStorage)

        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}):
            from src.cache.storage.github_actions import GitHubActionsStorage

            manager = CacheManager()
            assert isinstance(manager.storage, GitHubActionsStorage)
