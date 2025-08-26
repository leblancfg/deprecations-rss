"""Cache manager for HTML responses to speed up development."""

import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any


class CacheManager:
    """Manages cached HTML responses with TTL support."""
    
    def __init__(self, cache_dir: str = "cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.html_dir = self.cache_dir / "html"
        self.manifest_path = self.cache_dir / "cache_manifest.json"
        self.ttl_hours = ttl_hours
        
        # Create cache directories
        self.html_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create manifest
        self.manifest = self._load_manifest()
    
    def _load_manifest(self) -> Dict[str, Any]:
        """Load the cache manifest or create empty one."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_manifest(self):
        """Save the manifest to disk."""
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def _get_cache_key(self, provider: str, url: str) -> str:
        """Generate a cache key from provider and URL."""
        # Use a hash to handle long URLs and special characters
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{provider}_{url_hash}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.html_dir / f"{cache_key}.html"
    
    def is_cached(self, provider: str, url: str) -> bool:
        """Check if valid cached content exists."""
        cache_key = self._get_cache_key(provider, url)
        
        if cache_key not in self.manifest:
            return False
        
        entry = self.manifest[cache_key]
        cached_at = datetime.fromisoformat(entry["cached_at"])
        expires_at = cached_at + timedelta(hours=self.ttl_hours)
        
        # Check if cache has expired
        if datetime.now(timezone.utc) > expires_at:
            return False
        
        # Check if file exists
        cache_path = self._get_cache_path(cache_key)
        return cache_path.exists()
    
    def get_cached_html(self, provider: str, url: str) -> Optional[str]:
        """Get cached HTML if available and not expired."""
        if not self.is_cached(provider, url):
            return None
        
        cache_key = self._get_cache_key(provider, url)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        except IOError:
            # Remove from manifest if file read fails
            if cache_key in self.manifest:
                del self.manifest[cache_key]
                self._save_manifest()
            return None
    
    def save_html(self, provider: str, url: str, html: str):
        """Save HTML content to cache."""
        cache_key = self._get_cache_key(provider, url)
        cache_path = self._get_cache_path(cache_key)
        
        # Write HTML file
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Update manifest
        self.manifest[cache_key] = {
            "provider": provider,
            "url": url,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "ttl_hours": self.ttl_hours,
            "file": str(cache_path.relative_to(self.cache_dir))
        }
        self._save_manifest()
    
    def clear_expired(self):
        """Remove expired cache entries."""
        expired_keys = []
        
        for cache_key, entry in self.manifest.items():
            cached_at = datetime.fromisoformat(entry["cached_at"])
            expires_at = cached_at + timedelta(hours=entry.get("ttl_hours", self.ttl_hours))
            
            if datetime.now(timezone.utc) > expires_at:
                expired_keys.append(cache_key)
                # Delete the file
                cache_path = self._get_cache_path(cache_key)
                if cache_path.exists():
                    cache_path.unlink()
        
        # Remove from manifest
        for key in expired_keys:
            del self.manifest[key]
        
        if expired_keys:
            self._save_manifest()
            print(f"Cleared {len(expired_keys)} expired cache entries")
    
    def clear_all(self):
        """Clear all cache entries."""
        # Remove all HTML files
        for html_file in self.html_dir.glob("*.html"):
            html_file.unlink()
        
        # Clear manifest
        self.manifest = {}
        self._save_manifest()
        
        print("Cleared all cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.manifest)
        valid_entries = sum(1 for p, u in [
            (e["provider"], e["url"]) for e in self.manifest.values()
        ] if self.is_cached(p, u))
        
        total_size = sum(
            self._get_cache_path(k).stat().st_size 
            for k in self.manifest 
            if self._get_cache_path(k).exists()
        )
        
        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2)
        }