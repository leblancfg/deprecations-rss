"""Simple deprecation scrapers for AI providers."""

import httpx
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
    
    def scrape(self) -> Dict:
        """Override this method in subclasses."""
        raise NotImplementedError


class OpenAIScraper(BaseScraper):
    def scrape(self) -> Dict:
        url = "https://platform.openai.com/docs/deprecations"
        content = "No deprecation content found"
        
        # Use Playwright to bypass Cloudflare
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                # Launch with more realistic browser settings
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                
                # Navigate to the page
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait a bit for any redirects or challenges
                page.wait_for_timeout(5000)
                
                # Try to find the content
                try:
                    # Wait for actual content, not Cloudflare challenge
                    page.wait_for_selector('main, article, .docs-content, div[class*="deprecat"]', timeout=10000)
                    
                    # Get the main content
                    main_content = page.query_selector('main') or page.query_selector('article') or page.query_selector('.docs-content')
                    
                    if main_content:
                        content = main_content.inner_text()
                except:
                    # If selectors fail, just get all text
                    content = page.inner_text('body')
                
                browser.close()
                
                if content and len(content) > 100:
                    return {
                        "provider": "OpenAI",
                        "url": url,
                        "content": content,
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    }
        except Exception as e:
            print(f"Playwright failed for OpenAI: {e}")
        
        # Fallback to basic scraping (will likely fail but worth trying)
        try:
            html = self.fetch(url)
            soup = BeautifulSoup(html, 'html.parser')
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='docs-content')
            
            if main_content:
                content = main_content.get_text(separator='\n', strip=True)
        except:
            pass
        
        return {
            "provider": "OpenAI",
            "url": url,
            "content": content,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }


class AnthropicScraper(BaseScraper):
    def scrape(self) -> Dict:
        url = "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the main content area
        content = soup.find('main') or soup.find('article') or soup.find('div', class_='markdown')
        text = content.get_text(separator='\n', strip=True) if content else "No deprecation content found"
        
        return {
            "provider": "Anthropic",
            "url": url,
            "content": text,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }


class GoogleVertexScraper(BaseScraper):
    def scrape(self) -> Dict:
        url = "https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations"
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Google Cloud docs typically have content in devsite-content
        content = soup.find('article') or soup.find('div', class_='devsite-article-body')
        text = content.get_text(separator='\n', strip=True) if content else "No deprecation content found"
        
        return {
            "provider": "Google Vertex AI",
            "url": url,
            "content": text,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }


class AWSBedrockScraper(BaseScraper):
    def scrape(self) -> Dict:
        url = "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html"
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # AWS docs usually have content in main-content div
        content = soup.find('div', id='main-content') or soup.find('main')
        text = content.get_text(separator='\n', strip=True) if content else "No deprecation content found"
        
        return {
            "provider": "AWS Bedrock",
            "url": url,
            "content": text,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }


class CohereScraper(BaseScraper):
    def scrape(self) -> Dict:
        url = "https://docs.cohere.com/docs/deprecations"
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the main content
        content = soup.find('main') or soup.find('article') or soup.find('div', class_='markdown')
        text = content.get_text(separator='\n', strip=True) if content else "No deprecation content found"
        
        return {
            "provider": "Cohere",
            "url": url,
            "content": text,
            "scraped_at": datetime.now(timezone.utc).isoformat()
        }


# List of all scrapers
SCRAPERS = [
    OpenAIScraper,
    AnthropicScraper,
    GoogleVertexScraper,
    AWSBedrockScraper,
    CohereScraper,
]