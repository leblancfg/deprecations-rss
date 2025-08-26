"""RSS feed generator with structured data in description."""

import json
import hashlib
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
    """Create RSS feed with structured data in description field."""
    # Create RSS root element
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    # Add channel metadata
    ET.SubElement(channel, "title").text = "AI Model Deprecations"
    ET.SubElement(channel, "link").text = "https://deprecations.info/"
    ET.SubElement(
        channel, "description"
    ).text = "RSS feed tracking deprecations across major AI providers"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    # Add items for each deprecation notice
    for item_data in data:
        item = ET.SubElement(channel, "item")

        # Build title with model name if available
        model_id = item_data.get('model_id', '')
        model_name = item_data.get('model_name', model_id)
        
        if model_name:
            title = f"{item_data['provider']}: {model_name}"
        elif "title" in item_data:
            title = item_data.get("title", f"{item_data['provider']} Deprecation")
        else:
            title = f"{item_data['provider']} Deprecation"

        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = item_data["url"]

        # Build structured description in plain text format
        description_parts = []

        # Add structured metadata in readable format
        description_parts.append(f"Provider: {item_data.get('provider', 'Unknown')}")

        # Add model info if available
        if "model_id" in item_data:
            description_parts.append(f"Model ID: {item_data['model_id']}")
        
        model_name = item_data.get('model_name', item_data.get('model_id', None))
        if model_name:
            model_name = item_data["model_name"]
        else:
            # Try to extract model name from title (format: "Provider: model_name")
            title = item_data.get("title", "")
            if ": " in title:
                potential_model = title.split(": ", 1)[1]
                # Only add if it looks like a model name (not generic like "Deprecations")
                if potential_model and "deprecation" not in potential_model.lower():
                    model_name = potential_model

        if model_name:
            description_parts.append(f"Model: {model_name}")

        # Add shutdown date if available
        if "shutdown_date" in item_data and item_data["shutdown_date"]:
            description_parts.append(f"Shutdown Date: {item_data['shutdown_date']}")
        elif "announcement_date" in item_data and item_data["announcement_date"]:
            description_parts.append(
                f"Announcement Date: {item_data['announcement_date']}"
            )

        # Add suggested replacement if available and not placeholder
        if "suggested_replacement" in item_data and item_data["suggested_replacement"]:
            if not item_data["suggested_replacement"].startswith("<"):
                description_parts.append(
                    f"Replacement: {item_data['suggested_replacement']}"
                )

        # Add deprecation reason if available and not placeholder
        if "deprecation_reason" in item_data and item_data["deprecation_reason"]:
            if not item_data["deprecation_reason"].startswith("<"):
                description_parts.append(f"Reason: {item_data['deprecation_reason']}")

        # Add observation dates
        if "first_observed" in item_data:
            description_parts.append(f"First Observed: {item_data['first_observed']}")

        if "last_observed" in item_data:
            description_parts.append(f"Last Observed: {item_data['last_observed']}")

        # Add separator before content
        description_parts.append("")  # Empty line

        # Add summary or original content
        if "summary" in item_data:
            description_parts.append(item_data["summary"])
        elif "deprecation_context" in item_data and item_data["deprecation_context"]:
            # Use first 500 chars of context
            context = item_data["deprecation_context"][:500]
            if len(item_data["deprecation_context"]) > 500:
                context += "..."
            description_parts.append(context)
        else:
            # Use the original content
            original_content = item_data.get("raw_content") or item_data.get(
                "content", ""
            )
            if original_content:
                description_parts.append(original_content)

        # Join all parts with newlines for readability
        description = "\n".join(description_parts)
        ET.SubElement(item, "description").text = description

        # Publication date
        if "scraped_at" in item_data:
            ET.SubElement(item, "pubDate").text = datetime.fromisoformat(
                item_data["scraped_at"]
            ).strftime("%a, %d %b %Y %H:%M:%S GMT")
        else:
            ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

        # Create unique GUID
        guid_parts = [item_data["provider"]]
        if "model_id" in item_data:
            guid_parts.append(item_data["model_id"])
        elif "model_name" in item_data:
            guid_parts.append(item_data["model_name"])
        elif "title" in item_data:
            guid_parts.append(item_data["title"])
        if "shutdown_date" in item_data and item_data["shutdown_date"]:
            guid_parts.append(item_data["shutdown_date"])

        content_hash = hashlib.sha256(
            str(item_data.get("content", "")).encode()
        ).hexdigest()[:8]
        guid_parts.append(content_hash)

        guid = (
            "-".join(str(p) for p in guid_parts)
            .replace(" ", "_")
            .replace(":", "")[:100]
        )
        ET.SubElement(item, "guid", isPermaLink="false").text = guid

    # Convert to pretty XML string
    xml_str = ET.tostring(rss, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")


def save_rss_feed(feed_content):
    """Save RSS feed to docs/v1/feed.xml."""
    # Create the v1 directory
    feed_dir = Path("docs/v1")
    feed_dir.mkdir(parents=True, exist_ok=True)

    # Save to the v1 path
    feed_file = feed_dir / "feed.xml"
    with open(feed_file, "w") as f:
        f.write(feed_content)

    print(f"RSS feed saved to {feed_file}")


if __name__ == "__main__":
    data = load_data()
    if data:
        feed = create_rss_feed(data)
        save_rss_feed(feed)
        print(f"Generated RSS feed with {len(data)} items")
    else:
        print("No data found in data.json")
