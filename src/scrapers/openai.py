"""OpenAI deprecations scraper implementation."""

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.models.deprecation import Deprecation
from src.scrapers.base import BaseScraper

try:
    from playwright.async_api import async_playwright  # type: ignore[import-not-found]
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI model deprecations."""

    def __init__(self) -> None:
        """Initialize the OpenAI scraper."""
        super().__init__("https://platform.openai.com/docs/deprecations")

    async def scrape_api(self) -> dict[str, Any]:
        """Scrape deprecations using OpenAI API if available."""
        try:
            # Try to fetch from a potential API endpoint
            # OpenAI might have a structured API for deprecations
            api_url = "https://platform.openai.com/api/deprecations"
            response = await self._make_request(api_url)

            deprecations = []
            for item in response.get("deprecations", []):
                try:
                    dep = self._parse_api_deprecation(item)
                    if dep:
                        deprecations.append(dep)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse API deprecation: {e}")
                    continue

            # Remove duplicates
            unique_deprecations = list({dep.get_hash(): dep for dep in deprecations}.values())
            return {"deprecations": unique_deprecations}

        except Exception as e:
            logger.error(f"API scraping failed: {e}")
            raise

    async def scrape_html(self) -> dict[str, Any]:
        """Scrape deprecations by parsing HTML content."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    headers={
                        "User-Agent": self.config.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    },
                    timeout=self.config.timeout,
                    follow_redirects=True
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            deprecations = self._parse_html_deprecations(soup)

            # Remove duplicates
            unique_deprecations = list({dep.get_hash(): dep for dep in deprecations}.values())
            return {"deprecations": unique_deprecations}

        except Exception as e:
            logger.error(f"HTML scraping failed: {e}")
            raise

    async def scrape_playwright(self) -> dict[str, Any]:
        """Scrape deprecations using Playwright for JavaScript-rendered content."""
        if not HAS_PLAYWRIGHT:
            raise ImportError("Playwright is not installed. Install with: pip install playwright")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Set realistic user agent
                await page.set_extra_http_headers({
                    "User-Agent": self.config.user_agent,
                    "Accept-Language": "en-US,en;q=0.9"
                })

                # Navigate to the page
                await page.goto(self.url, wait_until="networkidle")

                # Wait for content to load
                await page.wait_for_load_state("domcontentloaded")

                # Get the rendered HTML
                content = await page.content()
                await browser.close()

            soup = BeautifulSoup(content, "html.parser")
            deprecations = self._parse_html_deprecations(soup)

            # Remove duplicates
            unique_deprecations = list({dep.get_hash(): dep for dep in deprecations}.values())
            return {"deprecations": unique_deprecations}

        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}")
            raise

    def _parse_api_deprecation(self, item: dict[str, Any]) -> Deprecation | None:
        """Parse a single deprecation from API response."""
        try:
            model = item.get("model")
            if not model:
                return None

            deprecation_date = self._parse_date(item.get("deprecation_date"))
            retirement_date = self._parse_date(
                item.get("shutdown_date") or item.get("retirement_date")
            )

            if not deprecation_date or not retirement_date:
                return None

            # Handle invalid date ordering
            if retirement_date <= deprecation_date:
                logger.warning(f"Invalid date ordering for {model}, skipping")
                return None

            return Deprecation(
                provider="OpenAI",
                model=model,
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                replacement=item.get("replacement"),
                notes=item.get("notes"),
                source_url=self.url  # type: ignore[arg-type]
            )

        except Exception as e:
            logger.warning(f"Failed to parse API deprecation: {e}")
            return None

    def _parse_html_deprecations(self, soup: BeautifulSoup) -> list[Deprecation]:
        """Parse deprecations from HTML content."""
        deprecations = []

        # Try multiple selector strategies
        selectors = [
            "div.model-deprecation",
            "div.deprecation",
            "section.deprecation",
            "article.deprecation",
            "[class*='deprecation']",
            "div[data-deprecation]"
        ]

        deprecation_blocks: list[Any] = []
        for selector in selectors:
            found = soup.select(selector)
            if found:
                deprecation_blocks.extend(found)

        # If no blocks found with class selectors, look for structure patterns
        if not deprecation_blocks:
            # Look for divs that contain model information
            for div in soup.find_all('div'):
                if self._contains_deprecation_info(div):
                    deprecation_blocks.append(div)

        # Parse each block
        seen_models = set()
        for block in deprecation_blocks:
            dep = self._parse_deprecation_block(block)
            if dep and dep.model not in seen_models:
                deprecations.append(dep)
                seen_models.add(dep.model)

        return deprecations

    def _find_deprecation_blocks(self, soup: BeautifulSoup) -> list[Any]:
        """Find deprecation blocks by text patterns."""
        blocks = []

        # Look for headings that might indicate models
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            text = heading.get_text().strip()

            # Check if this looks like a model name
            if any(pattern in text.lower() for pattern in ["gpt", "turbo", "davinci", "embedding", "moderation"]):
                # Get the parent or next sibling that might contain deprecation info
                parent = heading.parent
                if parent and self._contains_deprecation_info(parent):
                    blocks.append(parent)

                # Check next siblings
                for sibling in heading.find_next_siblings():
                    if self._contains_deprecation_info(sibling):
                        blocks.append(sibling)
                        break

        # Look for divs/sections that contain deprecation keywords
        for tag in soup.find_all(["div", "section", "article"]):
            if self._contains_deprecation_info(tag):
                blocks.append(tag)

        return blocks

    def _contains_deprecation_info(self, element: Any) -> bool:
        """Check if an element contains deprecation information."""
        if not element:
            return False

        text = element.get_text().lower()
        required_keywords = ["deprecat", "shutdown", "retire", "sunset", "end of life"]
        date_patterns = [r"\d{4}", r"january|february|march|april|may|june|july|august|september|october|november|december"]

        has_keyword = any(keyword in text for keyword in required_keywords)
        has_date = any(re.search(pattern, text, re.IGNORECASE) for pattern in date_patterns)

        return has_keyword and has_date

    def _parse_deprecation_block(self, block: Any) -> Deprecation | None:
        """Parse a single deprecation block from HTML."""
        try:
            text = block.get_text()

            # Extract model name more carefully
            model = self._extract_model_name(text)
            if not model:
                # Try to find model in specific tags
                model_elem = block.find(text=re.compile(r'Model:', re.IGNORECASE))
                if model_elem:
                    model = self._extract_model_name(model_elem.parent.get_text())

                if not model:
                    # Try h3 tags which often contain model names
                    h3 = block.find('h3')
                    if h3:
                        model = self._extract_model_name(h3.get_text())

                if not model:
                    return None

            # Extract dates
            deprecation_date = self._extract_date(text, ["deprecation", "deprecated", "announce"])
            retirement_date = self._extract_date(text, ["shutdown", "retire", "sunset", "end", "stop"])

            if not deprecation_date or not retirement_date:
                # Try alternative date extraction
                dates = self._extract_all_dates(text)
                if len(dates) >= 2:
                    deprecation_date = dates[0]
                    retirement_date = dates[1]
                else:
                    return None

            # Handle invalid date ordering
            if retirement_date <= deprecation_date:
                # Try swapping if they're in wrong order
                deprecation_date, retirement_date = retirement_date, deprecation_date
                if retirement_date <= deprecation_date:
                    return None

            # Extract replacement
            replacement = self._extract_replacement(text)

            # Extract notes
            notes = self._extract_notes(text)

            return Deprecation(
                provider="OpenAI",
                model=model,
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                replacement=replacement,
                notes=notes,
                source_url=self.url  # type: ignore[arg-type]
            )

        except Exception as e:
            logger.warning(f"Failed to parse deprecation block: {e}")
            return None

    def _extract_model_name(self, text: str) -> str | None:
        """Extract model name from text."""
        # First try to find explicit model field
        model_match = re.search(r"Model:\s*([a-z0-9-_.]+)", text, re.IGNORECASE)
        if model_match:
            return model_match.group(1).lower()

        # Common OpenAI model patterns
        patterns = [
            r"(gpt-[0-9.]+-turbo(?:-\d+)?)",
            r"(gpt-4(?:-\d+)?)",
            r"(gpt-3\.5(?:-turbo)?(?:-\d+)?)",
            r"(text-davinci-\d+)",
            r"(text-curie-\d+)",
            r"(text-babbage-\d+)",
            r"(text-ada-\d+)",
            r"(code-davinci-\d+)",
            r"(text-embedding-[a-z]+-\d+(?:-v\d+)?)",
            r"(text-moderation-[a-z]+)",
            r"([a-z]+-[a-z]+-\d+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                model_name = match.group(1).lower()
                # Skip generic patterns if they don't look like model names
                if "-" in model_name and len(model_name) > 5:
                    return model_name

        # Try extracting from heading text (like "GPT-3.5 Turbo 0301")
        heading_patterns = [
            r"GPT-3\.5 Turbo (\d+)",
            r"GPT-4 (\d+)",
            r"Text Davinci (\d+)",
        ]

        for pattern in heading_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if "turbo" in pattern.lower():
                    return f"gpt-3.5-turbo-{match.group(1)}"
                elif "gpt-4" in pattern.lower():
                    return f"gpt-4-{match.group(1)}"
                elif "davinci" in pattern.lower():
                    return f"text-davinci-{match.group(1)}"

        return None

    def _extract_date(self, text: str, keywords: list[str]) -> datetime | None:
        """Extract date associated with specific keywords."""
        for keyword in keywords:
            # Look for date near keyword - match until newline or next field
            pattern = rf"{keyword}[^:]*:\s*([^\n]+?)(?:\n|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                date_str = match.group(1).strip()
                # Clean up the date string - remove trailing punctuation
                date_str = date_str.rstrip('.,;')
                date = self._parse_date(date_str)
                if date:
                    return date

        return None

    def _extract_all_dates(self, text: str) -> list[datetime]:
        """Extract all dates from text."""
        dates = []

        # Various date patterns
        patterns = [
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
            r"\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
            r"\d{4}-\d{2}-\d{2}",
            r"\d{2}/\d{2}/\d{4}",
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match if isinstance(match, str) else " ".join(match)
                date = self._parse_date(date_str)
                if date:
                    dates.append(date)

        # Sort dates chronologically
        dates.sort()
        return dates

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse various date formats."""
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try different date formats
        formats = [
            "%Y-%m-%d",
            "%B %d, %Y",
            "%B %d %Y",
            "%d %B %Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%B %Y",
            "%Y/%m/%d"
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If only month and year, default to first day
                if fmt == "%B %Y":
                    dt = dt.replace(day=1)
                return dt.replace(tzinfo=UTC)
            except ValueError:
                continue

        # Try parsing month-year format (e.g., "December 2023")
        month_year_match = re.match(r"(\w+)\s+(\d{4})", date_str)
        if month_year_match:
            try:
                month_str, year_str = month_year_match.groups()
                dt = datetime.strptime(f"{month_str} 1, {year_str}", "%B %d, %Y")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                pass

        return None

    def _extract_replacement(self, text: str) -> str | None:
        """Extract replacement model from text."""
        patterns = [
            r"(?:recommended\s+)?replacement[:\s]+([a-z0-9-_.]+(?:\s+or\s+later)?)",
            r"(?:migrate|upgrade|switch)\s+to[:\s]+([a-z0-9-_.]+(?:\s+or\s+later)?)",
            r"alternative[:\s]+([a-z0-9-_.]+(?:\s+or\s+later)?)",
            r"use[:\s]+([a-z0-9-_.]+(?:\s+or\s+later)?)\s+instead"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _extract_notes(self, text: str) -> str | None:
        """Extract additional notes from text."""
        patterns = [
            r"note[:\s]+([^.]+)",
            r"(?:this\s+is\s+a\s+)([^.]+model)",
            r"additional\s+info[:\s]+([^.]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                note = match.group(1).strip()
                # Clean up the note
                if len(note) < 200:  # Reasonable note length
                    return note

        return None
