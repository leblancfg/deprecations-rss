"""Anthropic deprecations scraper implementation."""

import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.models.deprecation import Deprecation
from src.scrapers.base import BaseScraper

try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


class AnthropicScraper(BaseScraper):
    """Scraper for Anthropic model deprecations."""

    def __init__(self) -> None:
        """Initialize the Anthropic scraper."""
        super().__init__("https://docs.anthropic.com/en/docs/about-claude/model-deprecations")

    async def scrape_api(self) -> dict[str, Any]:
        """Scrape deprecations using Anthropic API if available."""
        try:
            # Anthropic doesn't have a public API endpoint for deprecations
            # But we'll simulate what one might look like for testing
            api_url = "https://api.anthropic.com/v1/deprecations"
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
                        "Upgrade-Insecure-Requests": "1",
                    },
                    timeout=self.config.timeout,
                    follow_redirects=True,
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
                await page.set_extra_http_headers(
                    {"User-Agent": self.config.user_agent, "Accept-Language": "en-US,en;q=0.9"}
                )

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
            retirement_date = self._parse_date(item.get("retirement_date"))

            if not deprecation_date or not retirement_date:
                return None

            # Handle invalid date ordering
            if retirement_date <= deprecation_date:
                logger.warning(f"Invalid date ordering for {model}, skipping")
                return None

            return Deprecation(
                provider="Anthropic",
                model=model,
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                replacement=item.get("replacement"),
                notes=item.get("notes"),
                source_url=self.url,  # type: ignore[arg-type]
            )

        except Exception as e:
            logger.warning(f"Failed to parse API deprecation: {e}")
            return None

    def _parse_html_deprecations(self, soup: BeautifulSoup) -> list[Deprecation]:
        """Parse deprecations from HTML content."""
        deprecations = []

        # Parse main status table
        status_table_deprecations = self._parse_status_table(soup)
        deprecations.extend(status_table_deprecations)

        # Parse history tables for replacement information
        history_table_deprecations = self._parse_history_tables(soup)
        deprecations.extend(history_table_deprecations)

        # Merge duplicates, preferring ones with replacement info
        merged_deprecations = self._merge_duplicate_deprecations(deprecations)

        return merged_deprecations

    def _parse_status_table(self, soup: BeautifulSoup) -> list[Deprecation]:
        """Parse the main model status table."""
        deprecations = []

        # Find the main status table
        tables = soup.find_all("table")
        logger.debug(f"Found {len(tables)} tables total")

        for i, table in enumerate(tables):
            # Check if this is the status table by looking for expected headers
            headers = table.find("thead")
            if not headers:
                logger.debug(f"Table {i + 1}: No thead found")
                continue

            header_cells = [
                cell.get_text().strip().lower() for cell in headers.find_all(["th", "td"])
            ]
            header_text = " ".join(header_cells)
            logger.debug(f"Table {i + 1} headers: {header_cells}")

            if not ("api model name" in header_text and "current state" in header_text):
                logger.debug(f"Table {i + 1}: Not the status table (missing expected headers)")
                continue

            logger.debug(f"Table {i + 1}: Identified as status table")

            # Parse table rows
            tbody = table.find("tbody")
            if not tbody:
                logger.debug(f"Table {i + 1}: No tbody found")
                continue

            rows = tbody.find_all("tr")
            logger.debug(f"Table {i + 1}: Found {len(rows)} body rows")

            for j, row in enumerate(rows):
                dep = self._parse_status_table_row(row)
                if dep:
                    logger.debug(
                        f"Table {i + 1}, Row {j + 1}: Extracted deprecation for {dep.model}"
                    )
                    deprecations.append(dep)
                else:
                    cells = [cell.get_text().strip() for cell in row.find_all(["td", "th"])]
                    logger.debug(f"Table {i + 1}, Row {j + 1}: Skipped row with cells: {cells}")

        logger.debug(f"Status table parsing found {len(deprecations)} deprecations")
        return deprecations

    def _parse_status_table_row(self, row: Any) -> Deprecation | None:
        """Parse a single row from the status table."""
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                logger.debug(f"Row has {len(cells)} cells, need at least 4")
                return None

            model = cells[0].get_text().strip()
            status = cells[1].get_text().strip().lower()
            deprecated_date_str = cells[2].get_text().strip()
            retired_date_str = cells[3].get_text().strip()

            logger.debug(
                f"Parsing row: model={model}, status={status}, dep_date={deprecated_date_str}, ret_date={retired_date_str}"
            )

            # Skip active models
            if status == "active":
                logger.debug(f"Skipping active model: {model}")
                return None

            if not deprecated_date_str or not retired_date_str:
                logger.debug(f"Missing date info for {model}")
                return None

            deprecation_date = self._parse_date(deprecated_date_str)
            retirement_date = self._parse_date(retired_date_str)

            logger.debug(f"Parsed dates: dep={deprecation_date}, ret={retirement_date}")

            if not deprecation_date or not retirement_date:
                logger.debug(f"Failed to parse dates for {model}")
                return None

            # Handle invalid date ordering
            if retirement_date <= deprecation_date:
                logger.warning(f"Invalid date ordering for {model}, skipping")
                return None

            return Deprecation(
                provider="Anthropic",
                model=model,
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                source_url=self.url,  # type: ignore[arg-type]
            )

        except Exception as e:
            logger.warning(f"Failed to parse status table row: {e}")
            return None

    def _parse_history_tables(self, soup: BeautifulSoup) -> list[Deprecation]:
        """Parse deprecation history tables."""
        deprecations = []

        # Find all tables that might be history tables
        tables = soup.find_all("table")

        for table in tables:
            # Check if this is a history table by looking for expected headers
            headers = table.find("thead")
            if not headers:
                continue

            header_cells = [
                cell.get_text().strip().lower() for cell in headers.find_all(["th", "td"])
            ]
            header_text = " ".join(header_cells)

            if not ("retirement date" in header_text and "deprecated model" in header_text):
                continue

            # Parse table rows
            tbody = table.find("tbody")
            if not tbody:
                continue

            for row in tbody.find_all("tr"):
                dep = self._parse_history_table_row(row)
                if dep:
                    deprecations.append(dep)

        return deprecations

    def _parse_history_table_row(self, row: Any) -> Deprecation | None:
        """Parse a single row from a history table."""
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                return None

            retired_date_str = cells[0].get_text().strip()
            model = cells[1].get_text().strip()
            replacement = cells[2].get_text().strip() or None

            retirement_date = self._parse_date(retired_date_str)
            if not retirement_date:
                return None

            # For history tables, we need to infer the deprecation date
            # Anthropic provides at least 60 days notice, so we'll estimate
            # deprecation date as retirement date minus 60 days as a fallback
            deprecation_date = self._estimate_deprecation_date(retirement_date)

            return Deprecation(
                provider="Anthropic",
                model=model,
                deprecation_date=deprecation_date,
                retirement_date=retirement_date,
                replacement=replacement,
                source_url=self.url,  # type: ignore[arg-type]
            )

        except Exception as e:
            logger.warning(f"Failed to parse history table row: {e}")
            return None

    def _estimate_deprecation_date(self, retirement_date: datetime) -> datetime:
        """Estimate deprecation date as retirement date minus 60 days."""
        from datetime import timedelta

        return retirement_date - timedelta(days=60)

    def _merge_duplicate_deprecations(self, deprecations: list[Deprecation]) -> list[Deprecation]:
        """Merge duplicate deprecations, preferring ones with replacement info."""
        # Group by model name
        by_model: dict[str, list[Deprecation]] = {}
        for dep in deprecations:
            if dep.model not in by_model:
                by_model[dep.model] = []
            by_model[dep.model].append(dep)

        merged = []
        for model_deprecations in by_model.values():
            if len(model_deprecations) == 1:
                merged.append(model_deprecations[0])
            else:
                # Merge duplicates by creating a best-of-both combination
                # Start with the first one as base
                best_dep = model_deprecations[0]

                for dep in model_deprecations[1:]:
                    # Create a merged deprecation with the best attributes from both
                    # Prefer actual deprecation dates over estimated ones
                    estimated_dep_date = self._estimate_deprecation_date(dep.retirement_date)
                    estimated_best_date = self._estimate_deprecation_date(best_dep.retirement_date)

                    # Choose the better deprecation date (non-estimated if available)
                    if (
                        best_dep.deprecation_date == estimated_best_date
                        and dep.deprecation_date != estimated_dep_date
                    ):
                        # dep has actual date, best has estimated - use dep's date
                        deprecation_date = dep.deprecation_date
                    elif (
                        dep.deprecation_date == estimated_dep_date
                        and best_dep.deprecation_date != estimated_best_date
                    ):
                        # best has actual date, dep has estimated - use best's date
                        deprecation_date = best_dep.deprecation_date
                    else:
                        # Both are actual or both are estimated - keep the first one
                        deprecation_date = best_dep.deprecation_date

                    # Choose replacement info (prefer non-None)
                    replacement = dep.replacement if dep.replacement else best_dep.replacement

                    # Choose notes (prefer non-None)
                    notes = dep.notes if dep.notes else best_dep.notes

                    # Create merged deprecation
                    best_dep = Deprecation(
                        provider=best_dep.provider,
                        model=best_dep.model,
                        deprecation_date=deprecation_date,
                        retirement_date=best_dep.retirement_date,  # Should be the same
                        replacement=replacement,
                        notes=notes,
                        source_url=best_dep.source_url,
                    )

                merged.append(best_dep)

        return merged

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse various date formats used by Anthropic."""
        if not date_str or not date_str.strip():
            return None

        date_str = date_str.strip()

        # Try different date formats
        formats = [
            "%Y-%m-%d",  # 2024-09-04
            "%B %d, %Y",  # September 4, 2024
            "%B %d %Y",  # September 4 2024
            "%d %B %Y",  # 4 September 2024
            "%m/%d/%Y",  # 09/04/2024
            "%d/%m/%Y",  # 04/09/2024
            "%Y/%m/%d",  # 2024/09/04
            "%B %Y",  # September 2024
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

        # Try parsing month-year format with regex
        month_year_match = re.match(r"(\w+)\s+(\d{4})", date_str)
        if month_year_match:
            try:
                month_str, year_str = month_year_match.groups()
                dt = datetime.strptime(f"{month_str} 1, {year_str}", "%B %d, %Y")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                pass

        # Try parsing various formats with more flexible regex
        date_patterns = [
            (r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", "%B %d %Y"),  # Month DD, YYYY
            (r"(\d{1,2})\s+(\w+)\s+(\d{4})", "%d %B %Y"),  # DD Month YYYY
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),  # YYYY-MM-DD
            (r"(\d{1,2})/(\d{1,2})/(\d{4})", "%m/%d/%Y"),  # MM/DD/YYYY
        ]

        for pattern, fmt in date_patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    if "%" in fmt and "%B" in fmt:
                        # Handle month names
                        groups = match.groups()
                        if len(groups) == 3:
                            if fmt == "%B %d %Y" or fmt == "%d %B %Y":
                                dt = datetime.strptime(f"{groups[0]} {groups[1]} {groups[2]}", fmt)
                            else:
                                continue
                            return dt.replace(tzinfo=UTC)
                    else:
                        # Handle numeric dates
                        reconstructed = date_str
                        dt = datetime.strptime(reconstructed, fmt)
                        return dt.replace(tzinfo=UTC)
                except ValueError:
                    continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
