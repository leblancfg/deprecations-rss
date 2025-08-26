"""Anthropic deprecations scraper with individual model extraction."""

import re
from typing import List
from bs4 import BeautifulSoup

from base_scraper import EnhancedBaseScraper
from models import DeprecationItem


class AnthropicScraper(EnhancedBaseScraper):
    """Scraper for Anthropic deprecations page."""

    provider_name = "Anthropic"
    url = "https://docs.anthropic.com/en/docs/about-claude/model-deprecations"
    requires_playwright = True  # Client-side rendering

    def extract_structured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Extract deprecations from Anthropic's table format."""
        items = []
        soup = BeautifulSoup(html, "html.parser")

        # Find main content
        main = soup.find("main") or soup.find("article")
        if not main:
            return items

        # Find all tables - Anthropic uses tables for deprecation info
        current_section = ""

        # Find all headers and tables in the document
        all_elements = main.find_all(["h2", "h3", "table"])

        for element in all_elements:
            # Track section headers
            if element.name in ["h2", "h3"]:
                current_section = element.get_text(strip=True)
                continue

            # Process tables
            if element.name == "table":
                rows = element.find_all("tr")
                if len(rows) <= 1:
                    continue

                # Parse headers
                headers = [
                    th.get_text(strip=True).lower()
                    for th in rows[0].find_all(["th", "td"])
                ]

                # Extract announcement date from section if present
                announcement_date = ""
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", current_section)
                if date_match:
                    announcement_date = date_match.group(1)

                # Process each row
                for row in rows[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) < 2:
                        continue

                    # Anthropic tables typically have one of these formats:
                    # Format 1: Model | State | Deprecated Date | Retired Date
                    # Format 2: Retirement Date | Deprecated Model | Recommended Replacement

                    model_name = ""
                    shutdown_date = ""
                    replacement = None
                    deprecated_date = ""
                    state_text = ""

                    # Detect table format by checking headers
                    if "deprecated model" in " ".join(headers).lower():
                        # Format 2: Retirement Date | Deprecated Model | Recommended Replacement
                        if len(cells) >= 2:
                            shutdown_date = self.parse_date(cells[0])
                            model_name = cells[1]
                            if len(cells) > 2 and cells[2] not in ["—", "-", "N/A"]:
                                replacement = cells[2]
                    else:
                        # Format 1: Model | State | Deprecated Date | Retired Date
                        # Try to identify columns by content and headers
                        for i, cell in enumerate(cells):
                            header = headers[i] if i < len(headers) else ""

                            # Model name detection - first column often in format 1
                            if i == 0 and any(
                                model_prefix in cell.lower()
                                for model_prefix in [
                                    "claude",
                                    "haiku",
                                    "sonnet",
                                    "opus",
                                ]
                            ):
                                model_name = cell

                            # State detection
                            elif cell.lower() in ["retired", "deprecated", "active"]:
                                state_text = cell

                            # Date detection - use header to determine type
                            elif i < len(headers) and (
                                "retire" in header or "deprecat" in header
                            ):
                                # Skip if the cell explicitly says N/A (model is active)
                                if cell.strip().upper() == "N/A":
                                    if "deprecat" in header:
                                        # N/A in deprecation column means model is active - skip this row
                                        deprecated_date = "N/A"
                                else:
                                    parsed = self.parse_date(cell)
                                    if parsed:
                                        if "retire" in header:
                                            shutdown_date = parsed
                                        else:
                                            deprecated_date = parsed

                            # Replacement detection
                            elif i == len(cells) - 1 and cell not in ["—", "-", "N/A"]:
                                replacement = cell

                    # If no model name found, try first non-date cell
                    if not model_name:
                        for cell in cells:
                            if cell and not re.match(r"\d{4}-\d{2}-\d{2}", cell):
                                model_name = cell
                                break

                    if model_name and (shutdown_date or deprecated_date):
                        # For retired models, use the retired date as shutdown date
                        if state_text == "Retired" and not shutdown_date:
                            shutdown_date = deprecated_date

                        # Parse "Not sooner than" dates - extract the actual date
                        if shutdown_date and "Not sooner than" in shutdown_date:
                            date_match = re.search(
                                r"(\d{4}-\d{2}-\d{2})", shutdown_date
                            )
                            if date_match:
                                shutdown_date = date_match.group(1)

                        # Skip if deprecated_date is explicitly N/A (model is active)
                        if deprecated_date == "N/A":
                            continue

                        # Skip if we don't have a valid date
                        final_shutdown = shutdown_date or deprecated_date
                        if not final_shutdown:
                            continue

                        item = DeprecationItem(
                            provider=self.provider_name,
                            model_id=model_name,
                            model_name=model_name,
                            announcement_date=deprecated_date
                            or announcement_date
                            or "",
                            shutdown_date=final_shutdown,
                            replacement_model=replacement,
                            deprecation_context=current_section,
                            url=f"{self.url}#{model_name.replace(' ', '-').lower()}",
                        )
                        items.append(item)

        return items

    def extract_unstructured_deprecations(self, html: str) -> List[DeprecationItem]:
        """Anthropic uses tables, so no unstructured extraction needed."""
        return []
