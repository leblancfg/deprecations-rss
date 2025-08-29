"""Test for LLM analyzer module import and basic functionality."""

import os
import pytest
from unittest.mock import patch, MagicMock


def test_llm_analyzer_import():
    """Test that LLM analyzer can be imported without errors."""
    from src.llm_analyzer import LLMAnalyzer

    assert LLMAnalyzer is not None


def test_hash_item_import():
    """Test that hash_item can be imported from main module."""
    from src.main import hash_item

    # Test basic hashing functionality
    item = {
        "provider": "TestProvider",
        "model_id": "test-model-1",
        "shutdown_date": "2025-01-01",
        "deprecation_context": "Test deprecation",
        "url": "https://example.com",
    }

    hash1 = hash_item(item)
    assert isinstance(hash1, str)
    assert len(hash1) == 16  # SHA256 truncated to 16 chars

    # Same content should produce same hash
    hash2 = hash_item(item)
    assert hash1 == hash2

    # Different content should produce different hash
    item["model_id"] = "test-model-2"
    hash3 = hash_item(item)
    assert hash1 != hash3


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
@patch("instructor.from_anthropic")
def test_llm_analyzer_initialization(mock_instructor):
    """Test LLM analyzer can be initialized with API key."""
    from src.llm_analyzer import LLMAnalyzer

    # Mock the instructor client
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    analyzer = LLMAnalyzer()
    assert analyzer.client == mock_client
    assert analyzer.model_name == "claude-3-5-haiku-latest"


def test_llm_analyzer_requires_api_key():
    """Test LLM analyzer raises error without API key."""
    from src.llm_analyzer import LLMAnalyzer

    # Clear any existing API keys
    env_backup = {}
    for key in ["ANTHROPIC_API_KEY", "ANTHROPIC_API_TOKEN"]:
        if key in os.environ:
            env_backup[key] = os.environ[key]
            del os.environ[key]

    try:
        with pytest.raises(
            ValueError,
            match="ANTHROPIC_API_KEY or ANTHROPIC_API_TOKEN environment variable required",
        ):
            LLMAnalyzer()
    finally:
        # Restore environment
        for key, value in env_backup.items():
            os.environ[key] = value


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
@patch("instructor.from_anthropic")
def test_llm_analyzer_batch_processing(mock_instructor):
    """Test LLM analyzer can process a batch of items."""
    from src.llm_analyzer import LLMAnalyzer

    # Mock the instructor client and its behavior
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client

    # Mock the analysis result
    mock_analysis = MagicMock()
    mock_analysis.model_name = "test-model"
    mock_analysis.summary = "Test summary"
    mock_analysis.shutdown_date = "2025-01-01"
    mock_analysis.suggested_replacement = "new-model"
    mock_analysis.deprecation_reason = "Superseded by newer model"

    mock_client.messages.create.return_value = mock_analysis

    analyzer = LLMAnalyzer()

    # Test data
    items = [
        {
            "_hash": "test_hash_1",
            "provider": "TestProvider",
            "title": "Test Model Deprecation",
            "content": "The test-model will be deprecated on January 1, 2025.",
            "url": "https://example.com",
        }
    ]

    # Process batch
    enhanced = analyzer.analyze_batch(items, [])

    assert len(enhanced) == 1
    assert enhanced[0]["model_name"] == "test-model"
    assert enhanced[0]["summary"] == "Test summary"
    assert enhanced[0]["shutdown_date"] == "2025-01-01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
