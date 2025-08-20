"""Utility functions for scraping and parsing."""

import html
from datetime import UTC, datetime
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser


def parse_date(
    date_str: str | None,
    raise_on_error: bool = True,
) -> datetime | None:
    """
    Parse various date formats into datetime objects.

    Handles:
    - ISO format (2024-03-15T10:30:00Z)
    - RFC format (Wed, 15 Mar 2024 10:30:00 GMT)
    - Human-readable formats (March 15, 2024, etc.)

    Args:
        date_str: String to parse as date
        raise_on_error: Whether to raise exception on parse error

    Returns:
        Parsed datetime with timezone info, or None if parsing fails

    Raises:
        ValueError: If date cannot be parsed and raise_on_error is True
    """
    if not date_str:
        if raise_on_error:
            raise ValueError("Could not parse date: empty string")
        return None

    try:
        # Use dateutil parser which handles many formats
        dt = date_parser.parse(date_str)

        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt
    except (ValueError, TypeError) as e:
        if raise_on_error:
            raise ValueError(f"Could not parse date: {date_str}") from e
        return None


def clean_text(
    text: str | None,
    preserve_lines: bool = False,
) -> str:
    """
    Clean and normalize extracted text.

    - Removes HTML tags
    - Decodes HTML entities
    - Normalizes whitespace
    - Trims leading/trailing space

    Args:
        text: Text to clean
        preserve_lines: Whether to preserve line breaks

    Returns:
        Cleaned text string
    """
    if not text:
        return ""

    # Remove HTML tags
    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text()

    # Decode HTML entities
    text = html.unescape(text)

    if preserve_lines:
        # Normalize spaces within lines but preserve line breaks
        lines = text.split('\n')
        lines = [' '.join(line.split()) for line in lines]
        text = '\n'.join(lines)
    else:
        # Normalize all whitespace
        text = ' '.join(text.split())

    return text.strip()


def validate_url(url: str | None, require_https: bool = False) -> bool:
    """
    Validate that a string is a valid HTTP(S) URL.

    Args:
        url: URL string to validate
        require_https: Whether to require HTTPS scheme

    Returns:
        True if valid URL, False otherwise
    """
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Check basic requirements
        if not parsed.scheme or not parsed.netloc:
            return False

        # Check scheme
        if require_https:
            return parsed.scheme == "https"
        else:
            return parsed.scheme in ("http", "https")

    except Exception:
        return False


def normalize_url(url: str | None) -> str:
    """
    Normalize a URL for consistent comparison.

    - Adds missing scheme (defaults to https)
    - Lowercases domain
    - Removes trailing slashes from path

    Args:
        url: URL to normalize

    Returns:
        Normalized URL string, or empty string if invalid
    """
    if not url:
        return ""

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        parsed = urlparse(url)

        # Lowercase the domain
        netloc = parsed.netloc.lower()

        # Remove trailing slash from path
        path = parsed.path.rstrip("/")
        if not path:
            path = ""

        # Reconstruct URL
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))

        return normalized

    except Exception:
        return ""

