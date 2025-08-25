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
    """Enhance scraped data with LLM analysis for changed items only."""
    print("🔍 Checking for content changes...")
    change_detector = ChangeDetector()
    changed_items = change_detector.detect_changes(scraped_data)
    
    if not changed_items:
        print("✓ No content changes detected")
        return scraped_data
    
    print(f"🧠 Analyzing {len(changed_items)} changed items with LLM...")
    
    # LLMAnalyzer initialization will validate API key and fail fast if invalid
    analyzer = LLMAnalyzer()
    enhanced_changed = analyzer.analyze_batch(changed_items)
    
    # Create a map of enhanced items by hash for quick lookup
    enhanced_map = {}
    for original, enhanced in zip(changed_items, enhanced_changed):
        item_hash = change_detector._hash_item(original)
        enhanced_map[item_hash] = enhanced
    
    # Build final result: use enhanced version for changed items, original for unchanged
    result = []
    for item in scraped_data:
        item_hash = change_detector._hash_item(item)
        if item_hash in enhanced_map:
            result.append(enhanced_map[item_hash])
        else:
            result.append(item)
    
    print(f"✓ Enhanced {len(enhanced_changed)} items with LLM analysis")
    return result


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
