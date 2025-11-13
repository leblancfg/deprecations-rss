"""Tests for LLM analyzer module."""

import os
from unittest.mock import patch

from src.llm_analyzer import LLMAnalyzer


def test_llm_analyzer_imports():
    """Test that LLMAnalyzer can be imported without errors."""
    assert LLMAnalyzer is not None


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_analyze_batch_empty_items():
    """Test analyze_batch with empty items list."""
    analyzer = LLMAnalyzer()
    result = analyzer.analyze_batch([])
    assert result == []


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
def test_analyze_batch_with_existing_data():
    """Test that analyze_batch can import hash_item from main without errors."""
    analyzer = LLMAnalyzer()

    items = []
    existing_data = [{"provider": "Test", "model_id": "test-1", "content": "test"}]

    result = analyzer.analyze_batch(items, existing_data)
    assert result == []
