"""GitHub Actions cache storage backend."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.cache.storage.filesystem import FileSystemStorage


class GitHubActionsStorage(FileSystemStorage):
    """GitHub Actions cache storage using actions/cache.

    This storage backend extends FileSystemStorage to work with GitHub Actions cache.
    It uses a specific directory structure that can be cached and restored between runs.
    """

    def __init__(self, cache_dir: Path | None = None):
        """Initialize GitHub Actions storage.

        Args:
            cache_dir: Directory for cache storage. Defaults to GitHub workspace cache
        """
        if cache_dir is None:
            workspace = os.environ.get("GITHUB_WORKSPACE", ".")
            cache_dir = Path(workspace) / ".github-cache" / "deprecations"

        super().__init__(cache_dir)

        self._state_file = self.cache_dir / "cache-state.json"
        self._ensure_state_file()

    def _ensure_state_file(self) -> None:
        """Ensure cache state file exists."""
        if not self._state_file.exists():
            initial_state = {
                "version": "1.0.0",
                "created_at": datetime.now(UTC).isoformat(),
                "last_updated": datetime.now(UTC).isoformat(),
                "entries": {},
            }
            self._state_file.write_text(json.dumps(initial_state, indent=2))

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Store data in cache and update state file."""
        result = await super().set(key, value, ttl)

        if result:
            await self._update_state(key, "added")

        return result

    async def delete(self, key: str) -> bool:
        """Delete cached data and update state file."""
        result = await super().delete(key)

        if result:
            await self._update_state(key, "deleted")

        return result

    async def _update_state(self, key: str, action: str) -> None:
        """Update the cache state file.

        Args:
            key: The cache key
            action: The action performed ('added', 'deleted', etc.)
        """
        try:
            state = json.loads(self._state_file.read_text())
            state["last_updated"] = datetime.now(UTC).isoformat()

            if action == "added":
                state["entries"][key] = {
                    "added_at": datetime.now(UTC).isoformat(),
                    "status": "active",
                }
            elif action == "deleted" and key in state["entries"]:
                del state["entries"][key]

            self._state_file.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    async def get_cache_info(self) -> dict[str, Any]:
        """Get information about the current cache state.

        Returns:
            Dictionary with cache information
        """
        try:
            state = json.loads(self._state_file.read_text())

            total_size = 0
            for cache_file in self.cache_dir.glob("*.cache"):
                total_size += cache_file.stat().st_size

            return {
                "version": state.get("version", "unknown"),
                "created_at": state.get("created_at"),
                "last_updated": state.get("last_updated"),
                "total_entries": len(state.get("entries", {})),
                "total_size_bytes": total_size,
                "cache_directory": str(self.cache_dir),
                "is_github_actions": self._is_github_actions(),
            }
        except Exception:
            return {
                "error": "Could not retrieve cache information",
                "cache_directory": str(self.cache_dir),
                "is_github_actions": self._is_github_actions(),
            }

    def _is_github_actions(self) -> bool:
        """Check if running in GitHub Actions environment."""
        return os.environ.get("GITHUB_ACTIONS") == "true"

    def get_cache_key_for_actions(self, base_key: str, date: datetime | None = None) -> str:
        """Generate a cache key suitable for GitHub Actions cache action.

        Args:
            base_key: Base cache key
            date: Optional date for the cache key

        Returns:
            Cache key formatted for GitHub Actions
        """
        if date is None:
            date = datetime.now(UTC)

        date_str = date.strftime("%Y-%m-%d")
        week_str = date.strftime("%Y-W%U")

        return f"deprecations-cache-{base_key}-{date_str}-week-{week_str}"

    async def prepare_for_cache_action(self) -> dict[str, Any]:
        """Prepare cache for GitHub Actions cache action.

        Returns:
            Dictionary with cache paths and keys for GitHub Actions
        """
        cache_info = await self.get_cache_info()
        date = datetime.now(UTC)

        return {
            "path": str(self.cache_dir),
            "key": self.get_cache_key_for_actions("primary", date),
            "restore-keys": [
                self.get_cache_key_for_actions("primary", date),
                f"deprecations-cache-primary-{date.strftime('%Y-%m-')}",
                f"deprecations-cache-primary-{date.strftime('%Y-')}",
                "deprecations-cache-primary-",
            ],
            "cache_info": cache_info,
        }
