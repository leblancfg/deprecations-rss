# Scrapers Module

This module provides utilities and base classes for scraping AI model deprecation data from various providers.

## Structure

- `base_scraper.py` - Abstract base class with common scraping functionality
- `utils.py` - Utility functions for date parsing, text cleaning, and URL handling
- `example_scraper.py` - Example implementation showing how to create provider-specific scrapers

## Creating a New Scraper

To create a scraper for a new provider:

1. Create a new file for your provider (e.g., `openai_scraper.py`)
2. Extend the `BaseScraper` class
3. Implement the `extract_deprecations()` method

### Example

```python
from src.scrapers.base_scraper import BaseScraper

class OpenAIScraper(BaseScraper):
    async def extract_deprecations(self) -> list[dict[str, Any]]:
        # Fetch the deprecation page
        html = await self.fetch(self.url)
        soup = await self.parse_html(html)
        
        deprecations = []
        # Parse the HTML and extract deprecation data
        # Use self.extract_text() and self.extract_date() helpers
        
        return deprecations
```

## Utilities

### Date Parsing
- Handles ISO, RFC, and human-readable date formats
- Automatically adds UTC timezone if missing

### Text Cleaning
- Removes HTML tags and entities
- Normalizes whitespace
- Optionally preserves line breaks

### URL Handling
- Validates HTTP(S) URLs
- Normalizes URLs for consistent comparison

## Error Handling

The base scraper includes:
- Automatic retry with exponential backoff
- Configurable timeouts and retry attempts
- Proper exception handling and reporting

## Testing

Each scraper should have corresponding tests following the pytest-describe pattern.
See `tests/scrapers/` for examples.