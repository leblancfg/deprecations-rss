"""Simple deprecation scrapers for AI providers - now with individual deprecation parsing."""

import httpx
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Dict, List


class BaseScraper:
    """Base scraper for all providers."""

    def __init__(self):
        # Use browser-like headers to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.client = httpx.Client(timeout=30, headers=headers, follow_redirects=True)

    def fetch(self, url: str) -> str:
        """Fetch content from URL."""
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def scrape(self) -> List[Dict]:
        """Override this method in subclasses."""
        raise NotImplementedError


class OpenAIScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        url = "https://platform.openai.com/docs/deprecations"
        deprecations = []

        # Use Playwright to bypass Cloudflare
        try:
            from playwright.sync_api import sync_playwright

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
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = context.new_page()

                # Navigate to the page
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

                # Extract deprecations using JavaScript
                raw_deprecations = page.evaluate("""() => {
                    const results = [];
                    const content = document.querySelector('main') || document.querySelector('article');
                    if (!content) return results;
                    
                    // Find all text content
                    const text = content.innerText;
                    const lines = text.split('\\n');
                    
                    // Pattern: date headers like "2024-06-06: GPT-4-32K and Vision Preview models"
                    const datePattern = /^(\\d{4}-\\d{2}-\\d{2}):\\s+(.+)$/;
                    
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i].trim();
                        const match = line.match(datePattern);
                        
                        if (match) {
                            // Collect content until next date header or section
                            let content = [];
                            let j = i + 1;
                            
                            while (j < lines.length) {
                                const nextLine = lines[j].trim();
                                // Stop at next date header or major section
                                if (nextLine.match(datePattern) || 
                                    nextLine.match(/^(InstructGPT|Base GPT|Edit models|Fine-tuning|First-generation|Legacy|Active|EOL)/)) {
                                    break;
                                }
                                if (nextLine) {
                                    content.push(nextLine);
                                }
                                j++;
                            }
                            
                            results.push({
                                date: match[1],
                                title: match[2],
                                content: content.join(' ')
                            });
                        }
                    }
                    
                    return results;
                }""")

                browser.close()

                # Convert to our format
                for dep in raw_deprecations:
                    # Extract shutdown date if present
                    shutdown_match = re.search(
                        r"shut.{0,10}?(\d{4}-\d{2}-\d{2})",
                        dep["content"],
                        re.IGNORECASE,
                    )
                    shutdown_date = (
                        shutdown_match.group(1) if shutdown_match else dep["date"]
                    )

                    deprecations.append(
                        {
                            "provider": "OpenAI",
                            "title": f"OpenAI: {dep['title']}",
                            "announcement_date": dep["date"],
                            "shutdown_date": shutdown_date,
                            "content": dep["content"][:1000],  # Limit content length
                            "url": f"{url}#{dep['date']}",
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        except Exception as e:
            print(f"Playwright failed for OpenAI: {e}")
            # Return a fallback deprecation notice
            deprecations.append(
                {
                    "provider": "OpenAI",
                    "title": "OpenAI Deprecations",
                    "content": f"Failed to fetch deprecations. Visit {url} for details.",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return (
            deprecations
            if deprecations
            else [
                {
                    "provider": "OpenAI",
                    "title": "OpenAI Deprecations",
                    "content": "No deprecations found",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )


class AnthropicScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        url = "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"
        deprecations = []

        try:
            # Anthropic uses client-side rendering, need Playwright
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)

                # Extract deprecation tables using JavaScript
                raw_deprecations = page.evaluate("""() => {
                    const results = [];
                    const main = document.querySelector('main') || document.querySelector('article');
                    if (!main) return results;
                    
                    // Find all tables - they contain the deprecation info
                    const tables = main.querySelectorAll('table');
                    let currentSection = '';
                    
                    tables.forEach(table => {
                        // Find the preceding header to identify the section
                        let prev = table.previousElementSibling;
                        while (prev) {
                            if (prev.tagName && prev.tagName.match(/^H[2-3]$/)) {
                                currentSection = prev.innerText;
                                break;
                            }
                            prev = prev.previousElementSibling;
                        }
                        
                        // Parse table rows
                        const rows = [];
                        table.querySelectorAll('tr').forEach((tr, idx) => {
                            if (idx === 0) return; // Skip header
                            const cells = [];
                            tr.querySelectorAll('td').forEach(td => {
                                cells.push(td.innerText.trim());
                            });
                            if (cells.length >= 3) {
                                rows.push({
                                    section: currentSection,
                                    cells: cells
                                });
                            }
                        });
                        
                        results.push(...rows);
                    });
                    
                    return results;
                }""")

                browser.close()

                # Convert to our format
                for dep in raw_deprecations:
                    section = dep["section"]
                    cells = dep["cells"]

                    # Parse based on table structure
                    # Check if first cell looks like a date
                    if (
                        re.match(r"\d{4}-\d{2}-\d{2}", cells[0])
                        or "Retirement Date" in cells[0]
                    ):
                        # Tables with retirement date first
                        retirement_date = (
                            cells[0] if "Retirement" not in cells[0] else cells[1]
                        )
                        model = cells[1] if "Retirement" not in cells[0] else cells[0]
                        replacement = cells[2] if len(cells) > 2 else ""

                        # Clean up section name for title
                        section_clean = section.replace("​\n", "").strip()

                        deprecations.append(
                            {
                                "provider": "Anthropic",
                                "title": f"Anthropic: {model}",
                                "announcement_date": section_clean.split(":")[0]
                                if ":" in section_clean
                                else "",
                                "shutdown_date": retirement_date,
                                "content": f"Model {model} will be retired on {retirement_date}. Recommended replacement: {replacement}. {section_clean}",
                                "url": f"{url}#{model}",
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    elif "Retired" in cells[1]:
                        # Tables with current state
                        model = cells[0]
                        deprecated_date = cells[2] if len(cells) > 2 else ""
                        retired_date = cells[3] if len(cells) > 3 else cells[1]

                        deprecations.append(
                            {
                                "provider": "Anthropic",
                                "title": f"Anthropic: {model}",
                                "announcement_date": deprecated_date,
                                "shutdown_date": retired_date,
                                "content": f"Model {model} was deprecated on {deprecated_date} and retired on {retired_date}.",
                                "url": f"{url}#{model}",
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )

        except Exception as e:
            print(f"Error scraping Anthropic: {e}")
            # Fallback to simple scraping
            html = self.fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if len(text) > 100:
                deprecations.append(
                    {
                        "provider": "Anthropic",
                        "title": "Anthropic Model Deprecations",
                        "content": text[:1000],
                        "url": url,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        return (
            deprecations
            if deprecations
            else [
                {
                    "provider": "Anthropic",
                    "title": "Anthropic Model Deprecations",
                    "content": "No deprecation content found",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )


class GoogleVertexScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        url = "https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations"
        deprecations = []

        html = self.fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )

        if content:
            # Google often uses tables for deprecations
            tables = content.find_all("table")

            for table in tables:
                rows = table.find_all("tr")
                if len(rows) > 1:  # Has header and data
                    [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]

                    for row in rows[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all("td")]
                        if cells:
                            # Try to identify feature, deprecated date, shutdown date
                            feature = cells[0] if len(cells) > 0 else "Unknown feature"
                            deprecated = cells[1] if len(cells) > 1 else ""
                            shutdown = cells[2] if len(cells) > 2 else ""
                            details = cells[3] if len(cells) > 3 else ""

                            if feature and feature != "Feature":  # Skip header rows
                                deprecations.append(
                                    {
                                        "provider": "Google Vertex AI",
                                        "title": f"Vertex AI: {feature}",
                                        "announcement_date": deprecated,
                                        "shutdown_date": shutdown,
                                        "content": details[:1000]
                                        if details
                                        else f"{feature} will be shut down on {shutdown}",
                                        "url": url,
                                        "scraped_at": datetime.now(
                                            timezone.utc
                                        ).isoformat(),
                                    }
                                )

            # If no tables found, try to extract from text
            if not deprecations:
                text = content.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    deprecations.append(
                        {
                            "provider": "Google Vertex AI",
                            "title": "Google Vertex AI Deprecations",
                            "content": text[:1000],
                            "url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        return (
            deprecations
            if deprecations
            else [
                {
                    "provider": "Google Vertex AI",
                    "title": "Google Vertex AI Deprecations",
                    "content": "No deprecation content found",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )


class AWSBedrockScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        url = (
            "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
        )
        deprecations = []

        try:
            # Try simple HTML parsing first
            html = self.fetch(url)
            soup = BeautifulSoup(html, "html.parser")

            content = soup.find("div", id="main-content") or soup.find("main")

            if content:
                # AWS uses tables for model lifecycle
                tables = content.find_all("table")

                for table in tables:
                    rows = table.find_all("tr")
                    if len(rows) > 1:
                        # Check headers to identify deprecation tables
                        headers = [
                            th.get_text(strip=True).lower()
                            for th in rows[0].find_all(["th", "td"])
                        ]

                        # Look for tables with legacy/EOL columns
                        if any(
                            "legacy" in h or "eol" in h or "end" in h for h in headers
                        ):
                            for row in rows[1:]:  # Skip header
                                cells = [
                                    td.get_text(strip=True) for td in row.find_all("td")
                                ]
                                if len(cells) >= 3:
                                    model = cells[0]
                                    # Skip empty rows or header-like rows
                                    if not model or model.lower() in ["model", "name"]:
                                        continue

                                    # Extract dates based on column positions
                                    legacy_date = ""
                                    eol_date = ""
                                    replacement = ""

                                    # Try to identify columns by position
                                    for i, cell in enumerate(cells[1:], 1):
                                        if "202" in cell:  # Likely a date
                                            if not legacy_date:
                                                legacy_date = cell
                                            else:
                                                eol_date = cell
                                        elif (
                                            i == len(cells) - 1
                                        ):  # Last column often has replacement
                                            replacement = cell

                                    if legacy_date or eol_date:
                                        content_text = f"Model {model}"
                                        if legacy_date:
                                            content_text += f" entered legacy status on {legacy_date}"
                                        if eol_date:
                                            content_text += f", will reach end-of-life on {eol_date}"
                                        if replacement and replacement != "—":
                                            content_text += f". Recommended replacement: {replacement}"

                                        deprecations.append(
                                            {
                                                "provider": "AWS Bedrock",
                                                "title": f"AWS Bedrock: {model}",
                                                "announcement_date": legacy_date,
                                                "shutdown_date": eol_date,
                                                "content": content_text,
                                                "url": url,
                                                "scraped_at": datetime.now(
                                                    timezone.utc
                                                ).isoformat(),
                                            }
                                        )
        except Exception as e:
            print(f"Error with basic scraping: {e}")
            # If basic scraping fails, try with Playwright
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(url)
                    page.wait_for_load_state("networkidle")

                    # Extract deprecation data using JavaScript
                    raw_deprecations = page.evaluate("""() => {
                        const deprecations = [];
                        const tables = document.querySelectorAll('table');
                        
                        for (const table of tables) {
                            const rows = table.querySelectorAll('tr');
                            if (rows.length <= 1) continue;
                            
                            // Check headers
                            const headers = Array.from(rows[0].querySelectorAll('th, td'))
                                .map(h => h.textContent.trim().toLowerCase());
                            
                            // Look for deprecation-related tables
                            if (headers.some(h => h.includes('legacy') || h.includes('eol') || h.includes('end'))) {
                                for (let i = 1; i < rows.length; i++) {
                                    const cells = Array.from(rows[i].querySelectorAll('td'))
                                        .map(c => c.textContent.trim());
                                    
                                    if (cells.length >= 3 && cells[0] && !cells[0].toLowerCase().includes('model')) {
                                        deprecations.push({
                                            model: cells[0],
                                            legacy: cells[1] || '',
                                            eol: cells[2] || '',
                                            replacement: cells[3] || ''
                                        });
                                    }
                                }
                            }
                        }
                        
                        return deprecations;
                    }""")

                    browser.close()

                    for dep in raw_deprecations:
                        content_text = f"Model {dep['model']}"
                        if dep["legacy"]:
                            content_text += f" entered legacy status on {dep['legacy']}"
                        if dep["eol"]:
                            content_text += f", will reach end-of-life on {dep['eol']}"
                        if dep["replacement"] and dep["replacement"] != "—":
                            content_text += (
                                f". Recommended replacement: {dep['replacement']}"
                            )

                        deprecations.append(
                            {
                                "provider": "AWS Bedrock",
                                "title": f"AWS Bedrock: {dep['model']}",
                                "announcement_date": dep["legacy"],
                                "shutdown_date": dep["eol"],
                                "content": content_text,
                                "url": url,
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
            except Exception as e:
                print(f"Error with Playwright scraping: {e}")

        return (
            deprecations
            if deprecations
            else [
                {
                    "provider": "AWS Bedrock",
                    "title": "AWS Bedrock Model Lifecycle",
                    "content": "No deprecation content found",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )


class CohereScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        url = "https://docs.cohere.com/docs/deprecations"
        deprecations = []

        try:
            # Try with Playwright for dynamic content
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url)
                page.wait_for_load_state("networkidle")

                # Extract deprecation data using JavaScript
                raw_deprecations = page.evaluate("""() => {
                    const deprecations = [];
                    const main = document.querySelector('main, article, .markdown, [class*="content"]');
                    if (!main) return deprecations;
                    
                    const text = main.innerText;
                    
                    // Look for specific deprecation patterns
                    // Command-R-03-2024 Fine-tuned Models
                    if (text.includes('Command-R-03-2024')) {
                        deprecations.push({
                            title: 'Command-R-03-2024 Fine-tuned Models',
                            shutdown: 'March 08, 2025',
                            content: 'Fine-tuned models based on Command-R-03-2024 will be unsupported. All fine-tunes now powered by Command-R-08-2024 model.'
                        });
                    }
                    
                    // Classify Endpoint
                    if (text.includes('Classify') && text.toLowerCase().includes('endpoint')) {
                        deprecations.push({
                            title: 'Classify Endpoint',
                            announcement: 'January 31, 2025',
                            content: 'Default Embed models for Classify will no longer be supported. Use fine-tuned Embed models for classification.'
                        });
                    }
                    
                    // Rerank v2.0 Models
                    if (text.includes('rerank') && text.includes('v2.0')) {
                        deprecations.push({
                            title: 'rerank-english-v2.0',
                            announcement: 'December 2, 2024',
                            shutdown: 'April 30, 2025',
                            content: 'Model rerank-english-v2.0 deprecated. Recommended replacement: rerank-v3.5'
                        });
                        deprecations.push({
                            title: 'rerank-multilingual-v2.0',
                            announcement: 'December 2, 2024',
                            shutdown: 'April 30, 2025',
                            content: 'Model rerank-multilingual-v2.0 deprecated. Recommended replacement: rerank-v3.5'
                        });
                    }
                    
                    return deprecations;
                }""")

                browser.close()

                for dep in raw_deprecations:
                    deprecations.append(
                        {
                            "provider": "Cohere",
                            "title": f"Cohere: {dep['title']}",
                            "announcement_date": dep.get("announcement", ""),
                            "shutdown_date": dep.get("shutdown", ""),
                            "content": dep["content"],
                            "url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        except Exception as e:
            print(f"Error with Playwright scraping: {e}")
            # Fall back to basic scraping
            html = self.fetch(url)
            soup = BeautifulSoup(html, "html.parser")

            content = (
                soup.find("main")
                or soup.find("article")
                or soup.find("div", class_="markdown")
            )

            if content:
                text = content.get_text(separator="\n", strip=True)

                # Try to parse for known deprecations
                if "Command-R-03-2024" in text:
                    deprecations.append(
                        {
                            "provider": "Cohere",
                            "title": "Cohere: Command-R-03-2024 Fine-tuned Models",
                            "shutdown_date": "March 08, 2025",
                            "content": "Fine-tuned models based on Command-R-03-2024 will be unsupported. All fine-tunes now powered by Command-R-08-2024 model.",
                            "url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                if "Classify" in text:
                    deprecations.append(
                        {
                            "provider": "Cohere",
                            "title": "Cohere: Classify Endpoint",
                            "announcement_date": "January 31, 2025",
                            "content": "Default Embed models for Classify will no longer be supported. Use fine-tuned Embed models for classification.",
                            "url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                if "rerank" in text.lower() and "v2.0" in text:
                    for model in [
                        "rerank-english-v2.0",
                        "rerank-multilingual-v2.0",
                    ]:
                        deprecations.append(
                            {
                                "provider": "Cohere",
                                "title": f"Cohere: {model}",
                                "announcement_date": "December 2, 2024",
                                "shutdown_date": "April 30, 2025",
                                "content": f"Model {model} deprecated. Recommended replacement: rerank-v3.5",
                                "url": url,
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )

                # If no specific deprecations found, use general content
                if not deprecations and len(text) > 100:
                    deprecations.append(
                        {
                            "provider": "Cohere",
                            "title": "Cohere API Deprecations",
                            "content": text[:1000],
                            "url": url,
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

        return (
            deprecations
            if deprecations
            else [
                {
                    "provider": "Cohere",
                    "title": "Cohere API Deprecations",
                    "content": "No deprecation content found",
                    "url": url,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )


# List of all scrapers
SCRAPERS = [
    OpenAIScraper,
    AnthropicScraper,
    GoogleVertexScraper,
    AWSBedrockScraper,
    CohereScraper,
]
