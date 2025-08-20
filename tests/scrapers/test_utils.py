"""Tests for scraper utilities."""

from datetime import UTC, datetime

import pytest

from src.scrapers.utils import (
    clean_text,
    normalize_url,
    parse_date,
    validate_url,
)


class DescribeParseDateUtil:
    """Test date parsing utilities."""

    def it_parses_iso_format(self):
        result = parse_date("2024-03-15T10:30:00Z")
        assert result == datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)

    def it_parses_iso_date_only(self):
        result = parse_date("2024-03-15")
        assert result.date() == datetime(2024, 3, 15).date()

    def it_parses_rfc_format(self):
        result = parse_date("Wed, 15 Mar 2024 10:30:00 GMT")
        assert result == datetime(2024, 3, 15, 10, 30, 0, tzinfo=UTC)

    def it_parses_human_readable_format(self):
        # Test various human-readable formats
        dates = [
            "March 15, 2024",
            "15 March 2024",
            "Mar 15, 2024",
            "2024-03-15",
        ]
        for date_str in dates:
            result = parse_date(date_str)
            assert result.date() == datetime(2024, 3, 15).date()

    def it_handles_relative_dates(self):
        # These would need to be mocked for consistent testing
        with pytest.raises(ValueError, match="Could not parse date"):
            parse_date("tomorrow")

    def it_returns_none_for_invalid_dates(self):
        assert parse_date("not a date", raise_on_error=False) is None

    def it_raises_for_invalid_dates_when_requested(self):
        with pytest.raises(ValueError, match="Could not parse date"):
            parse_date("not a date", raise_on_error=True)


class DescribeCleanText:
    """Test text cleaning utilities."""

    def it_removes_extra_whitespace(self):
        text = "  This   has  \n\n  extra    spaces  "
        assert clean_text(text) == "This has extra spaces"

    def it_removes_html_tags(self):
        text = "<p>This is <strong>HTML</strong> content</p>"
        assert clean_text(text) == "This is HTML content"

    def it_handles_special_characters(self):
        text = "This has &nbsp; special &amp; characters &lt;&gt;"
        assert clean_text(text) == "This has special & characters <>"

    def it_preserves_sentence_structure(self):
        text = "First sentence. Second sentence! Third?"
        assert clean_text(text) == "First sentence. Second sentence! Third?"

    def it_handles_empty_strings(self):
        assert clean_text("") == ""
        assert clean_text("   ") == ""

    def it_handles_none_values(self):
        assert clean_text(None) == ""

    def it_optionally_preserves_line_breaks(self):
        text = "Line one\nLine two\nLine three"
        assert clean_text(text, preserve_lines=True) == "Line one\nLine two\nLine three"


class DescribeValidateUrl:
    """Test URL validation."""

    def it_validates_http_urls(self):
        assert validate_url("http://example.com") is True
        assert validate_url("https://example.com") is True

    def it_validates_complex_urls(self):
        urls = [
            "https://example.com/path/to/page",
            "https://example.com:8080/path",
            "https://sub.example.com/path?query=1&param=2",
            "https://example.com/path#anchor",
        ]
        for url in urls:
            assert validate_url(url) is True

    def it_rejects_invalid_urls(self):
        invalid_urls = [
            "not a url",
            "ftp://example.com",  # Only http/https
            "http://",
            "//example.com",
            "",
            None,
        ]
        for url in invalid_urls:
            assert validate_url(url) is False

    def it_optionally_requires_https(self):
        assert validate_url("https://example.com", require_https=True) is True
        assert validate_url("http://example.com", require_https=True) is False


class DescribeNormalizeUrl:
    """Test URL normalization."""

    def it_adds_missing_scheme(self):
        assert normalize_url("example.com") == "https://example.com"
        assert normalize_url("www.example.com") == "https://www.example.com"

    def it_preserves_existing_scheme(self):
        assert normalize_url("http://example.com") == "http://example.com"
        assert normalize_url("https://example.com") == "https://example.com"

    def it_removes_trailing_slashes(self):
        assert normalize_url("https://example.com/") == "https://example.com"
        assert normalize_url("https://example.com/path/") == "https://example.com/path"

    def it_preserves_query_params(self):
        url = "https://example.com/path?param=value"
        assert normalize_url(url) == url

    def it_handles_fragments(self):
        assert normalize_url("https://example.com#section") == "https://example.com#section"

    def it_lowercases_domain(self):
        assert normalize_url("https://EXAMPLE.COM/Path") == "https://example.com/Path"

    def it_handles_invalid_urls(self):
        assert normalize_url("") == ""
        assert normalize_url(None) == ""

