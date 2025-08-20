"""OpenAI deprecations scraper."""

import json
import re
from typing import Any

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.scrapers.base import BaseScraper, ScraperResult
from src.scrapers.cache import CacheManager


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI model and API deprecations."""

    provider_name = "openai"
    base_url = "https://platform.openai.com/docs/deprecations"
    expected_url_patterns = [
        r"https://platform\.openai\.com/docs/deprecations.*",
        r"https://api\.openai\.com/v1/deprecations.*",
        r"https://platform\.openai\.com/docs/api-reference/deprecations.*",
    ]

    # Additional URLs to check for deprecations
    additional_urls = [
        "https://platform.openai.com/docs/models",
        "https://platform.openai.com/docs/api-reference",
    ]

    @property
    def sample_deprecations_html(self) -> str:
        """Sample HTML for testing."""
        return """<html><body>Sample deprecations</body></html>"""

    async def extract_deprecations(self, content: str) -> list[dict[str, Any]]:
        """Extract deprecation information from HTML content.
        
        Args:
            content: HTML content from OpenAI deprecations page
            
        Returns:
            List of deprecation dictionaries
        """
        deprecations = []
        soup = BeautifulSoup(content, "html.parser")

        # Look for deprecation tables
        tables = soup.find_all("table")
        for table in tables:
            deprecations.extend(self._extract_from_table(table))

        # Look for deprecation notices in text
        deprecations.extend(self._extract_from_notices(soup))

        # Look for model-specific deprecations
        deprecations.extend(self._extract_model_deprecations(soup))

        # Remove duplicates based on model name
        seen = set()
        unique_deprecations = []
        for dep in deprecations:
            key = dep.get("model") or dep.get("endpoint")
            if key and key not in seen:
                seen.add(key)
                unique_deprecations.append(dep)

        return unique_deprecations

    def _extract_from_table(self, table: Any) -> list[dict[str, Any]]:
        """Extract deprecations from HTML table."""
        deprecations: list[dict[str, Any]] = []

        rows = table.find_all("tr")
        if not rows:
            return deprecations

        # Try to identify header row
        headers = []
        header_row = table.find("thead")
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]
        elif rows:
            # Assume first row is header
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
            rows = rows[1:]

        # Map headers to expected fields
        header_map = {
            "model": ["model", "model name", "name"],
            "deprecation_date": ["deprecation date", "deprecated", "deprecation", "announced"],
            "retirement_date": ["shutdown date", "retirement date", "shutdown", "retired", "end date"],
            "replacement": ["replacement", "migrate to", "use instead", "alternative"],
        }

        # Process data rows
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            deprecation: dict[str, Any] = {}

            for i, cell in enumerate(cells):
                if i >= len(headers):
                    break

                header = headers[i]
                value = cell.get_text(strip=True)

                # Map header to field
                for field, variations in header_map.items():
                    if header in variations:
                        if "date" in field:
                            value = self.normalize_date(value)
                        deprecation[field] = value
                        break

            if deprecation:
                deprecations.append(deprecation)

        return deprecations

    def _extract_from_notices(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract deprecations from notice text."""
        deprecations = []

        # Look for deprecation notices
        notice_patterns = [
            r"([\w\-\.]+)\s+will be deprecated on\s+([^,\.]+)",
            r"([\w\-\.]+)\s+deprecated on\s+([^,\.]+)",
            r"deprecating\s+([\w\-\.]+)\s+on\s+([^,\.]+)",
            r"([\w\-\.]+).*?Use\s+([\w\-\.]+)\s+instead",
        ]

        text_content = soup.get_text()

        for pattern in notice_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 2:
                    model = match.group(1)

                    # Skip if it's not a model name
                    if not re.match(r"^[a-z0-9\-\.]+$", model, re.IGNORECASE):
                        continue

                    deprecation = {"model": model}

                    # Check if second group is a date or replacement
                    second_group = match.group(2)
                    if self._looks_like_date(second_group):
                        deprecation["deprecation_date"] = self.normalize_date(second_group)
                    else:
                        deprecation["replacement"] = second_group

                    # Try to find replacement in nearby text
                    if "replacement" not in deprecation:
                        replacement = self._find_replacement_nearby(text_content, model)
                        if replacement:
                            deprecation["replacement"] = replacement

                    deprecations.append(deprecation)

        return deprecations

    def _extract_model_deprecations(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract model-specific deprecations from sections."""
        deprecations = []

        # Look for model family sections
        for heading in soup.find_all(["h2", "h3"]):
            heading_text = heading.get_text(strip=True).lower()

            # Check if this is a model family section
            if any(family in heading_text for family in ["gpt", "turbo", "davinci", "curie", "babbage", "ada"]):
                # Extract deprecations from the following content
                sibling = heading.find_next_sibling()
                while sibling and sibling.name not in ["h2", "h3"]:
                    text = sibling.get_text(strip=True)

                    # Look for model names and dates
                    model_pattern = r"(gpt-[\w\-\.]+|text-[\w\-\.]+|[\w]+-[\w\-\.]+)"
                    models = re.findall(model_pattern, text, re.IGNORECASE)

                    for model in models:
                        # Look for associated date
                        date_pattern = rf"{re.escape(model)}.*?(\w+\s+\d+,?\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"
                        date_match = re.search(date_pattern, text, re.IGNORECASE)

                        if date_match:
                            deprecation = {
                                "model": model,
                                "deprecation_date": self.normalize_date(date_match.group(1))
                            }

                            # Look for replacement
                            replacement = self._find_replacement_nearby(text, model)
                            if replacement:
                                deprecation["replacement"] = replacement

                            deprecations.append(deprecation)

                    sibling = sibling.find_next_sibling()

        return deprecations

    def _looks_like_date(self, text: str) -> bool:
        """Check if text looks like a date."""
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",
            r"\w+\s+\d+,?\s+\d{4}",
            r"\d+/\d+/\d{4}",
        ]

        for pattern in date_patterns:
            if re.match(pattern, text.strip(), re.IGNORECASE):
                return True
        return False

    def _find_replacement_nearby(self, text: str, model: str) -> str | None:
        """Find replacement model mentioned near the deprecated model."""
        # Look for replacement patterns near the model
        patterns = [
            rf"{re.escape(model)}.*?use\s+([\w\-\.]+)",
            rf"{re.escape(model)}.*?replaced (?:by|with)\s+([\w\-\.]+)",
            rf"{re.escape(model)}.*?migrate to\s+([\w\-\.]+)",
            rf"([\w\-\.]+)\s+replaces\s+{re.escape(model)}",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                replacement = match.group(1)
                # Validate it looks like a model name
                if re.match(r"^[a-z0-9\-\.]+$", replacement, re.IGNORECASE):
                    return replacement

        return None

    def normalize_date(self, date_str: str) -> str:
        """Normalize various date formats to ISO format (YYYY-MM-DD).
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            ISO formatted date string
        """
        if not date_str:
            return ""

        date_str = date_str.strip()

        # Already in ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        try:
            # Use dateutil parser for flexible parsing
            parsed_date = date_parser.parse(date_str)
            return parsed_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            # If parsing fails, return original
            return date_str

    async def extract_api_deprecations(self, content: str) -> list[dict[str, Any]]:
        """Extract API endpoint deprecations from JSON content.
        
        Args:
            content: JSON content with API deprecations
            
        Returns:
            List of deprecation dictionaries
        """
        try:
            data = json.loads(content)
            deprecations = data.get("deprecations", [])

            # Normalize date fields
            for dep in deprecations:
                if "deprecation_date" in dep:
                    dep["deprecation_date"] = self.normalize_date(dep["deprecation_date"])
                if "shutdown_date" in dep:
                    dep["retirement_date"] = self.normalize_date(dep.pop("shutdown_date"))
                if "retired_date" in dep:
                    dep["retirement_date"] = self.normalize_date(dep.pop("retired_date"))

            return deprecations  # type: ignore[no-any-return]

        except json.JSONDecodeError:
            return []

    async def scrape_with_cache(self, cache_manager: CacheManager) -> ScraperResult:
        """Scrape with cache fallback support.
        
        Args:
            cache_manager: Cache manager instance
            
        Returns:
            ScraperResult with data or from cache
        """
        # Try to scrape from primary URL
        result = await self.scrape()

        if result.success and result.data:
            # Save to cache
            entry = cache_manager.create_from_result(result, url=self.base_url)
            cache_manager.save(entry)
            return result

        # Try additional URLs
        for url in self.additional_urls:
            result = await self.scrape(url)
            if result.success and result.data:
                entry = cache_manager.create_from_result(result, url=url)
                cache_manager.save(entry)
                return result

        # Fall back to cache
        cache_entry = cache_manager.load(self.provider_name)
        if cache_entry:
            return cache_entry.to_scraper_result()

        # Return the last failure result
        return result
