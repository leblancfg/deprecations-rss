"""Simple deprecation scrapers for AI providers - now with individual deprecation parsing."""

# Import the new enhanced scrapers
from .scrapers.openai_scraper import OpenAIScraper
from .scrapers.anthropic_scraper import AnthropicScraper
from .scrapers.google_vertex_scraper import GoogleVertexScraper
from .scrapers.aws_bedrock_scraper import AWSBedrockScraper
from .scrapers.cohere_scraper import CohereScraper

# List of all scrapers - using the new enhanced versions
SCRAPERS = [
    OpenAIScraper,
    AnthropicScraper,
    GoogleVertexScraper,
    AWSBedrockScraper,
    CohereScraper,
]
