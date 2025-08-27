"""xAI deprecations scraper with support for interactive deprecated models display."""

import re
from typing import List
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

                for selector in deprecated_selectors:
                    try:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click()
                            print(
                                f"  → Clicked deprecated models toggle using selector: {selector}"
                            )
                            page.wait_for_timeout(2000)  # Wait for content to load
                            break
                    except Exception:
                        continue

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

        # xAI currently doesn't have a dedicated deprecations page
        # Look for any explicit deprecation notices
        deprecation_keywords = [
            "deprecated",
            "legacy",
            "discontinued",
            "sunset",
            "end of life",
        ]

        for keyword in deprecation_keywords:
            # Find all elements containing deprecation keywords
            elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))

            for element in elements:
                parent = element.parent
                if not parent:
                    continue

                # Get surrounding context
                context = parent.get_text(strip=True)

                # Look for model names in the context (xAI pattern: grok-*)
                model_pattern = re.compile(r"\b(grok-[\w\-]+)\b", re.IGNORECASE)
                models = model_pattern.findall(context)

                for model in models:
                    # Try to extract dates
                    date_pattern = re.compile(
                        r"(?:on|by|before|after|starting|effective)\s+"
                        r"(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
                        re.IGNORECASE,
                    )
                    date_match = date_pattern.search(context)
                    shutdown_date = ""
                    if date_match:
                        shutdown_date = self.parse_date(date_match.group(1))

                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=model,
                        model_name=model,
                        announcement_date=shutdown_date,
                        shutdown_date=shutdown_date,
                        replacement_model=None,
                        deprecation_context=context[:500],
                        url=self.url,
                    )
                    items.append(item)

        # Deduplicate by model_id
        seen = set()
        unique_items = []
        for item in items:
            if item.model_id not in seen:
                seen.add(item.model_id)
                unique_items.append(item)

        return unique_items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """xAI page is expected to be structured, so minimal unstructured extraction."""
        return []
