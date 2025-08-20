"""Test suite for the scraper registry."""


from src.models.scraper import ScraperConfig
from src.scrapers.base import BaseScraper
from src.scrapers.openai import OpenAIScraper
from src.scrapers.registry import ScraperRegistry


class _MockScraper(BaseScraper):
    """Mock scraper for testing."""

    def __init__(self, config: ScraperConfig | None = None):
        super().__init__("https://example.com", config)

    async def scrape_api(self) -> dict:
        return {"deprecations": []}

    async def scrape_html(self) -> dict:
        return {"deprecations": []}

    async def scrape_playwright(self) -> dict:
        return {"deprecations": []}


def describe_scraper_registry():
    """Test scraper registry functionality."""

    def it_initializes_with_default_scrapers():
        """Initializes with default scrapers registered."""
        registry = ScraperRegistry()

        # Check that OpenAI scraper is registered by default
        assert "openai" in registry.list_available()
        assert registry.get("openai") == OpenAIScraper

    def it_registers_new_scrapers():
        """Registers new scrapers successfully."""
        registry = ScraperRegistry()

        # Register a mock scraper
        registry.register("mock", _MockScraper)

        assert "mock" in registry.list_available()
        assert registry.get("mock") == _MockScraper

    def it_overwrites_existing_scrapers():
        """Overwrites existing scrapers when registering with same name."""
        registry = ScraperRegistry()

        # Register first scraper
        registry.register("test", _MockScraper)
        assert registry.get("test") == _MockScraper

        # Register different scraper with same name
        registry.register("test", OpenAIScraper)
        assert registry.get("test") == OpenAIScraper

    def it_returns_none_for_unknown_scrapers():
        """Returns None when getting unknown scraper."""
        registry = ScraperRegistry()

        assert registry.get("unknown") is None

    def it_creates_scraper_instances():
        """Creates scraper instances successfully."""
        registry = ScraperRegistry()

        # Create OpenAI scraper
        openai_scraper = registry.create("openai")
        assert isinstance(openai_scraper, OpenAIScraper)
        assert openai_scraper is not None

    def it_creates_scraper_with_config():
        """Creates scraper with custom configuration."""
        registry = ScraperRegistry()

        config = ScraperConfig(
            timeout=60,
            max_retries=5,
            user_agent="CustomAgent/1.0"
        )

        # Create OpenAI scraper with config
        openai_scraper = registry.create("openai", config)
        assert isinstance(openai_scraper, OpenAIScraper)
        assert openai_scraper.config.timeout == 60
        assert openai_scraper.config.max_retries == 5
        assert openai_scraper.config.user_agent == "CustomAgent/1.0"

    def it_returns_none_for_unknown_scraper_creation():
        """Returns None when creating unknown scraper."""
        registry = ScraperRegistry()

        scraper = registry.create("unknown")
        assert scraper is None

    def it_creates_all_registered_scrapers():
        """Creates instances of all registered scrapers."""
        registry = ScraperRegistry()

        # Register additional scraper
        registry.register("mock", _MockScraper)

        # Create all scrapers
        scrapers = registry.create_all()

        assert len(scrapers) >= 2  # At least OpenAI and Mock
        assert any(isinstance(s, OpenAIScraper) for s in scrapers)
        assert any(isinstance(s, _MockScraper) for s in scrapers)

    def it_creates_all_scrapers_with_config():
        """Creates all scrapers with shared configuration."""
        registry = ScraperRegistry()

        config = ScraperConfig(
            timeout=45,
            max_retries=2
        )

        # Create all scrapers with config
        scrapers = registry.create_all(config)

        for scraper in scrapers:
            assert scraper.config.timeout == 45
            assert scraper.config.max_retries == 2

    def it_lists_available_scrapers():
        """Lists all available scraper names."""
        registry = ScraperRegistry()

        # Register additional scrapers
        registry.register("mock1", _MockScraper)
        registry.register("mock2", _MockScraper)

        available = registry.list_available()

        assert "openai" in available
        assert "mock1" in available
        assert "mock2" in available
        assert len(available) >= 3

    def it_handles_scraper_creation_errors():
        """Handles errors during scraper creation gracefully."""
        registry = ScraperRegistry()

        # Register a scraper that will fail to instantiate
        class _FailingScraper(BaseScraper):
            def __init__(self):
                raise ValueError("Intentional failure")

        registry.register("failing", _FailingScraper)

        # Should return None instead of raising
        scraper = registry.create("failing")
        assert scraper is None

        # create_all should skip the failing scraper
        scrapers = registry.create_all()
        assert all(not isinstance(s, _FailingScraper) for s in scrapers)
