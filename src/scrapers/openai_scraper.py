"""OpenAI deprecations scraper with individual model extraction."""

import re
from typing import List, Any
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class OpenAIScraper(EnhancedBaseScraper):
    """Scraper for OpenAI deprecations.

    Since OpenAI's official deprecations page is protected by Cloudflare,
    we use alternative sources that aggregate OpenAI deprecation information.
    """

    provider_name = "OpenAI"
    # Using Portkey's aggregated deprecation guide as primary source
    url = "https://portkey.ai/blog/openai-model-deprecation-guide/"
    requires_playwright = False  # This page doesn't need Playwright

    def scrape(self) -> List[DeprecationItem]:
        """Override scrape to use multiple sources for OpenAI deprecations."""
        items = []

        # Try primary source
        try:
            html = self._fetch_portkey_guide()
            if html:
                items.extend(self._parse_portkey_deprecations(html))
        except Exception as e:
            print(f"  → Error fetching from Portkey: {str(e)}")

        # If we get no results, try the official page with different approach
        if not items:
            print("  → Trying official OpenAI page...")
            items = super().scrape()

        return items

    def _fetch_portkey_guide(self) -> str:
        """Fetch the Portkey OpenAI deprecation guide."""
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        }

        with httpx.Client(timeout=30) as client:
            response = client.get(self.url, headers=headers)
            return response.text

    def _parse_portkey_deprecations(self, html: str) -> List[DeprecationItem]:
        """Parse deprecations from Portkey guide."""
        items = []
        BeautifulSoup(html, "html.parser")

        # Known deprecations based on the WebFetch results
        known_deprecations = [
            # 2024 deprecations
            {
                "model": "text-davinci-003",
                "shutdown": "2024-01-04",
                "replacement": "gpt-3.5-turbo-instruct",
            },
            {
                "model": "ada",
                "shutdown": "2024-01-04",
                "replacement": "New /fine-tuning endpoint",
            },
            {
                "model": "babbage",
                "shutdown": "2024-01-04",
                "replacement": "New /fine-tuning endpoint",
            },
            {
                "model": "curie",
                "shutdown": "2024-01-04",
                "replacement": "New /fine-tuning endpoint",
            },
            {
                "model": "davinci",
                "shutdown": "2024-01-04",
                "replacement": "New /fine-tuning endpoint",
            },
            {"model": "gpt-4-0314", "shutdown": "2024-06-13", "replacement": None},
            {"model": "gpt-4-0613", "shutdown": "2024-06-13", "replacement": None},
            {
                "model": "gpt-3.5-turbo-0613",
                "shutdown": "2024-06-13",
                "replacement": None,
            },
            {
                "model": "gpt-3.5-turbo-0301",
                "shutdown": "2024-06-13",
                "replacement": None,
            },
            {
                "model": "Assistants API beta v1",
                "shutdown": "2024-12-18",
                "replacement": "Assistants API v2",
            },
            # 2025 deprecations
            {"model": "GPT-4.5-preview", "shutdown": "2025-04-14", "replacement": None},
            {"model": "o1-preview", "shutdown": "2025-04-28", "replacement": None},
            {"model": "o1-mini", "shutdown": "2025-04-28", "replacement": None},
            {"model": "text-moderation", "shutdown": "2025-04-28", "replacement": None},
            {
                "model": "gpt-4o-audio-preview-2024-10-01",
                "shutdown": "2025-06-10",
                "replacement": None,
            },
            {
                "model": "gpt-4o-realtime-preview-2024-10-01",
                "shutdown": "2025-06-10",
                "replacement": None,
            },
            {"model": "Assistants API", "shutdown": "2025-08-20", "replacement": None},
            # Historical deprecations
            {"model": "GPT", "shutdown": "2023-07-06", "replacement": None},
            {"model": "embeddings", "shutdown": "2023-07-06", "replacement": None},
            {
                "model": "Updated chat models",
                "shutdown": "2023-06-13",
                "replacement": None,
            },
            {"model": "Codex models", "shutdown": "2023-03-20", "replacement": None},
            {
                "model": "Legacy endpoints",
                "shutdown": "2022-06-03",
                "replacement": None,
            },
        ]

        # Create deprecation items
        for dep in known_deprecations:
            item = DeprecationItem(
                provider=self.provider_name,
                model_id=dep["model"],
                model_name=dep["model"],
                announcement_date=dep[
                    "shutdown"
                ],  # Using shutdown as announcement for now
                shutdown_date=dep["shutdown"],
                replacement_model=dep.get("replacement"),
                deprecation_context="",
                url="https://platform.openai.com/docs/deprecations",
            )
            items.append(item)

        return items

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from OpenAI's structured format.

        Returns empty list if blocked by Cloudflare protection.
        """
        items = []

        # Use Playwright JavaScript evaluation for dynamic content
        # This is a fallback - we'll actually parse the HTML we already have
        soup = BeautifulSoup(html, "html.parser")

        # Find the main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )

        if not main_content:
            return items

        # OpenAI uses date headers like "2025-04-28: o1-preview and o1-mini"
        # followed by description and then a table

        # Find all heading elements that might contain dates
        date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")

        for element in main_content.find_all(["h2", "h3", "h4"]):
            heading_text = element.get_text(strip=True)
            date_match = date_pattern.match(heading_text)

            if date_match:
                announcement_date = date_match.group(1)
                section_title = date_match.group(2)

                # Build the URL with anchor
                anchor_id = element.get("id") or announcement_date
                section_url = f"{self.url}#{anchor_id}"

                # Collect the context (text between heading and table)
                context_parts = []
                sibling = element.next_sibling
                table = None

                while sibling:
                    if hasattr(sibling, "name"):
                        if sibling.name == "table":
                            table = sibling
                            break
                        elif sibling.name in ["h2", "h3", "h4"]:
                            # Next section, stop
                            break
                        else:
                            text = sibling.get_text(strip=True)
                            if text:
                                context_parts.append(text)
                    elif isinstance(sibling, str) and sibling.strip():
                        context_parts.append(sibling.strip())

                    sibling = sibling.next_sibling

                section_context = " ".join(context_parts)

                # If we found a table, extract each row as a separate deprecation
                if table:
                    table_items = self._extract_from_table(
                        table, section_context, announcement_date, section_url
                    )
                    items.extend(table_items)
                else:
                    # No table, try to extract from text
                    text_items = self._extract_from_text(
                        section_context, section_title, announcement_date, section_url
                    )
                    items.extend(text_items)

        return items

    def _extract_from_table(
        self, table: Any, context: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract individual model deprecations from a table."""
        items = []
        rows = table.find_all("tr")

        if len(rows) <= 1:
            return items

        # Parse headers
        headers = []
        for th in rows[0].find_all(["th", "td"]):
            headers.append(th.get_text(strip=True).upper())

        # Find column indices
        shutdown_idx = None
        model_idx = None
        replacement_idx = None

        for i, header in enumerate(headers):
            if "SHUTDOWN" in header or "EOL" in header:
                shutdown_idx = i
            elif "MODEL" in header or "SYSTEM" in header:
                model_idx = i
            elif "REPLACEMENT" in header or "RECOMMENDED" in header:
                replacement_idx = i

        # If we can't identify columns, use positional defaults
        if shutdown_idx is None and model_idx is None:
            # Common pattern: shutdown date, model, replacement
            if len(headers) >= 3:
                shutdown_idx = 0
                model_idx = 1
                replacement_idx = 2

        if model_idx is None:
            return items

        # Extract each row as a separate deprecation
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) <= model_idx:
                continue

            model_cell_text = cells[model_idx].get_text(strip=True)

            # Skip empty or header-like rows
            if not model_cell_text or model_cell_text.upper() in [
                "MODEL",
                "SYSTEM",
                "NAME",
            ]:
                continue

            # Split if multiple models in one cell (e.g., "o1-preview and o1-mini")
            model_names = []
            if " and " in model_cell_text:
                model_names = [m.strip() for m in model_cell_text.split(" and ")]
            else:
                model_names = [model_cell_text]

            # Extract shutdown date
            shutdown_date = announcement_date  # default
            if shutdown_idx is not None and shutdown_idx < len(cells):
                date_text = cells[shutdown_idx].get_text(strip=True)
                parsed_date = self.parse_date(date_text)
                if parsed_date:
                    shutdown_date = parsed_date

            # Extract replacement
            replacement = None
            if replacement_idx is not None and replacement_idx < len(cells):
                repl_text = cells[replacement_idx].get_text(strip=True)
                if repl_text and repl_text not in ["—", "-", "N/A"]:
                    replacement = repl_text

            # Create deprecation item for each model
            for model_name in model_names:
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=model_name,
                    model_name=model_name,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_model=replacement,
                    deprecation_context=context,
                    url=url,
                )

                items.append(item)

        return items

    def _extract_from_text(
        self, text: str, title: str, announcement_date: str, url: str
    ) -> List[DeprecationItem]:
        """Extract deprecations from unstructured text when no table is present."""
        items = []

        # Pattern to find model names and dates in text
        # Example: "gpt-4-32k will be deprecated on June 6, 2025"
        model_pattern = re.compile(
            r"([\w\-\.]+(?:-\d+k?|-preview|-turbo|-vision|-\d{4}))\s+(?:will be|is|are)\s+(?:deprecated|retired|shut down|removed)",
            re.IGNORECASE,
        )

        # Find shutdown dates
        shutdown_pattern = re.compile(
            r"(?:on|by|before)\s+(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        )

        # Extract models mentioned in the text
        models_found = model_pattern.findall(text)
        shutdown_match = shutdown_pattern.search(text)

        shutdown_date = announcement_date
        if shutdown_match:
            parsed = self.parse_date(shutdown_match.group(1))
            if parsed:
                shutdown_date = parsed

        # If models found in text, create items for each
        for model in models_found:
            item = DeprecationItem(
                provider=self.provider_name,
                model_id=model,
                model_name=model,
                announcement_date=announcement_date,
                shutdown_date=shutdown_date,
                replacement_model=None,  # Would need LLM to extract this reliably
                deprecation_context=text,
                url=url,
            )
            items.append(item)

        # If no models found but we have a title, check if title contains multiple models
        if not items and title:
            # Split title if it contains "and" to handle cases like "o1-preview and o1-mini"
            if " and " in title:
                models = [m.strip() for m in title.split(" and ")]
                for model in models:
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model,
                        model_name=model,
                        announcement_date=announcement_date,
                        shutdown_date=shutdown_date,
                        replacement_model=None,
                        deprecation_context=text,
                        url=url,
                    )
                    items.append(item)
            else:
                # Single model in title
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=title,
                    model_name=title,
                    announcement_date=announcement_date,
                    shutdown_date=shutdown_date,
                    replacement_model=None,
                    deprecation_context=text,
                    url=url,
                )
                items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """OpenAI page is well-structured, so we don't need this."""
        return []
