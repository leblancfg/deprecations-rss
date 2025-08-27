"""OpenAI deprecations scraper with individual model extraction."""

import re
import json
import os
from typing import List, Any
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class OpenAIScraper(EnhancedBaseScraper):
    """Scraper for OpenAI deprecations page.

    KNOWN ISSUE: As of August 2025, OpenAI has implemented Cloudflare protection
    that blocks automated access. This scraper attempts various bypass techniques
    but may return 0 results if blocked. Manual intervention or alternative
    data sources may be required.
    """

    provider_name = "OpenAI"
    url = "https://platform.openai.com/docs/deprecations"
    requires_playwright = True  # OpenAI uses Cloudflare protection

    def fetch_with_playwright(self, url: str) -> str:
        """Fetch content using Playwright with advanced stealth techniques.

        NOTE: OpenAI uses Cloudflare protection. This implementation tries various
        bypass techniques but may still be blocked.
        """
        from playwright.sync_api import sync_playwright
        import random

        with sync_playwright() as p:
            # Launch with stealth options
            browser = p.chromium.launch(
                headless=True,  # Change back to headless for CI/CD
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-web-security",
                    "--disable-features=CrossSiteDocumentBlockingAlways",
                    "--disable-features=CrossSiteDocumentBlockingIfIsolating",
                    "--enable-features=NetworkService,NetworkServiceInProcess",
                    "--allow-running-insecure-content",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--deterministic-fetch",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=Translate",
                    "--disable-ipc-flooding-protection",
                    "--password-store=basic",
                    "--use-mock-keychain",
                    "--disable-features=DialMediaRouteProvider",
                    "--disable-features=ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls,DestroyProfileOnBrowserClose,MediaRouter,CalculateNativeWinOcclusion,InterestFeedContentSuggestions,CertificateTransparencyComponentUpdater",
                    "--lang=en-US,en",
                ],
            )

            # Create context with realistic viewport and user agent
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                color_scheme="light",
                reduced_motion="no-preference",
                forced_colors="none",
            )

            page = context.new_page()

            # Add stealth scripts before navigation
            page.add_init_script("""
                // Overwrite the navigator.webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock plugins and mimeTypes
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"}, 
                         description: "Portable Document Format", 
                         filename: "internal-pdf-viewer", 
                         length: 1, 
                         name: "Chrome PDF Plugin"}
                    ],
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Remove automation indicators
                ['webdriver', '__driver_evaluate', '__webdriver_evaluate', '__selenium_evaluate', 
                 '__fxdriver_evaluate', '__driver_unwrapped', '__webdriver_unwrapped', 
                 '__selenium_unwrapped', '__fxdriver_unwrapped', '_Selenium_IDE_Recorder',
                 '__webdriver_script_function', '__webdriver_script_func', '__webdriver_script_fn',
                 '__fxdriver_script_fn', '__selenium_script_fn', '__webdriver_unwrapped'].forEach(prop => {
                    delete window[prop];
                    delete document[prop];
                });
            """)

            try:
                # Set extra headers
                page.set_extra_http_headers(
                    {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br, zstd",
                        "DNT": "1",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0",
                        "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"macOS"',
                    }
                )

                # Random delay before navigation
                page.wait_for_timeout(random.randint(1000, 3000))

                # Navigate with realistic behavior
                page.goto(url, wait_until="networkidle", timeout=60000)

                # Random human-like delay
                page.wait_for_timeout(random.randint(3000, 5000))

                # Simulate some mouse movement
                page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                page.wait_for_timeout(random.randint(500, 1000))

                # Check if we hit Cloudflare protection
                html = page.content()
                if "Just a moment..." in html or "challenge-platform" in html:
                    print(
                        "  → Detected Cloudflare protection, waiting for challenge..."
                    )
                    # Wait longer for potential challenge resolution
                    page.wait_for_timeout(30000)
                    html = page.content()

                # Try to find deprecation content
                try:
                    page.wait_for_selector("text=/\\d{4}-\\d{2}-\\d{2}/", timeout=10000)
                    print("  → Found date pattern in content")
                except Exception:
                    print("  → No deprecation dates found in page")
                    # Check if still on Cloudflare
                    if (
                        "cloudflare" in html.lower()
                        or "cf-browser-verification" in html
                    ):
                        print("  → Still blocked by Cloudflare protection")

            finally:
                # Clean up
                context.close()
                browser.close()

            return html

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from OpenAI's structured format.

        Returns empty list if blocked by Cloudflare protection.
        """
        # Check if we're blocked by Cloudflare
        if (
            "cloudflare" in html.lower()
            or "cf-browser-verification" in html
            or "challenge-platform" in html
        ):
            print("  → WARNING: OpenAI scraper blocked by Cloudflare protection")
            print("  → Using fallback data from last manual update")
            return self._load_fallback_data()

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

    def _load_fallback_data(self) -> List[DeprecationItem]:
        """Load fallback data when blocked by Cloudflare."""
        fallback_path = os.path.join(
            os.path.dirname(__file__), "openai_fallback_data.json"
        )

        if not os.path.exists(fallback_path):
            print("  → ERROR: Fallback data file not found")
            return []

        try:
            with open(fallback_path, "r") as f:
                data = json.load(f)

            items = []
            for dep in data.get("deprecations", []):
                item = DeprecationItem(
                    provider=self.provider_name,
                    model_id=dep["model_id"],
                    model_name=dep["model_name"],
                    announcement_date=dep["announcement_date"],
                    shutdown_date=dep["shutdown_date"],
                    replacement_model=dep.get("replacement_model"),
                    deprecation_context=dep.get("deprecation_context", ""),
                    url=dep["url"],
                )
                items.append(item)

            print(f"  → Loaded {len(items)} deprecations from fallback data")
            return items

        except Exception as e:
            print(f"  → ERROR loading fallback data: {e}")
            return []
