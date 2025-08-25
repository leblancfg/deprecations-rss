"""Main script to scrape deprecations and update data.json."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from providers import SCRAPERS
from change_detector import ChangeDetector
from llm_analyzer import LLMAnalyzer

# Load environment variables
load_dotenv(os.path.expanduser("~/.env"))


def scrape_all():
    """Scrape all providers and return results."""
    all_deprecations = []

    for scraper_class in SCRAPERS:
        try:
            scraper = scraper_class()
            deprecations = scraper.scrape()  # Now returns a list
            all_deprecations.extend(deprecations)

            # Get provider name from first item or fallback
            provider = (
                deprecations[0]["provider"]
                if deprecations
                else scraper_class.__name__.replace("Scraper", "")
            )
            print(f"✓ Scraped {provider}: {len(deprecations)} deprecations")
        except Exception as e:
            print(f"✗ Failed to scrape {scraper_class.__name__}: {e}")

    return all_deprecations


def enhance_with_llm(scraped_data):
    """Enhance scraped data with LLM analysis when content changes."""
    if not (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_TOKEN')):
        print("⚠️  No ANTHROPIC_API_KEY or ANTHROPIC_API_TOKEN found, skipping LLM enhancement")
        return scraped_data
    
    print("🔍 Checking for content changes...")
    change_detector = ChangeDetector()
    changed_items, unchanged_items = change_detector.detect_changes(scraped_data)
    
    if not changed_items:
        print("✓ No content changes detected, using cached data")
        return unchanged_items + changed_items  # Return all items
    
    print(f"🧠 Analyzing {len(changed_items)} changed items with LLM...")
    
    try:
        analyzer = LLMAnalyzer()
        enhanced_changed = analyzer.analyze_batch(changed_items)
        
        # Cache the LLM analysis results
        for original, enhanced in zip(changed_items, enhanced_changed):
            if enhanced.get('llm_enhanced'):
                llm_analysis = {
                    'title': enhanced.get('title'),
                    'content': enhanced.get('content'),
                    'announcement_date': enhanced.get('announcement_date'),
                    'shutdown_date': enhanced.get('shutdown_date'),
                    'llm_enhanced': True,
                    'llm_enhanced_at': enhanced.get('llm_enhanced_at')
                }
                change_detector.cache_llm_analysis(original, llm_analysis)
        
        print(f"✓ Enhanced {len(enhanced_changed)} items with LLM analysis")
        return unchanged_items + enhanced_changed
        
    except Exception as e:
        print(f"✗ LLM enhancement failed: {e}")
        print("📝 Falling back to original scraped content")
        return scraped_data


def save_data(data):
    """Save scraped data to data.json."""
    output_file = Path("data.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved {len(data)} deprecation notices to data.json")


if __name__ == "__main__":
    print("🚀 Starting deprecation scraper with LLM enhancement...")
    scraped_data = scrape_all()
    enhanced_data = enhance_with_llm(scraped_data)
    save_data(enhanced_data)
