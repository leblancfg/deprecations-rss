"""Tests for cache storage backends."""

import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.cache.storage.filesystem import FileSystemStorage
from src.cache.storage.github_actions import GitHubActionsStorage


@pytest.fixture
async def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def filesystem_storage(temp_cache_dir):
    """Create a FileSystemStorage instance with temp directory."""
    return FileSystemStorage(cache_dir=temp_cache_dir / "cache")


@pytest.fixture
async def github_actions_storage(temp_cache_dir):
    """Create a GitHubActionsStorage instance with temp directory."""
    return GitHubActionsStorage(cache_dir=temp_cache_dir / "gh-cache")


class DescribeStorageBackend:
    """Test the abstract StorageBackend class."""

    def it_generates_keys_correctly(self):
        backend = FileSystemStorage()  # Use concrete implementation

        key = backend.generate_key("test", "item1")
        assert key == "test:item1"

        date = datetime(2024, 1, 15, tzinfo=UTC)
        key_with_date = backend.generate_key("test", "item2", date)
        assert key_with_date == "test:item2:2024-01-15"


class DescribeFilesystemStorage:
    """Test the FileSystemStorage implementation."""

    @pytest.mark.asyncio
    async def it_stores_and_retrieves_data(self, filesystem_storage):
        key = "test:key"
        value = b"test data"

        assert await filesystem_storage.set(key, value)
        retrieved = await filesystem_storage.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def it_checks_key_existence(self, filesystem_storage):
        key = "test:exists"
        value = b"data"

        assert not await filesystem_storage.exists(key)
        await filesystem_storage.set(key, value)
        assert await filesystem_storage.exists(key)

    @pytest.mark.asyncio
    async def it_deletes_keys(self, filesystem_storage):
        key = "test:delete"
        value = b"data to delete"

        await filesystem_storage.set(key, value)
        assert await filesystem_storage.exists(key)

        assert await filesystem_storage.delete(key)
        assert not await filesystem_storage.exists(key)

    @pytest.mark.asyncio
    async def it_handles_ttl_expiration(self, filesystem_storage):
        key = "test:ttl"
        value = b"expiring data"

        await filesystem_storage.set(key, value, ttl=1)
        assert await filesystem_storage.exists(key)

        await asyncio.sleep(2)
        assert not await filesystem_storage.exists(key)
        assert await filesystem_storage.get(key) is None

    @pytest.mark.asyncio
    async def it_stores_and_retrieves_metadata(self, filesystem_storage):
        key = "test:metadata"
        value = b"data with metadata"

        await filesystem_storage.set(key, value)
        metadata = await filesystem_storage.get_metadata(key)

        assert metadata is not None
        assert metadata["key"] == key
        assert metadata["size"] == len(value)
        assert "created_at" in metadata

    @pytest.mark.asyncio
    async def it_clears_all_cache(self, filesystem_storage):
        keys = ["test:clear1", "test:clear2", "test:clear3"]

        for key in keys:
            await filesystem_storage.set(key, b"data")

        for key in keys:
            assert await filesystem_storage.exists(key)

        assert await filesystem_storage.clear()

        for key in keys:
            assert not await filesystem_storage.exists(key)

    @pytest.mark.asyncio
    async def it_lists_keys_with_pattern(self, filesystem_storage):
        await filesystem_storage.set("users:alice", b"alice data")
        await filesystem_storage.set("users:bob", b"bob data")
        await filesystem_storage.set("posts:1", b"post data")

        all_keys = await filesystem_storage.list_keys()
        assert len(all_keys) == 3

        user_keys = await filesystem_storage.list_keys("users:")
        assert len(user_keys) == 2
        assert "users:alice" in user_keys
        assert "users:bob" in user_keys
        assert "posts:1" not in user_keys


class DescribeGithubActionsStorage:
    """Test the GitHubActionsStorage implementation."""

    @pytest.mark.asyncio
    async def it_inherits_filesystem_functionality(self, github_actions_storage):
        key = "test:gh"
        value = b"github data"

        assert await github_actions_storage.set(key, value)
        retrieved = await github_actions_storage.get(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def it_maintains_state_file(self, github_actions_storage):
        state_file = github_actions_storage._state_file
        assert state_file.exists()

        state = json.loads(state_file.read_text())
        assert "version" in state
        assert "created_at" in state
        assert "entries" in state

    @pytest.mark.asyncio
    async def it_updates_state_on_operations(self, github_actions_storage):
        key = "test:state"
        value = b"state test"

        await github_actions_storage.set(key, value)

        state = json.loads(github_actions_storage._state_file.read_text())
        assert key in state["entries"]
        assert state["entries"][key]["status"] == "active"

        await github_actions_storage.delete(key)

        state = json.loads(github_actions_storage._state_file.read_text())
        assert key not in state["entries"]

    @pytest.mark.asyncio
    async def it_generates_action_cache_keys(self, github_actions_storage):
        date = datetime(2024, 1, 15, tzinfo=UTC)
        cache_key = github_actions_storage.get_cache_key_for_actions("test", date)

        assert "deprecations-cache-test-2024-01-15" in cache_key
        assert "week" in cache_key

    @pytest.mark.asyncio
    async def it_prepares_cache_for_actions(self, github_actions_storage):
        await github_actions_storage.set("test:prep", b"data")

        cache_config = await github_actions_storage.prepare_for_cache_action()

        assert "path" in cache_config
        assert "key" in cache_config
        assert "restore-keys" in cache_config
        assert isinstance(cache_config["restore-keys"], list)
        assert len(cache_config["restore-keys"]) > 0

    @pytest.mark.asyncio
    async def it_provides_cache_info(self, github_actions_storage):
        await github_actions_storage.set("test:info", b"info data")

        info = await github_actions_storage.get_cache_info()

        assert "version" in info
        assert "created_at" in info
        assert "total_entries" in info
        assert "total_size_bytes" in info
        assert "cache_directory" in info
        assert "is_github_actions" in info

    def it_detects_github_actions_environment(self, github_actions_storage, monkeypatch):
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        assert not github_actions_storage._is_github_actions()

        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert github_actions_storage._is_github_actions()
