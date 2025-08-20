"""Caching infrastructure for deprecation data."""

from src.cache.manager import CacheEntry, CacheManager
from src.cache.storage.base import StorageBackend
from src.cache.storage.filesystem import FileSystemStorage
from src.cache.storage.github_actions import GitHubActionsStorage

__all__ = [
    "CacheEntry",
    "CacheManager",
    "StorageBackend",
    "FileSystemStorage",
    "GitHubActionsStorage",
]
