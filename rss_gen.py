"""Simple RSS feed generator."""

import json
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom


def load_data():
    """Load data from data.json."""
    data_file = Path("data.json")
    if not data_file.exists():
        return []
    
    with open(data_file) as f:
        return json.load(f)


def create_rss_feed(data):
    """Create RSS feed from scraped data."""
    # Create RSS root element
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    # Add channel metadata
    ET.SubElement(channel, "title").text = "AI Model Deprecations"
    ET.SubElement(channel, "link").text = "https://leblancfg.com/deprecations-rss/"
    ET.SubElement(channel, "description").text = "RSS feed tracking deprecations across major AI providers"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Add items for each provider
    for item_data in data:
        item = ET.SubElement(channel, "item")
        
        title = f"{item_data['provider']} Deprecations"
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = item_data["url"]
        
        # Use the scraped content as description (truncate if too long)
        content = item_data["content"]
        if len(content) > 5000:
            content = content[:5000] + "...\n\n[Content truncated. Visit the link for full details.]"
        
        ET.SubElement(item, "description").text = content
        ET.SubElement(item, "pubDate").text = datetime.fromisoformat(item_data["scraped_at"]).strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item, "guid", isPermaLink="false").text = f"{item_data['provider']}-{item_data['scraped_at']}"
    
    # Convert to pretty XML string
    xml_str = ET.tostring(rss, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")


def save_rss_feed(feed_content):
    """Save RSS feed to docs/feed.xml."""
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    
    feed_file = docs_dir / "feed.xml"
    with open(feed_file, "w") as f:
        f.write(feed_content)
    
    print(f"RSS feed saved to {feed_file}")


if __name__ == "__main__":
    data = load_data()
    if data:
        feed = create_rss_feed(data)
        save_rss_feed(feed)
    else:
        print("No data found in data.json")