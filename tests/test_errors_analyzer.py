"""Tests for error aggregation and analysis."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.errors.analyzer import (
    ErrorAnalyzer,
    ErrorPattern,
    ErrorReport,
    ErrorStats,
    get_analyzer,
)
from src.errors.logger import ErrorCategory, ErrorSeverity, StructuredError


class TestErrorStats:
    """Test error statistics model."""

    def test_default_values(self):
        """Test default error stats values."""
        stats = ErrorStats()
        assert stats.total_count == 0
        assert stats.by_category == {}
        assert stats.by_provider == {}
        assert stats.by_severity == {}
        assert stats.recent_errors == []

    def test_with_values(self):
        """Test error stats with values."""
        stats = ErrorStats(
            total_count=10,
            by_category={"network": 5, "parsing": 5},
            by_provider={"openai": 7, "anthropic": 3},
            by_severity={"error": 8, "warning": 2},
            recent_errors=["error1", "error2"],
        )
        assert stats.total_count == 10
        assert stats.by_category["network"] == 5
        assert stats.by_provider["openai"] == 7
        assert stats.by_severity["error"] == 8


class TestErrorPattern:
    """Test error pattern detection model."""

    def test_pattern_creation(self):
        """Test creating an error pattern."""
        pattern = ErrorPattern(
            pattern_id="net_timeout_openai",
            description="Network timeouts for OpenAI API",
            category=ErrorCategory.NETWORK,
            provider="openai",
            error_codes=["TIMEOUT", "CONNECTION_TIMEOUT"],
            occurrence_count=5,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            affected_urls=["https://api.openai.com/v1/models"],
        )
        assert pattern.pattern_id == "net_timeout_openai"
        assert pattern.occurrence_count == 5
        assert len(pattern.affected_urls) == 1

    def test_is_critical(self):
        """Test critical pattern detection."""
        pattern = ErrorPattern(
            pattern_id="test",
            description="Test pattern",
            category=ErrorCategory.NETWORK,
            occurrence_count=3,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
        # Default threshold is 3, so this should be critical
        assert pattern.is_critical(threshold=3) is True
        assert pattern.is_critical(threshold=5) is False


class TestErrorReport:
    """Test error report generation."""

    def test_report_creation(self):
        """Test creating an error report."""
        report = ErrorReport(
            report_id="report_123",
            generated_at=datetime.now(UTC),
            time_window_hours=24,
            stats=ErrorStats(total_count=10),
            patterns=[],
            critical_issues=[],
            recommendations=["Check API endpoints"],
        )
        assert report.report_id == "report_123"
        assert report.time_window_hours == 24
        assert report.stats.total_count == 10
        assert len(report.recommendations) == 1

    def test_to_markdown(self):
        """Test converting report to markdown."""
        stats = ErrorStats(
            total_count=10,
            by_category={"network": 5, "parsing": 5},
            by_severity={"error": 8, "warning": 2},
        )
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            description="Test pattern",
            category=ErrorCategory.NETWORK,
            occurrence_count=5,
            first_seen=datetime.now(UTC) - timedelta(hours=2),
            last_seen=datetime.now(UTC),
        )
        report = ErrorReport(
            report_id="test_report",
            generated_at=datetime.now(UTC),
            time_window_hours=24,
            stats=stats,
            patterns=[pattern],
            critical_issues=["High network failure rate"],
            recommendations=["Check network connectivity"],
        )
        
        markdown = report.to_markdown()
        assert "# Error Analysis Report" in markdown
        assert "Total Errors: 10" in markdown
        assert "network: 5" in markdown
        assert "Test pattern" in markdown
        assert "High network failure rate" in markdown
        assert "Check network connectivity" in markdown


class TestErrorAnalyzer:
    """Test error analyzer."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.error_handling.failure_threshold = 3
        config.error_handling.threshold_window_hours = 24
        return config

    def test_initialization(self, mock_config):
        """Test analyzer initialization."""
        analyzer = ErrorAnalyzer(config=mock_config)
        assert analyzer.config == mock_config
        assert analyzer.errors == []
        assert analyzer._patterns == {}

    def test_add_error(self, mock_config):
        """Test adding errors to analyzer."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        error = StructuredError(
            message="Test error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
        )
        
        analyzer.add_error(error)
        assert len(analyzer.errors) == 1
        assert analyzer.errors[0] == error

    def test_get_recent_errors(self, mock_config):
        """Test getting recent errors."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        # Add old error
        old_error = StructuredError(
            message="Old error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            timestamp=datetime.now(UTC) - timedelta(hours=25),
        )
        analyzer.add_error(old_error)
        
        # Add recent error
        recent_error = StructuredError(
            message="Recent error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
        )
        analyzer.add_error(recent_error)
        
        recent = analyzer.get_recent_errors(hours=24)
        assert len(recent) == 1
        assert recent[0].message == "Recent error"

    def test_detect_patterns(self, mock_config):
        """Test pattern detection."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        # Add multiple similar errors
        for i in range(5):
            error = StructuredError(
                message=f"Network timeout {i}",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                provider="openai",
                error_code="TIMEOUT",
                url="https://api.openai.com/v1/models",
            )
            analyzer.add_error(error)
        
        patterns = analyzer.detect_patterns()
        assert len(patterns) > 0
        
        # Check that a pattern was detected for network/openai/TIMEOUT
        network_patterns = [p for p in patterns if p.category == ErrorCategory.NETWORK]
        assert len(network_patterns) > 0
        assert network_patterns[0].occurrence_count == 5

    def test_get_stats(self, mock_config):
        """Test getting error statistics."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        # Add various errors
        errors = [
            StructuredError(
                message="Network error",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                provider="openai",
            ),
            StructuredError(
                message="Parse error",
                category=ErrorCategory.PARSING,
                severity=ErrorSeverity.WARNING,
                provider="anthropic",
            ),
            StructuredError(
                message="Network error 2",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.ERROR,
                provider="openai",
            ),
        ]
        
        for error in errors:
            analyzer.add_error(error)
        
        stats = analyzer.get_stats(hours=24)
        assert stats.total_count == 3
        assert stats.by_category["network"] == 2
        assert stats.by_category["parsing"] == 1
        assert stats.by_provider["openai"] == 2
        assert stats.by_provider["anthropic"] == 1
        assert stats.by_severity["error"] == 2
        assert stats.by_severity["warning"] == 1

    def test_generate_report(self, mock_config):
        """Test generating error report."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        # Add errors to trigger patterns
        for i in range(4):
            error = StructuredError(
                message=f"Critical error {i}",
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.CRITICAL,
                provider="openai",
                error_code="CRITICAL_FAILURE",
            )
            analyzer.add_error(error)
        
        report = analyzer.generate_report(hours=24)
        assert report.stats.total_count == 4
        assert len(report.patterns) > 0
        assert len(report.critical_issues) > 0  # Should have critical issues
        assert len(report.recommendations) > 0

    def test_clear_old_errors(self, mock_config):
        """Test clearing old errors."""
        analyzer = ErrorAnalyzer(config=mock_config)
        
        # Add old and new errors
        old_error = StructuredError(
            message="Old error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            timestamp=datetime.now(UTC) - timedelta(days=8),
        )
        new_error = StructuredError(
            message="New error",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
        )
        
        analyzer.add_error(old_error)
        analyzer.add_error(new_error)
        
        assert len(analyzer.errors) == 2
        
        analyzer.clear_old_errors(days=7)
        assert len(analyzer.errors) == 1
        assert analyzer.errors[0].message == "New error"


class TestGetAnalyzer:
    """Test analyzer singleton."""

    def test_singleton_pattern(self):
        """Test that get_analyzer returns the same instance."""
        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()
        assert analyzer1 is analyzer2