"""Error aggregation and analysis system."""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.errors.logger import ErrorCategory, StructuredError


class ErrorStats(BaseModel):
    """Statistics about errors."""

    total_count: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    recent_errors: list[str] = Field(default_factory=list)


class ErrorPattern(BaseModel):
    """Detected error pattern."""

    pattern_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    category: ErrorCategory
    provider: str | None = None
    error_codes: list[str] = Field(default_factory=list)
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    affected_urls: list[str] = Field(default_factory=list)

    def is_critical(self, threshold: int) -> bool:
        """Check if pattern is critical based on occurrence threshold."""
        return self.occurrence_count >= threshold


class ErrorReport(BaseModel):
    """Error analysis report."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    time_window_hours: int
    stats: ErrorStats
    patterns: list[ErrorPattern]
    critical_issues: list[str]
    recommendations: list[str]

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            "# Error Analysis Report",
            f"\n**Report ID:** {self.report_id}",
            f"**Generated:** {self.generated_at.isoformat()}",
            f"**Time Window:** {self.time_window_hours} hours",
            "\n## Summary Statistics",
            f"- Total Errors: {self.stats.total_count}",
        ]

        if self.stats.by_category:
            lines.append("\n### By Category")
            for category, count in sorted(self.stats.by_category.items()):
                lines.append(f"- {category}: {count}")

        if self.stats.by_provider:
            lines.append("\n### By Provider")
            for provider, count in sorted(self.stats.by_provider.items()):
                lines.append(f"- {provider}: {count}")

        if self.stats.by_severity:
            lines.append("\n### By Severity")
            for severity, count in sorted(self.stats.by_severity.items()):
                lines.append(f"- {severity}: {count}")

        if self.patterns:
            lines.append("\n## Detected Patterns")
            for pattern in self.patterns:
                lines.append(f"\n### {pattern.description}")
                lines.append(f"- **Category:** {pattern.category.value}")
                if pattern.provider:
                    lines.append(f"- **Provider:** {pattern.provider}")
                lines.append(f"- **Occurrences:** {pattern.occurrence_count}")
                lines.append(f"- **First Seen:** {pattern.first_seen.isoformat()}")
                lines.append(f"- **Last Seen:** {pattern.last_seen.isoformat()}")
                if pattern.error_codes:
                    lines.append(f"- **Error Codes:** {', '.join(pattern.error_codes)}")
                if pattern.affected_urls:
                    lines.append("- **Affected URLs:**")
                    for url in pattern.affected_urls[:5]:  # Limit to 5 URLs
                        lines.append(f"  - {url}")

        if self.critical_issues:
            lines.append("\n## Critical Issues")
            for issue in self.critical_issues:
                lines.append(f"- {issue}")

        if self.recommendations:
            lines.append("\n## Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)


class ErrorAnalyzer:
    """Analyzes errors to detect patterns and generate reports."""

    def __init__(self, config: Settings | None = None) -> None:
        """Initialize error analyzer."""
        self.config = config or get_settings()
        self.errors: list[StructuredError] = []
        self._patterns: dict[str, ErrorPattern] = {}

    def add_error(self, error: StructuredError) -> None:
        """Add an error to the analyzer."""
        self.errors.append(error)

    def get_recent_errors(self, hours: int = 24) -> list[StructuredError]:
        """Get errors from the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return [e for e in self.errors if e.timestamp >= cutoff]

    def detect_patterns(self, hours: int = 24) -> list[ErrorPattern]:
        """Detect error patterns in recent errors."""
        recent_errors = self.get_recent_errors(hours)
        patterns: dict[str, ErrorPattern] = {}

        # Group errors by category, provider, and error code
        pattern_groups: dict[tuple[str, str | None, str | None], list[StructuredError]] = (
            defaultdict(list)
        )

        for error in recent_errors:
            key = (error.category.value, error.provider, error.error_code)
            pattern_groups[key].append(error)

        # Create patterns for groups with multiple occurrences
        for (category_str, provider, error_code), errors in pattern_groups.items():
            if len(errors) >= 2:  # At least 2 occurrences to be a pattern
                pattern_key = f"{category_str}_{provider}_{error_code}"

                # Get unique URLs
                urls = list({e.url for e in errors if e.url})

                # Get all error codes
                codes = list({e.error_code for e in errors if e.error_code})

                # Create pattern description
                desc_parts = [category_str.replace("_", " ").title()]
                if provider:
                    desc_parts.append(f"from {provider}")
                if error_code:
                    desc_parts.append(f"({error_code})")
                description = " ".join(desc_parts)

                pattern = ErrorPattern(
                    pattern_id=pattern_key,
                    description=description,
                    category=ErrorCategory(category_str),
                    provider=provider,
                    error_codes=codes,
                    occurrence_count=len(errors),
                    first_seen=min(e.timestamp for e in errors),
                    last_seen=max(e.timestamp for e in errors),
                    affected_urls=urls,
                )
                patterns[pattern_key] = pattern

        return list(patterns.values())

    def get_stats(self, hours: int = 24) -> ErrorStats:
        """Get error statistics for the specified time window."""
        recent_errors = self.get_recent_errors(hours)

        stats = ErrorStats(
            total_count=len(recent_errors),
            by_category=dict(Counter(e.category.value for e in recent_errors)),
            by_provider=dict(Counter(e.provider for e in recent_errors if e.provider)),
            by_severity=dict(Counter(e.severity.value for e in recent_errors)),
            recent_errors=[e.error_id for e in recent_errors[-10:]],  # Last 10 error IDs
        )

        return stats

    def generate_report(self, hours: int = 24) -> ErrorReport:
        """Generate a comprehensive error analysis report."""
        stats = self.get_stats(hours)
        patterns = self.detect_patterns(hours)

        # Identify critical issues
        critical_issues = []
        threshold = self.config.error_handling.failure_threshold

        for pattern in patterns:
            if pattern.is_critical(threshold):
                critical_issues.append(
                    f"{pattern.description}: {pattern.occurrence_count} occurrences"
                )

        # Check for high error rates
        if stats.total_count > threshold * 5:  # Arbitrary multiplier for overall volume
            critical_issues.append(f"High overall error rate: {stats.total_count} errors")

        # Generate recommendations
        recommendations = []

        # Network errors
        network_count = stats.by_category.get("network", 0)
        if network_count > threshold:
            recommendations.append(
                "High network error rate detected. Check network connectivity and API endpoints."
            )

        # Provider-specific issues
        for provider, count in stats.by_provider.items():
            if count >= threshold:
                recommendations.append(
                    f"Multiple errors from {provider}. Check API status and rate limits."
                )

        # Critical severity
        critical_count = stats.by_severity.get("critical", 0)
        if critical_count > 0:
            recommendations.append(
                f"{critical_count} critical errors detected. Immediate attention required."
            )

        # Pattern-based recommendations
        for pattern in patterns:
            if pattern.category == ErrorCategory.RATE_LIMIT:
                recommendations.append(
                    f"Rate limiting detected for {pattern.provider or 'provider'}. "
                    "Consider implementing backoff strategies."
                )
            elif pattern.category == ErrorCategory.AUTHENTICATION:
                recommendations.append(
                    f"Authentication issues with {pattern.provider or 'provider'}. "
                    "Verify API credentials."
                )

        return ErrorReport(
            time_window_hours=hours,
            stats=stats,
            patterns=sorted(patterns, key=lambda p: p.occurrence_count, reverse=True),
            critical_issues=critical_issues,
            recommendations=list(dict.fromkeys(recommendations)),  # Remove duplicates
        )

    def clear_old_errors(self, days: int = 7) -> None:
        """Remove errors older than specified days."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        self.errors = [e for e in self.errors if e.timestamp >= cutoff]


@lru_cache(maxsize=1)
def get_analyzer() -> ErrorAnalyzer:
    """Get the singleton analyzer instance."""
    return ErrorAnalyzer()
