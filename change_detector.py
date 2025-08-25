"""Change detection system to minimize LLM API calls."""

import hashlib
import json
from pathlib import Path
from typing import Dict, List


class ChangeDetector:
    """Detects changes in scraped data to minimize LLM API calls."""
    
    def __init__(self, cache_file: str = "data_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load existing cache of content hashes."""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_cache(self):
        """Save cache to disk."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _hash_content(self, item: Dict) -> str:
        """Create stable hash of deprecation content."""
        # Only hash the core content that matters for change detection
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
    
    def _create_item_key(self, item: Dict) -> str:
        """Create unique key for deprecation item."""
        provider = item.get('provider', 'unknown')
        title = item.get('title', 'unknown')
        # Clean title for key
        clean_title = title.replace(':', '_').replace(' ', '_')
        return f"{provider}_{clean_title}"[:100]
    
    def detect_changes(self, scraped_data: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """
        Detect which items have changed and need LLM analysis.
        
        Returns:
            (changed_items, unchanged_items)
        """
        changed_items = []
        unchanged_items = []
        new_cache = {}
        
        for item in scraped_data:
            item_key = self._create_item_key(item)
            content_hash = self._hash_content(item)
            
            # Check if content has changed
            if (item_key not in self.cache or 
                self.cache[item_key].get('content_hash') != content_hash):
                changed_items.append(item)
            else:
                # Use cached analysis if available
                cached_analysis = self.cache[item_key].get('llm_analysis')
                if cached_analysis:
                    # Merge cached analysis with current scraped data
                    enhanced_item = {**item, **cached_analysis}
                    unchanged_items.append(enhanced_item)
                else:
                    unchanged_items.append(item)
            
            # Update cache with current hash
            new_cache[item_key] = {
                'content_hash': content_hash,
                'llm_analysis': self.cache.get(item_key, {}).get('llm_analysis')
            }
        
        # Update cache
        self.cache = new_cache
        self._save_cache()
        
        return changed_items, unchanged_items
    
    def cache_llm_analysis(self, item: Dict, analysis: Dict):
        """Cache LLM analysis result for future use."""
        item_key = self._create_item_key(item)
        if item_key in self.cache:
            self.cache[item_key]['llm_analysis'] = analysis
            self._save_cache()