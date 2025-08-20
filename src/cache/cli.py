"""CLI commands for cache management."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from src.cache import CacheManager


async def update_with_cache(provider: str | None = None) -> dict[str, Any]:
    """Update deprecation data with cache support.

    Args:
        provider: Optional specific provider to update

    Returns:
        Dictionary with update results
    """
    cache_manager = CacheManager()
    results = {}

    providers = [provider] if provider else ["openai", "anthropic", "google", "mistral", "cohere"]

    for prov in providers:
        try:

            async def fetch_provider_data(provider: str = prov) -> dict[str, str]:
                # This would be replaced with actual scraper call
                print(f"Fetching fresh data for {provider}...")
                # Simulate scraper - in real implementation, call the actual scraper
                return {"status": "scraped", "timestamp": datetime.now(UTC).isoformat()}

            data = await cache_manager.get_with_fallback(
                key=cache_manager.storage.generate_key("deprecations", prov, datetime.now(UTC)),
                fetch_func=fetch_provider_data,
                ttl=86400,
                use_stale_on_error=True,
            )

            results[prov] = {
                "success": True,
                "data": data,
                "source": "fresh" if data and data.get("status") == "scraped" else "cache",
            }

        except Exception as e:
            results[prov] = {"success": False, "error": str(e)}

    return results


async def fallback_to_cache() -> dict[str, Any]:
    """Load all available data from cache when scraping fails.

    Returns:
        Dictionary with cached data for all providers
    """
    cache_manager = CacheManager()

    print("Loading data from cache...")
    cached_data = await cache_manager.get_all_providers_data()

    if not cached_data:
        print("Warning: No cached data available")
        return {}

    print(f"Loaded cached data for {len(cached_data)} providers")
    return cached_data


async def cache_status() -> dict[str, Any]:
    """Get current cache status and statistics.

    Returns:
        Dictionary with cache status information
    """
    cache_manager = CacheManager()

    if hasattr(cache_manager.storage, "get_cache_info"):
        info = await cache_manager.storage.get_cache_info()
    else:
        info = {"message": "Cache info not available for this storage backend"}

    # Check data availability for each provider
    providers_status = {}
    for provider in ["openai", "anthropic", "google", "mistral", "cohere"]:
        data = await cache_manager.get_deprecation_data(provider, max_age_days=1)
        providers_status[provider] = "available" if data else "missing"

    return {
        "storage_info": info,
        "providers": providers_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def clear_cache(confirm: bool = False) -> bool:
    """Clear all cached data.

    Args:
        confirm: Must be True to actually clear the cache

    Returns:
        True if cache was cleared
    """
    if not confirm:
        print("Cache clear cancelled. Pass confirm=True to clear.")
        return False

    cache_manager = CacheManager()
    result = await cache_manager.storage.clear()

    if result:
        print("Cache cleared successfully")
    else:
        print("Failed to clear cache")

    return result


def main() -> None:
    """CLI entry point for cache management."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.cache.cli [update|fallback|status|clear]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "update":
        result = asyncio.run(update_with_cache())
        print(json.dumps(result, indent=2))

    elif command == "fallback":
        result = asyncio.run(fallback_to_cache())
        print(json.dumps(result, indent=2, default=str))

    elif command == "status":
        result = asyncio.run(cache_status())
        print(json.dumps(result, indent=2))

    elif command == "clear":
        confirm = "--confirm" in sys.argv
        asyncio.run(clear_cache(confirm))

    else:
        print(f"Unknown command: {command}")
        print("Available commands: update, fallback, status, clear")
        sys.exit(1)


if __name__ == "__main__":
    main()
