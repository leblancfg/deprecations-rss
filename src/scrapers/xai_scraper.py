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
                            page.wait_for_timeout(3000)  # Wait for content to load
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
        """Extract deprecations from xAI's models page pricing table."""
        items = []
        soup = BeautifulSoup(html, "html.parser")
        
        # These are the 7 deprecated models that appear after clicking "Show deprecated models"
        # They appear grayed out in the pricing table
        deprecated_models = [
            "grok-3-fastus-east-1",
            "grok-3-fasteu-west-1", 
            "grok-3-mini-fast",
            "grok-2-vision-1212us-east-1",
            "grok-2-1212us-east-1",
            "grok-2-vision-1212eu-west-1",
            "grok-2-1212eu-west-1"
        ]
        
        # Find the pricing table
        table = soup.find("table")
        if not table:
            return items
            
        # Look through all table rows for model names
        rows = table.find_all("tr")
        
        for row in rows:
            cells = row.find_all(["td", "th"])
            if cells and len(cells) > 0:
                first_cell_text = cells[0].get_text(strip=True)
                
                # Check if this is one of our known deprecated models
                if first_cell_text in deprecated_models:
                    item = DeprecationItem(
                        provider=self.provider_name,
                        model_id=first_cell_text,
                        model_name=first_cell_text,
                        announcement_date="",  # xAI doesn't provide announcement dates
                        shutdown_date="",  # xAI doesn't provide shutdown dates
                        replacement_model=None,
                        deprecation_context=f"Model {first_cell_text} is deprecated",
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
