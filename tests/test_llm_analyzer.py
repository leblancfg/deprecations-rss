"""Tests for LLM analyzer module."""

import pytest
from src.llm_analyzer import LLMAnalyzer


def test_llm_analyzer_imports():
    """Test that LLMAnalyzer can be imported and instantiated without errors."""
    # This will fail if there are import errors in the module
    assert LLMAnalyzer is not None


def test_analyze_batch_empty_items():
    """Test analyze_batch with empty items list."""
    # Skip API call by testing with empty items
    analyzer = LLMAnalyzer()
    result = analyzer.analyze_batch([])
    assert result == []


def test_analyze_batch_with_existing_data():
    """Test that analyze_batch can import hash_item from main without errors."""
    analyzer = LLMAnalyzer()

    # Create mock items and existing data
    items = []
    existing_data = [{"provider": "Test", "model_id": "test-1", "content": "test"}]

    # This will test the import path without making API calls
    result = analyzer.analyze_batch(items, existing_data)
    assert result == []
