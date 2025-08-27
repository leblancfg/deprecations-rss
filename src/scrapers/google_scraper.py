"""Google AI/Gemini deprecations scraper with individual model extraction."""

import re
from typing import List
from bs4 import BeautifulSoup

from ..base_scraper import EnhancedBaseScraper
from ..models import DeprecationItem


class GoogleScraper(EnhancedBaseScraper):
    """Scraper for Google AI/Gemini deprecations page."""

    provider_name = "Google"
    url = "https://ai.google.dev/gemini-api/docs/changelog"
    requires_playwright = False  # Static content, httpx is fine

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Google AI changelog format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        content = soup.find("article") or soup.find(
            "div", class_="devsite-article-body"
        )
        if not content:
            return items

        # Google AI uses date-based sections with h2 headers
        sections = content.find_all(["h2", "h3"])

        for section_header in sections:
            section_title = section_header.get_text(strip=True)
            
            # Skip non-date sections
            date_match = re.search(r'(\w+ \d+, \d{4})', section_title)
            if not date_match:
                continue
                
            section_date = self.parse_date(date_match.group(1))

            # Look for deprecation info after the header
            next_elem = section_header.next_sibling
            
            while next_elem:
                if hasattr(next_elem, "name"):
                    if next_elem.name in ["h2", "h3"]:
                        # Next section
                        break

                    text = next_elem.get_text(strip=True)

                    # Look for deprecation patterns
                    if any(keyword in text.lower() for keyword in [
                        "deprecated", "deprecation", "no longer supported", 
                        "removed", "will be deprecated", "retirement"
                    ]):
                        # Extract model names and dates
                        model_matches = re.findall(
                            r'(gemini-[a-zA-Z0-9\-\.]+)', text.lower()
                        )
                        
                        # Look for specific deprecation dates in text
                        future_date_match = re.search(
                            r'(\w+ \d+, \d{4})', text
                        )
                        deprecation_date = ""
                        if future_date_match:
                            parsed_date = self.parse_date(future_date_match.group(1))
                            # Only use if it's a future date (likely shutdown date)
                            if parsed_date and parsed_date > section_date:
                                deprecation_date = parsed_date
                        
                        if not deprecation_date:
                            deprecation_date = section_date

                        # Create items for each model found
                        if model_matches:
                            for model_id in model_matches:
                                # Clean up model name
                                model_name = model_id.replace('-', ' ').title()
                                if 'Pro' in model_name:
                                    model_name = model_name.replace('Pro', 'Pro')
                                if 'Flash' in model_name:
                                    model_name = model_name.replace('Flash', 'Flash')
                                
                                # Look for replacement models
                                replacement = None
                                repl_patterns = [
                                    r'redirect(?:ing)?\s+to\s+(gemini-[a-zA-Z0-9\-\.]+)',
                                    r'use\s+(gemini-[a-zA-Z0-9\-\.]+)',
                                    r'replaced\s+(?:by|with)\s+(gemini-[a-zA-Z0-9\-\.]+)'
                                ]
                                for pattern in repl_patterns:
                                    repl_match = re.search(pattern, text.lower())
                                    if repl_match:
                                        replacement = repl_match.group(1)
                                        break

                                item = DeprecationItem(
                                    provider=self.provider_name,
                                    model_id=model_id,
                                    model_name=model_name,
                                    announcement_date=section_date,
                                    shutdown_date=deprecation_date if deprecation_date != section_date else "",
                                    replacement_model=replacement,
                                    deprecation_context=text,
                                    url=f"{self.url}#{section_date.replace('-', '')}",
                                )
                                items.append(item)
                        else:
                            # Handle general deprecation entries
                            if "gemini" in text.lower():
                                # Try to extract model from context
                                general_model_patterns = [
                                    r'gemini\s+1\.0\s+pro\s+vision',
                                    r'gemini\s+1\.0\s+pro',
                                    r'gemini\s+1\.5\s+(?:pro|flash)',
                                ]
                                
                                for pattern in general_model_patterns:
                                    if re.search(pattern, text.lower()):
                                        model_name = re.search(pattern, text.lower()).group(0)
                                        model_id = model_name.lower().replace(' ', '-')
                                        
                                        item = DeprecationItem(
                                            provider=self.provider_name,
                                            model_id=model_id,
                                            model_name=model_name.title(),
                                            announcement_date=section_date,
                                            shutdown_date=deprecation_date if deprecation_date != section_date else "",
                                            replacement_model=None,
                                            deprecation_context=text,
                                            url=f"{self.url}#{section_date.replace('-', '')}",
                                        )
                                        items.append(item)
                                        break

                next_elem = next_elem.next_sibling

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Google AI uses structured changelog, so no unstructured extraction needed."""
        return []