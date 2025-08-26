"""Test the enhanced scrapers to verify individual model extraction."""

import sys
sys.path.append('.')

from scrapers.openai_scraper import OpenAIScraper
from scrapers.cohere_scraper import CohereScraper
from scrapers.google_vertex_scraper import GoogleVertexScraper
from scrapers.aws_bedrock_scraper import AWSBedrockScraper
from scrapers.anthropic_scraper import AnthropicScraper


def test_scraper(scraper_class):
    """Test a single scraper and show results."""
    print(f"\n{'='*60}")
    print(f"Testing {scraper_class.provider_name}")
    print('='*60)
    
    try:
        scraper = scraper_class()
        items = scraper.scrape()
        
        print(f"Found {len(items)} deprecation items:")
        
        # Group by announcement date for cleaner output
        by_date = {}
        for item in items:
            date = item.announcement_date or "Unknown"
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(item)
        
        # Show items grouped by date
        for date in sorted(by_date.keys(), reverse=True):
            print(f"\n  Announced {date}:")
            for item in by_date[date]:
                print(f"    • {item.model_id}")
                print(f"      Shutdown: {item.shutdown_date}")
                if item.replacement_model:
                    print(f"      Replace with: {item.replacement_model}")
        
        # Show cache stats
        cache_stats = scraper.cache_manager.get_stats()
        print(f"\n  Cache: {cache_stats['valid_entries']} valid entries, "
              f"{cache_stats['total_size_mb']} MB")
        
        return len(items)
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Test all scrapers."""
    scrapers = [
        OpenAIScraper,
        CohereScraper,
        GoogleVertexScraper,
        AWSBedrockScraper,
        AnthropicScraper
    ]
    
    total_items = 0
    
    for scraper_class in scrapers:
        count = test_scraper(scraper_class)
        total_items += count
    
    print(f"\n{'='*60}")
    print(f"Total deprecation items found: {total_items}")
    print('='*60)


if __name__ == "__main__":
    main()