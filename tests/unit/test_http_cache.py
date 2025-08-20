"""Tests for HTTPCache class."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.cache.http_cache import HTTPCache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def http_cache(temp_cache_dir):
    """Create an HTTPCache instance with temporary storage."""
    return HTTPCache(cache_dir=temp_cache_dir)


class DescribeHTTPCache:
    """Tests for HTTPCache functionality."""

    @pytest.mark.asyncio
    async def it_fetches_and_caches_response(self, http_cache):
        """Should fetch URL and cache the response."""
        url = "https://api.example.com/data"
        content = b"test data"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "public, max-age=3600",
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.content = content
        mock_response.headers = headers
        mock_response.status_code = 200

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            # First fetch - should hit the network
            result = await http_cache.get(url)

            assert result == content
            mock_fetch.assert_called_once_with(url, {})

            # Second fetch - should use cache
            result2 = await http_cache.get(url)

            assert result2 == content
            mock_fetch.assert_called_once()  # Still only called once

    @pytest.mark.asyncio
    async def it_respects_cache_control_max_age(self, http_cache):
        """Should respect Cache-Control max-age directive."""
        url = "https://api.example.com/data"
        content = b"test data"

        # Response with 1 hour max-age
        headers = {"Cache-Control": "public, max-age=3600"}

        mock_response = Mock(spec=httpx.Response)
        mock_response.content = content
        mock_response.headers = headers
        mock_response.status_code = 200

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            # First fetch
            await http_cache.get(url)

            # Manually expire the cache by modifying the timestamp
            cache_file = http_cache.cache_dir / http_cache._get_cache_key(url)
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text())
                # Set timestamp to 2 hours ago
                old_timestamp = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
                cache_data["timestamp"] = old_timestamp
                cache_file.write_text(json.dumps(cache_data))

            # Should fetch again because cache is expired
            await http_cache.get(url)

            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def it_uses_etag_for_conditional_requests(self, http_cache):
        """Should use ETag for conditional requests when available."""
        url = "https://api.example.com/data"
        content = b"test data"
        etag = '"33a64df551425fcc55e4d42a148795d9f25f89d4"'

        # Initial response with ETag
        initial_response = Mock(spec=httpx.Response)
        initial_response.content = content
        initial_response.headers = {"ETag": etag}
        initial_response.status_code = 200

        # 304 Not Modified response
        not_modified_response = Mock(spec=httpx.Response)
        not_modified_response.status_code = 304

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [initial_response, not_modified_response]

            # First fetch - gets full response
            result1 = await http_cache.get(url)
            assert result1 == content

            # Expire cache to trigger conditional request
            cache_file = http_cache.cache_dir / http_cache._get_cache_key(url)
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text())
                # Set timestamp to trigger re-validation
                old_timestamp = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
                cache_data["timestamp"] = old_timestamp
                cache_file.write_text(json.dumps(cache_data))

            # Second fetch - should send If-None-Match header
            result2 = await http_cache.get(url)
            assert result2 == content  # Should return cached content

            # Check that conditional headers were sent
            second_call_headers = mock_fetch.call_args_list[1][0][1]
            assert "If-None-Match" in second_call_headers
            assert second_call_headers["If-None-Match"] == etag

    @pytest.mark.asyncio
    async def it_uses_last_modified_for_conditional_requests(self, http_cache):
        """Should use Last-Modified for conditional requests when available."""
        url = "https://api.example.com/data"
        content = b"test data"
        last_modified = "Wed, 21 Oct 2024 07:28:00 GMT"

        # Initial response with Last-Modified
        initial_response = Mock(spec=httpx.Response)
        initial_response.content = content
        initial_response.headers = {"Last-Modified": last_modified}
        initial_response.status_code = 200

        # 304 Not Modified response
        not_modified_response = Mock(spec=httpx.Response)
        not_modified_response.status_code = 304

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [initial_response, not_modified_response]

            # First fetch
            await http_cache.get(url)

            # Expire cache
            cache_file = http_cache.cache_dir / http_cache._get_cache_key(url)
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text())
                old_timestamp = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
                cache_data["timestamp"] = old_timestamp
                cache_file.write_text(json.dumps(cache_data))

            # Second fetch should use If-Modified-Since
            await http_cache.get(url)

            second_call_headers = mock_fetch.call_args_list[1][0][1]
            assert "If-Modified-Since" in second_call_headers
            assert second_call_headers["If-Modified-Since"] == last_modified

    @pytest.mark.asyncio
    async def it_falls_back_to_cache_on_network_error(self, http_cache):
        """Should return cached data when network request fails."""
        url = "https://api.example.com/data"
        content = b"cached data"

        # Initial successful response
        initial_response = Mock(spec=httpx.Response)
        initial_response.content = content
        initial_response.headers = {}
        initial_response.status_code = 200

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            # First call succeeds, second fails
            mock_fetch.side_effect = [
                initial_response,
                httpx.NetworkError("Connection failed"),
            ]

            # First fetch - successful
            result1 = await http_cache.get(url)
            assert result1 == content

            # Expire cache
            cache_file = http_cache.cache_dir / http_cache._get_cache_key(url)
            if cache_file.exists():
                cache_data = json.loads(cache_file.read_text())
                old_timestamp = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
                cache_data["timestamp"] = old_timestamp
                cache_file.write_text(json.dumps(cache_data))

            # Second fetch - network error, should return stale cache
            result2 = await http_cache.get(url)
            assert result2 == content

    @pytest.mark.asyncio
    async def it_handles_cache_directory_creation(self, tmp_path):
        """Should create cache directory if it doesn't exist."""
        non_existent_dir = tmp_path / "new_cache"
        HTTPCache(cache_dir=non_existent_dir)  # Creating the cache should create the directory

        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()

    @pytest.mark.asyncio
    async def it_generates_consistent_cache_keys(self, http_cache):
        """Should generate consistent cache keys for URLs."""
        url1 = "https://api.example.com/data"
        url2 = "https://api.example.com/data"
        url3 = "https://api.example.com/other"

        key1 = http_cache._get_cache_key(url1)
        key2 = http_cache._get_cache_key(url2)
        key3 = http_cache._get_cache_key(url3)

        assert key1 == key2  # Same URL should produce same key
        assert key1 != key3  # Different URLs should produce different keys

    @pytest.mark.asyncio
    async def it_clears_cache(self, http_cache):
        """Should be able to clear all cache entries."""
        url1 = "https://api.example.com/data1"
        url2 = "https://api.example.com/data2"

        mock_response = Mock(spec=httpx.Response)
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.status_code = 200

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            # Cache some data
            await http_cache.get(url1)
            await http_cache.get(url2)

            # Verify cache files exist
            assert len(list(http_cache.cache_dir.glob("*.json"))) == 2

            # Clear cache
            http_cache.clear()

            # Verify cache is empty
            assert len(list(http_cache.cache_dir.glob("*.json"))) == 0

    @pytest.mark.asyncio
    async def it_invalidates_specific_url(self, http_cache):
        """Should be able to invalidate cache for specific URL."""
        url1 = "https://api.example.com/data1"
        url2 = "https://api.example.com/data2"

        mock_response = Mock(spec=httpx.Response)
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.status_code = 200

        with patch.object(http_cache, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            # Cache some data
            await http_cache.get(url1)
            await http_cache.get(url2)

            # Invalidate only url1
            http_cache.invalidate(url1)

            # url1 cache should be gone, url2 should remain
            key1 = http_cache._get_cache_key(url1)
            key2 = http_cache._get_cache_key(url2)

            assert not (http_cache.cache_dir / key1).exists()
            assert (http_cache.cache_dir / key2).exists()

    @pytest.mark.asyncio
    async def it_extracts_max_age_from_various_cache_control_formats(self, http_cache):
        """Should correctly parse max-age from different Cache-Control formats."""
        test_cases = [
            ("max-age=3600", 3600),
            ("public, max-age=7200", 7200),
            ("max-age=300, must-revalidate", 300),
            ("private, max-age=0", 0),
            ("no-cache", None),
            ("no-store", None),
            ("", None),
        ]

        for cache_control, expected_max_age in test_cases:
            max_age = http_cache._parse_max_age(cache_control)
            assert max_age == expected_max_age
