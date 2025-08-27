"""xAI deprecations scraper with support for interactive deprecated models display."""

import re
from typing import List, Any
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class XAIScraper(EnhancedBaseScraper):
    """Scraper for xAI models page with deprecated models."""

    provider_name = "xAI"
    url = "https://docs.x.ai/docs/models"
    requires_playwright = True  # Requires interaction to show deprecated models

    def fetch_with_playwright(self, url: str) -> str:
        """Fetch content using Playwright with interaction to reveal deprecated models."""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.headers["User-Agent"],
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)  # Wait for initial content load

                # Look for "see deprecated models" link/button and click it
                deprecated_selectors = [
                    "text='see deprecated models'",
                    "text='See deprecated models'",
                    "text='Show deprecated models'",
                    "text='show deprecated models'",
                    "[data-testid*='deprecated']",
                    "[class*='deprecated']",
                    "button:has-text('deprecated')",
                    "a:has-text('deprecated')",
                ]

                clicked = False
                for selector in deprecated_selectors:
                    try:
                        if page.locator(selector).is_visible():
                            page.locator(selector).click()
                            page.wait_for_timeout(2000)  # Wait for content to load
                            clicked = True
                            print(
                                f"  → Clicked deprecated models toggle using selector: {selector}"
                            )
                            break
                    except Exception:
                        continue

                if not clicked:
                    print(
                        "  → Could not find deprecated models toggle, proceeding with static content"
                    )

                # Wait for any dynamic content to load
                page.wait_for_timeout(2000)
                html = page.content()

            finally:
                browser.close()

            return html

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from xAI's models page."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Look for tables containing model information
        tables = soup.find_all("table")

        for table in tables:
            # Check if this table contains model information
            headers = table.find("thead") or table.find("tr")
            if not headers:
                continue

            header_text = headers.get_text().lower()
            if "model" not in header_text:
                continue

            # Extract from this table
            table_items = self._extract_from_models_table(table)
            items.extend(table_items)

        # Also look for rows with deprecation indicators (circle with bar in left gutter)
        deprecated_rows = soup.find_all(
            lambda tag: tag.name == "tr" and self._has_deprecation_indicator(tag)
        )

        for row in deprecated_rows:
            row_items = self._extract_from_deprecated_row(row)
            items.extend(row_items)

        # Look for any text mentioning deprecated models
        deprecated_sections = soup.find_all(
            lambda tag: tag.name in ["div", "section", "p"]
            and "deprecat" in tag.get_text().lower()
        )

        for section in deprecated_sections:
            section_items = self._extract_from_deprecated_section(section)
            items.extend(section_items)

        return items

    def _has_deprecation_indicator(self, row_element) -> bool:
        """Check if a table row has a deprecation indicator."""
        # Look for visual indicators that might suggest deprecation
        row_classes = " ".join(row_element.get("class", []))

        # Check for deprecation-related classes
        deprecation_indicators = [
            "deprecated",
            "legacy",
            "discontinued",
            "sunset",
            "warning",
            "alert",
            "strikethrough",
        ]

        for indicator in deprecation_indicators:
            if indicator in row_classes.lower():
                return True

        # Look for styling that might indicate deprecation
        style = row_element.get("style", "")
        if any(
            style_hint in style.lower()
            for style_hint in ["line-through", "opacity", "disabled"]
        ):
            return True

        # Check for icons or symbols in the first cell (left gutter)
        first_cell = row_element.find("td")
        if first_cell:
            # Look for SVG icons, Unicode symbols, or specific classes
            if (
                first_cell.find("svg")
                or "⊖" in first_cell.get_text()
                or "⊝" in first_cell.get_text()
                or "🚫" in first_cell.get_text()
                or any(
                    cls in " ".join(first_cell.get("class", [])).lower()
                    for cls in ["icon", "deprecated", "warning"]
                )
            ):
                return True

        return False

    def _extract_from_models_table(self, table: Any) -> List[DeprecationItem]:
        """Extract model information from a standard models table."""
        items = []
        rows = table.find_all("tr")

        if len(rows) <= 1:
            return items

        # Parse headers to understand table structure
        headers = []
        header_row = rows[0]
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True).lower())

        # Find relevant column indices
        model_idx = None
        status_idx = None
        date_idx = None
        description_idx = None

        for i, header in enumerate(headers):
            if "model" in header or "name" in header:
                model_idx = i
            elif "status" in header or "state" in header:
                status_idx = i
            elif "date" in header or "deprecated" in header:
                date_idx = i
            elif "description" in header or "notes" in header:
                description_idx = i

        if model_idx is None:
            return items

        # Process each row
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= model_idx:
                continue

            model_name = cells[model_idx].get_text(strip=True)
            if not model_name or model_name.lower() in ["model", "name"]:
                continue

            # Check if this row indicates deprecation
            is_deprecated = self._has_deprecation_indicator(row)

            # Check status column for deprecation
            if not is_deprecated and status_idx is not None and status_idx < len(cells):
                status_text = cells[status_idx].get_text(strip=True).lower()
                if any(
                    dep_word in status_text
                    for dep_word in ["deprecat", "legacy", "discontinued"]
                ):
                    is_deprecated = True

            # Only process if deprecated
            if not is_deprecated:
                continue

            # Extract additional information
            deprecation_date = ""
            if date_idx is not None and date_idx < len(cells):
                date_text = cells[date_idx].get_text(strip=True)
                deprecation_date = self.parse_date(date_text)

            description = ""
            if description_idx is not None and description_idx < len(cells):
                description = cells[description_idx].get_text(strip=True)

            # Create deprecation item
            item = DeprecationItem(
                provider=self.provider_name,
                model_id=model_name,
                model_name=model_name,
                announcement_date=deprecation_date,
                shutdown_date=deprecation_date,
                replacement_model=None,  # Would need additional parsing
                deprecation_context=description,
                url=self.url,
            )

            items.append(item)

        return items

    def _extract_from_deprecated_row(self, row: Any) -> List[DeprecationItem]:
        """Extract model info from a row identified as having deprecation indicators."""
        items = []
        cells = row.find_all(["td", "th"])

        if not cells:
            return items

        # Try to find the model name in the cells
        for cell in cells:
            text = cell.get_text(strip=True)

            # Skip empty cells or cells with just symbols
            if not text or len(text) < 2:
                continue

            # Skip cells that are clearly not model names
            if text.lower() in ["status", "date", "description", "notes", "deprecated"]:
                continue

            # Look for model name patterns (containing letters, numbers, hyphens)
            if re.match(r"^[a-zA-Z][a-zA-Z0-9\-_\.]*$", text):
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=text,
                    model_name=text,
                    announcement_date="",
                    shutdown_date="",
                    replacement_model=None,
                    deprecation_context="Found in deprecated models section",
                    url=self.url,
                )
                items.append(item)
                break  # Take the first valid model name from the row

        return items

    def _extract_from_deprecated_section(self, section: Any) -> List[DeprecationItem]:
        """Extract model names from text sections mentioning deprecated models."""
        items = []
        text = section.get_text()

        # Look for model names in deprecation-related text
        model_pattern = re.compile(
            r"\b([a-z][a-z0-9\-_]*(?:-\d+)?(?:-preview|turbo|mini|large)?)\b"
        )

        # Only process if the text clearly mentions deprecation
        if not any(
            word in text.lower()
            for word in ["deprecat", "legacy", "discontinued", "sunset"]
        ):
            return items

        potential_models = model_pattern.findall(text.lower())

        # Filter out common words that aren't model names
        common_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "are",
            "was",
            "were",
            "been",
            "have",
            "has",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "must",
            "models",
            "model",
            "api",
            "docs",
            "documentation",
            "see",
            "more",
            "info",
            "information",
            "details",
            "page",
            "section",
            "text",
            "deprecated",
        }

        for model in potential_models:
            if model not in common_words and len(model) > 2:
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=model,
                    model_name=model,
                    announcement_date="",
                    shutdown_date="",
                    replacement_model=None,
                    deprecation_context=text[:200] + "..." if len(text) > 200 else text,
                    url=self.url,
                )
                items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecated models from unstructured content."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Look for any text mentioning specific deprecated models
        text_content = soup.get_text()

        # Common patterns for mentioning deprecated models
        deprecation_patterns = [
            r"(\w+(?:-\w+)*)\s+(?:is|has been|will be)\s+deprecat",
            r"deprecat(?:ed|ing)\s+(?:model[s]?)?\s*:?\s*(\w+(?:-\w+)*)",
            r"legacy\s+(?:model[s]?)?\s*:?\s*(\w+(?:-\w+)*)",
            r"discontinued\s+(?:model[s]?)?\s*:?\s*(\w+(?:-\w+)*)",
        ]

        for pattern in deprecation_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                model_name = match.group(1)
                if len(model_name) > 2:  # Filter out very short matches
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(text_content), match.end() + 100)
                    context = text_content[context_start:context_end].strip()

                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model_name,
                        model_name=model_name,
                        announcement_date="",
                        shutdown_date="",
                        replacement_model=None,
                        deprecation_context=context,
                        url=self.url,
                    )
                    items.append(item)

        return items
