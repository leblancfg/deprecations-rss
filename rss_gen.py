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
    
    # Add items for each deprecation notice
    for item_data in data:
        item = ET.SubElement(channel, "item")
        
        # Use the title if available, otherwise fallback to provider name
        title = item_data.get('title', f"{item_data['provider']} Deprecation")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = item_data["url"]
        
        # Build description with dates if available
        description_parts = []
        if 'announcement_date' in item_data and item_data['announcement_date']:
            description_parts.append(f"Announced: {item_data['announcement_date']}")
        if 'shutdown_date' in item_data and item_data['shutdown_date']:
            description_parts.append(f"Shutdown: {item_data['shutdown_date']}")
        
        content = item_data["content"]
        if len(content) > 2000:
            content = content[:2000] + "...\n\n[Content truncated. Visit the link for full details.]"
        
        if description_parts:
            description = " | ".join(description_parts) + "\n\n" + content
        else:
            description = content
            
        ET.SubElement(item, "description").text = description
        ET.SubElement(item, "pubDate").text = datetime.fromisoformat(item_data["scraped_at"]).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # Create unique GUID for each deprecation
        guid_parts = [item_data['provider']]
        if 'title' in item_data:
            guid_parts.append(item_data['title'])
        if 'announcement_date' in item_data and item_data['announcement_date']:
            guid_parts.append(item_data['announcement_date'])
        guid_parts.append(item_data['scraped_at'][:10])  # Date only
        
        guid = "-".join(guid_parts).replace(" ", "_").replace(":", "")[:100]
        ET.SubElement(item, "guid", isPermaLink="false").text = guid
    
    # Convert to pretty XML string
    xml_str = ET.tostring(rss, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")


def save_rss_feed(feed_content):
    """Save RSS feed to docs/rss/v1/feed.xml."""
    # Create the full directory structure
    feed_dir = Path("docs/rss/v1")
    feed_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to the versioned path
    feed_file = feed_dir / "feed.xml"
    with open(feed_file, "w") as f:
        f.write(feed_content)
    
    # Also save to docs/feed.xml for backwards compatibility
    docs_feed = Path("docs/feed.xml")
    with open(docs_feed, "w") as f:
        f.write(feed_content)
    
    print(f"RSS feed saved to {feed_file} and {docs_feed}")


if __name__ == "__main__":
    data = load_data()
    if data:
        feed = create_rss_feed(data)
        save_rss_feed(feed)
    else:
        print("No data found in data.json")