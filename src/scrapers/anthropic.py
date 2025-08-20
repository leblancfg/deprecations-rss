"""Anthropic deprecations scraper."""

import json
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.scrapers.base import BaseScraper, ScraperResult


class AnthropicScraper(BaseScraper):
    """Scraper for Anthropic Claude model deprecations."""

    provider_name = "anthropic"
    base_url = "https://docs.anthropic.com/deprecations"
    expected_url_patterns = [
        r"https://docs\.anthropic\.com/deprecations.*",
        r"https://docs\.anthropic\.com/en/api/deprecations.*",
        r"https://api\.anthropic\.com/v1/models.*",
    ]

    # Additional URLs to check
    additional_urls = [
        "https://docs.anthropic.com/en/api/getting-started",
        "https://docs.anthropic.com/claude/docs/models-overview",
    ]

    async def extract_deprecations(self, content: str) -> list[dict[str, Any]]:
        """Extract deprecation information from HTML content.
        
        Args:
            content: HTML content from Anthropic docs
            
        Returns:
            List of deprecation dictionaries
        """
        deprecations = []
        soup = BeautifulSoup(content, "html.parser")

        # Extract from tables
        tables = soup.find_all("table")
        for table in tables:
            deprecations.extend(self._extract_from_table(table))

        # Extract from text notices
        deprecations.extend(self._extract_from_notices(soup))

        # Extract Claude-specific deprecations
        deprecations.extend(self._extract_claude_models(soup))

        # Extract API version changes
        deprecations.extend(self._extract_api_changes(soup))

        # Remove duplicates
        seen = set()
        unique_deprecations = []
        for dep in deprecations:
            key = dep.get("model") or dep.get("version") or dep.get("endpoint")
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

        # Find headers
        headers = []
        header_row = table.find("thead")
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]
        elif rows:
            headers = [cell.get_text(strip=True).lower() for cell in rows[0].find_all(["th", "td"])]
            rows = rows[1:]

        # Map headers
        header_map = {
            "model": ["model", "model name", "name", "id"],
            "status": ["status", "state"],
            "deprecation_date": ["deprecation date", "deprecated", "deprecation"],
            "retirement_date": ["end of life", "eol", "retirement date", "sunset", "shutdown"],
            "replacement": ["suggested alternative", "replacement", "migrate to", "alternative"],
        }

        # Process rows
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

                # Skip if status is "active"
                if header == "status" and value.lower() == "active":
                    break

                # Map to fields
                for field, variations in header_map.items():
                    if header in variations:
                        if field == "model":
                            value = self.normalize_model_name(value)
                        elif "date" in field:
                            value = self.normalize_date(value)
                        deprecation[field] = value
                        break

            # Only add if it's actually deprecated
            if deprecation and ("deprecation_date" in deprecation or "retirement_date" in deprecation):
                deprecations.append(deprecation)

        return deprecations

    def _extract_from_notices(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract deprecations from notice text."""
        deprecations = []
        text_content = soup.get_text()

        # Patterns for Claude models
        patterns = [
            r"(claude-[\w\-\.]+)\s+will be deprecated on\s+([^,\.]+)",
            r"(claude-[\w\-\.]+)\s+(?:will be |is )?(?:deprecated|retired|sunset) on\s+([^,\.]+)",
            r"(claude-[\w\-\.]+).*?(?:EOL|end of life) on\s+([^,\.]+)",
            r"(Claude\s+[\d\.]+)\s+(?:will be )?deprecated on\s+([^,\.]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                model = self.normalize_model_name(match.group(1))
                date = self.normalize_date(match.group(2))

                deprecation = {
                    "model": model,
                    "retirement_date": date
                }

                # Find replacement
                replacement = self._find_replacement(text_content, model)
                if replacement:
                    deprecation["replacement"] = replacement

                deprecations.append(deprecation)

        return deprecations

    def _extract_claude_models(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract Claude-specific model deprecations."""
        deprecations = []

        # Look for Claude model sections
        for heading in soup.find_all(["h2", "h3"]):
            heading_text = heading.get_text(strip=True).lower()

            if "claude" in heading_text:
                # Process the section
                sibling = heading.find_next_sibling()
                section_text = ""

                while sibling and sibling.name not in ["h2", "h3"]:
                    section_text += sibling.get_text(strip=True) + " "
                    sibling = sibling.find_next_sibling()

                # Extract model names
                model_pattern = r"(claude-[\w\-\.]+|Claude\s+[\d\.]+\s+[\w]+)"
                models = re.findall(model_pattern, section_text, re.IGNORECASE)

                for model in models:
                    normalized_model = self.normalize_model_name(model)

                    # Look for associated dates
                    date_patterns = [
                        rf"{re.escape(model)}.*?(\w+\s+\d+,?\s+\d{{4}})",
                        rf"{re.escape(model)}.*?(\d{{4}}-\d{{2}}-\d{{2}})",
                    ]

                    for date_pattern in date_patterns:
                        date_match = re.search(date_pattern, section_text, re.IGNORECASE)
                        if date_match:
                            deprecation = {
                                "model": normalized_model,
                                "retirement_date": self.normalize_date(date_match.group(1))
                            }

                            replacement = self._find_replacement(section_text, model)
                            if replacement:
                                deprecation["replacement"] = replacement

                            deprecations.append(deprecation)
                            break

        return deprecations

    def _extract_api_changes(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract API version and endpoint deprecations."""
        deprecations = []
        text_content = soup.get_text()

        # API version patterns
        version_patterns = [
            r"API\s+(v\d+)\s+will be (?:sunset|deprecated) on\s+([^,\.]+)",
            r"(?:Version|v)(\d+)\s+(?:API\s+)?will be (?:sunset|deprecated) on\s+([^,\.]+)",
        ]

        for pattern in version_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                deprecation = {
                    "type": "api_version",
                    "version": match.group(1),
                    "retirement_date": self.normalize_date(match.group(2))
                }

                # Look for replacement version
                replacement_match = re.search(
                    rf"{re.escape(match.group(1))}.*?(?:migrate to|use)\s+(v\d+)",
                    text_content,
                    re.IGNORECASE
                )
                if replacement_match:
                    deprecation["replacement"] = replacement_match.group(1)

                deprecations.append(deprecation)

        # Endpoint patterns
        endpoint_patterns = [
            r"(/[\w/]+)\s+endpoint is deprecated",
            r"The\s+(/[\w/]+)\s+(?:endpoint\s+)?(?:is|will be)\s+deprecated",
        ]

        for pattern in endpoint_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                deprecation = {
                    "type": "api_endpoint",
                    "endpoint": match.group(1)
                }

                # Look for replacement
                replacement_match = re.search(
                    rf"{re.escape(match.group(1))}.*?(?:use|migrate to)\s+(/[\w/]+)",
                    text_content,
                    re.IGNORECASE
                )
                if replacement_match:
                    deprecation["replacement"] = replacement_match.group(1)

                deprecations.append(deprecation)

        return deprecations

    def normalize_model_name(self, name: str) -> str:
        """Normalize Claude model names to consistent format.
        
        Args:
            name: Model name in various formats
            
        Returns:
            Normalized model name (lowercase with hyphens)
        """
        if not name:
            return ""

        name = name.strip()

        # Replace "Claude X.Y" with "claude-x.y"
        name = re.sub(r"Claude\s+(\d+(?:\.\d+)?)", r"claude-\1", name, flags=re.IGNORECASE)

        # Replace "Claude X Model" with "claude-x-model"
        name = re.sub(r"Claude\s+(\d+(?:\.\d+)?)\s+(\w+)", r"claude-\1-\2", name, flags=re.IGNORECASE)

        # Lowercase and replace spaces/underscores with hyphens
        name = name.lower().replace(" ", "-").replace("_", "-")

        # Remove duplicate hyphens
        name = re.sub(r"-+", "-", name)

        return name

    def normalize_date(self, date_str: str) -> str:
        """Normalize various date formats to ISO format.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            ISO formatted date (YYYY-MM-DD)
        """
        if not date_str:
            return ""

        date_str = date_str.strip()

        # Already ISO format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        # Remove common prefixes
        date_str = re.sub(r"^(?:on|by|before|after)\s+", "", date_str, flags=re.IGNORECASE)

        try:
            parsed = date_parser.parse(date_str)
            return parsed.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return date_str

    def _find_replacement(self, text: str, model: str) -> str | None:
        """Find replacement model mentioned near the deprecated model."""
        patterns = [
            rf"{re.escape(model)}.*?(?:migrate to|upgrade to|use)\s+(claude-[\w\-\.]+)",
            rf"{re.escape(model)}.*?(?:replaced by|replacement:?)\s+(claude-[\w\-\.]+)",
            rf"(claude-[\w\-\.]+)\s+replaces\s+{re.escape(model)}",
            r"Recommended:?\s+(?:Upgrade to\s+)?(claude-[\w\-\.]+|Claude\s+[\d\.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                replacement = match.group(1)
                if "claude" in replacement.lower():
                    return self.normalize_model_name(replacement)

        return None

    async def extract_api_deprecations(self, content: str) -> list[dict[str, Any]]:
        """Extract deprecations from API JSON response.
        
        Args:
            content: JSON content with deprecation info
            
        Returns:
            List of deprecation dictionaries
        """
        try:
            data = json.loads(content)
            deprecations = []

            # Extract model deprecations
            if "models" in data:
                for model in data["models"]:
                    if model.get("status") in ["deprecated", "legacy"]:
                        dep = {
                            "model": model["id"],
                        }

                        if model.get("deprecation_date"):
                            dep["deprecation_date"] = self.normalize_date(model["deprecation_date"])

                        if model.get("end_of_life"):
                            dep["retirement_date"] = self.normalize_date(model["end_of_life"])
                        elif model.get("sunset_date"):
                            dep["retirement_date"] = self.normalize_date(model["sunset_date"])

                        if model.get("replacement"):
                            dep["replacement"] = model["replacement"]

                        deprecations.append(dep)

            # Extract API version deprecations
            if "api_versions" in data:
                for version, info in data["api_versions"].items():
                    if info.get("status") == "deprecated":
                        dep = {
                            "type": "api_version",
                            "version": version,
                        }

                        if info.get("sunset_date"):
                            dep["retirement_date"] = self.normalize_date(info["sunset_date"])

                        if info.get("replacement"):
                            dep["replacement"] = info["replacement"]

                        deprecations.append(dep)

            return deprecations

        except json.JSONDecodeError:
            return []

    async def scrape_all_sources(self) -> ScraperResult:
        """Scrape from all known Anthropic documentation sources."""
        all_deprecations = []
        errors = []

        # Try primary URL
        result = await self.scrape()
        if result.success and result.data:
            all_deprecations.extend(result.data)
        elif result.error:
            errors.append(result.error)

        # Try additional URLs
        for url in self.additional_urls:
            result = await self.scrape(url)
            if result.success and result.data:
                # Avoid duplicates
                for dep in result.data:
                    if dep not in all_deprecations:
                        all_deprecations.append(dep)
            elif result.error:
                errors.append(result.error)

        if all_deprecations:
            return ScraperResult(
                success=True,
                provider=self.provider_name,
                data=all_deprecations,
                timestamp=datetime.now(),
            )
        else:
            return ScraperResult(
                success=False,
                provider=self.provider_name,
                error=errors[0] if errors else None,
                timestamp=datetime.now(),
            )
