"""Change detection system to minimize LLM API calls."""

import hashlib
import json
import subprocess
from typing import Dict, List


class ChangeDetector:
    """Detects changes in scraped data by comparing with git history."""
    
    def _hash_item(self, item: Dict) -> str:
        """Create stable hash of scraped content (before LLM enhancement)."""
        key_fields = {
            'provider': item.get('provider', ''),
            'title': item.get('title', ''),
            'content': item.get('content', ''),
            'announcement_date': item.get('announcement_date', ''),
            'shutdown_date': item.get('shutdown_date', ''),
            'url': item.get('url', '')
        }
        content_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def _get_previous_data(self) -> List[Dict]:
        """Get previous data.json from git main branch."""
        try:
            result = subprocess.run(
                ['git', 'show', 'main:data.json'],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return []
    
    def detect_changes(self, current_data: List[Dict]) -> List[Dict]:
        """
        Detect which items need LLM analysis by comparing with git history.
        Returns items that are new or changed from the previous run.
        """
        previous_data = self._get_previous_data()
        previous_hashes = {self._hash_item(item) for item in previous_data}
        
        return [item for item in current_data 
                if self._hash_item(item) not in previous_hashes]