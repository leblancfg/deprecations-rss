"""Basic smoke tests to ensure nothing is broken."""

import subprocess
import sys
from pathlib import Path


def test_imports():
    """Verify core modules can be imported."""
    try:
        from src import main  # noqa: F401
        from src import providers  # noqa: F401
        from src import rss_gen  # noqa: F401
        from src import models  # noqa: F401

        assert True
    except ImportError as e:
        assert False, f"Failed to import module: {e}"


def test_scraper_imports():
    """Verify all scrapers can be imported."""
    try:
        from src.scrapers.openai_scraper import OpenAIScraper  # noqa: F401
        from src.scrapers.anthropic_scraper import AnthropicScraper  # noqa: F401
        from src.scrapers.google_vertex_scraper import GoogleVertexScraper  # noqa: F401
        from src.scrapers.aws_bedrock_scraper import AWSBedrockScraper  # noqa: F401
        from src.scrapers.cohere_scraper import CohereScraper  # noqa: F401

        assert True
    except ImportError as e:
        assert False, f"Failed to import scraper: {e}"


def test_main_module_runs():
    """Verify main module can be executed (dry run)."""
    # We'll test by importing and checking if the module loads without errors
    # Since actual scraping requires network/API access, we just test the import
    result = subprocess.run(
        [sys.executable, "-c", "import src.main"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"Failed to import main module: {result.stderr}"


def test_data_json_exists():
    """Verify data.json exists (it's required for feeds)."""
    data_file = Path("data.json")
    assert data_file.exists(), "data.json file not found"
    assert data_file.stat().st_size > 0, "data.json file is empty"


def test_cache_directory_exists():
    """Verify cache directory structure exists."""
    cache_dir = Path("cache")
    assert cache_dir.exists(), "cache directory not found"
    assert cache_dir.is_dir(), "cache is not a directory"
