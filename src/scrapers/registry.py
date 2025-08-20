"""Registry of available scrapers for the orchestrator."""

import logging

from src.models.scraper import ScraperConfig
from src.scrapers.base import BaseScraper
from src.scrapers.anthropic import AnthropicScraper
from src.scrapers.openai import OpenAIScraper

logger = logging.getLogger(__name__)


class ScraperRegistry:
    """Registry for managing available scrapers."""

    def __init__(self) -> None:
        """Initialize the scraper registry."""
        self._scrapers: dict[str, type[BaseScraper]] = {}
        self._register_default_scrapers()

    def _register_default_scrapers(self) -> None:
        """Register all default scrapers."""
        self.register("anthropic", AnthropicScraper)
        self.register("openai", OpenAIScraper)
        logger.info(f"Registered {len(self._scrapers)} default scrapers")

    def register(self, name: str, scraper_class: type[BaseScraper]) -> None:
        """
        Register a scraper class.

        Args:
            name: Name to register the scraper under
            scraper_class: Scraper class to register
        """
        if name in self._scrapers:
            logger.warning(f"Overwriting existing scraper: {name}")

        self._scrapers[name] = scraper_class
        logger.debug(f"Registered scraper: {name}")

    def get(self, name: str) -> type[BaseScraper] | None:
        """
        Get a scraper class by name.

        Args:
            name: Name of the scraper

        Returns:
            Scraper class or None if not found
        """
        return self._scrapers.get(name)

    def create(self, name: str, config: ScraperConfig | None = None) -> BaseScraper | None:
        """
        Create a scraper instance by name.

        Args:
            name: Name of the scraper
            config: Optional scraper configuration

        Returns:
            Scraper instance or None if not found
        """
        scraper_class = self.get(name)
        if not scraper_class:
            logger.error(f"Scraper not found: {name}")
            return None

        try:
            # Both OpenAI and Anthropic scrapers have their own URLs and don't take arguments
            if name in ("openai", "anthropic"):
                scraper = scraper_class()  # type: ignore[call-arg]
                if config:
                    scraper.config = config
            else:
                # Try to create with config parameter (for test scrapers)
                try:
                    scraper = scraper_class(config=config)  # type: ignore[call-arg]
                except TypeError:
                    # If that fails, try without any arguments
                    try:
                        scraper = scraper_class()  # type: ignore[call-arg]
                        if config:
                            scraper.config = config
                    except TypeError:
                        logger.error(
                            f"Cannot instantiate scraper {name} - unknown constructor signature"
                        )
                        return None

            logger.debug(f"Created scraper instance: {name}")
            return scraper
        except Exception as e:
            logger.error(f"Failed to create scraper {name}: {e}")
            return None

    def create_all(self, config: ScraperConfig | None = None) -> list[BaseScraper]:
        """
        Create instances of all registered scrapers.

        Args:
            config: Optional scraper configuration

        Returns:
            List of scraper instances
        """
        scrapers = []
        for name in self._scrapers:
            scraper = self.create(name, config)
            if scraper:
                scrapers.append(scraper)

        logger.info(f"Created {len(scrapers)} scraper instances")
        return scrapers

    def list_available(self) -> list[str]:
        """
        List all available scraper names.

        Returns:
            List of registered scraper names
        """
        return list(self._scrapers.keys())


# Global registry instance
registry = ScraperRegistry()
