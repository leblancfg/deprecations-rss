"""GitHub issue creation for error reporting."""

from functools import lru_cache
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.errors.analyzer import ErrorReport


class IssueTemplate(BaseModel):
    """Template for GitHub issues."""

    title: str
    body: str
    labels: list[str] = Field(default_factory=list)

    @classmethod
    def from_error_report(cls, report: ErrorReport) -> "IssueTemplate":
        """Create issue template from error report."""
        # Generate title from critical issues or patterns
        if report.critical_issues:
            title = f"Critical Errors Detected: {report.critical_issues[0][:50]}"
        elif report.patterns:
            title = f"Error Pattern: {report.patterns[0].description}"
        else:
            title = f"Error Report: {report.stats.total_count} errors in {report.time_window_hours}h"

        # Use the markdown report as body
        body = report.to_markdown()

        # Add footer with report metadata
        body += "\n\n---\n"
        body += "*This issue was automatically created by the error monitoring system.*\n"
        body += f"*Report ID: {report.report_id}*"

        labels = ["bug", "automated", "error-report"]

        # Add severity label if critical issues exist
        if report.critical_issues:
            labels.append("critical")

        return cls(title=title, body=body, labels=labels)

    @classmethod
    def for_provider_failure(
        cls,
        provider: str,
        error_count: int,
        error_messages: list[str],
        urls: list[str],
    ) -> "IssueTemplate":
        """Create issue template for provider failure."""
        title = f"Provider Failure: {provider} - {error_count} errors detected"

        body = f"# Provider Failure Report: {provider}\n\n"
        body += "## Summary\n"
        body += f"{error_count} errors detected for provider **{provider}**.\n\n"

        body += "## Error Messages\n"
        for msg in error_messages[:5]:  # Limit to 5 messages
            body += f"- {msg}\n"
        if len(error_messages) > 5:
            body += f"- ... and {len(error_messages) - 5} more\n"

        body += "\n## Affected URLs\n"
        for url in urls[:5]:  # Limit to 5 URLs
            body += f"- {url}\n"
        if len(urls) > 5:
            body += f"- ... and {len(urls) - 5} more\n"

        body += "\n## Recommended Actions\n"
        body += "1. Check if the provider's API is operational\n"
        body += "2. Verify API credentials and rate limits\n"
        body += "3. Review recent changes to the provider's API\n"
        body += "4. Consider implementing retry logic or fallback mechanisms\n"

        labels = ["bug", "automated", "provider-issue", provider.lower()]

        return cls(title=title, body=body, labels=labels)

    @classmethod
    def for_url_change(
        cls,
        provider: str,
        old_url: str,
        suggested_url: str | None,
        error_message: str,
    ) -> "IssueTemplate":
        """Create issue template for URL change detection."""
        title = f"URL Change Detected: {provider}"

        body = f"# URL Change Detection: {provider}\n\n"
        body += "## Summary\n"
        body += f"A potential URL change has been detected for provider **{provider}**.\n\n"

        body += "## Details\n"
        body += f"- **Old URL:** `{old_url}`\n"
        if suggested_url:
            body += f"- **Suggested URL:** `{suggested_url}`\n"
        body += f"- **Error:** {error_message}\n\n"

        body += "## Recommended Actions\n"
        body += "1. Verify the provider's current API documentation\n"
        body += "2. Update the scraper configuration with the new URL\n"
        body += "3. Test the new URL to ensure compatibility\n"
        body += "4. Update any related documentation\n"

        labels = ["bug", "automated", "url-change", provider.lower()]

        return cls(title=title, body=body, labels=labels)


class GitHubIssue(BaseModel):
    """GitHub issue model."""

    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] | None = None
    milestone: int | None = None

    def to_api_payload(self) -> dict[str, Any]:
        """Convert to GitHub API payload."""
        payload: dict[str, Any] = {
            "title": self.title,
            "body": self.body,
            "labels": self.labels,
        }

        if self.assignees:
            payload["assignees"] = self.assignees

        if self.milestone:
            payload["milestone"] = self.milestone

        return payload


class GitHubIssueCreator:
    """Creates GitHub issues for error reports."""

    def __init__(self, config: Settings | None = None) -> None:
        """Initialize GitHub issue creator."""
        self.config = config or get_settings()

        if not self.config.github.token:
            raise ValueError("GitHub token not configured")

        if not self.config.github.repository:
            raise ValueError("GitHub repository not configured")

        # Parse repository owner and name
        parts = self.config.github.repository.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repository format: {self.config.github.repository}")

        self.repo_owner = parts[0]
        self.repo_name = parts[1]

        # Set up HTTP client
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.config.github.token}",
                "Accept": "application/vnd.github.v3+json",
            }
        )

        # Cache for existing issues to avoid duplicates
        self._existing_issues: set[str] = set()

    async def check_duplicate(self, title: str) -> bool:
        """Check if an issue with similar title already exists."""
        # Fetch existing issues if not cached
        if not self._existing_issues:
            await self._fetch_existing_issues()

        # Check for similar titles (case-insensitive)
        title_lower = title.lower()
        for existing in self._existing_issues:
            if existing.lower() in title_lower or title_lower in existing.lower():
                return True

        return False

    async def _fetch_existing_issues(self) -> list[dict[str, Any]]:
        """Fetch existing open issues from the repository."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        params: dict[str, str | int] = {
            "state": "open",
            "labels": "automated",  # Only check automated issues
            "per_page": 100,
        }

        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                issues: list[dict[str, Any]] = response.json()
                self._existing_issues = {issue["title"] for issue in issues}
                return issues
        except Exception:
            pass  # Fail silently, allow issue creation

        return []

    async def create_issue(self, issue: GitHubIssue) -> dict[str, Any] | None:
        """Create a GitHub issue."""
        # Check for duplicates
        if await self.check_duplicate(issue.title):
            return None  # Skip duplicate

        # Add default labels
        if self.config.github.labels:
            issue.labels = list(set(issue.labels + self.config.github.labels))

        # Create the issue
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
        payload = issue.to_api_payload()

        try:
            response = await self.client.post(url, json=payload)
            if response.status_code == 201:
                created_issue: dict[str, Any] = response.json()
                # Add to cache
                self._existing_issues.add(issue.title)
                return created_issue
            else:
                # Log error but don't raise
                return None
        except Exception:
            return None  # Fail silently

    async def create_issue_from_report(self, report: ErrorReport) -> dict[str, Any] | None:
        """Create a GitHub issue from an error report."""
        template = IssueTemplate.from_error_report(report)
        issue = GitHubIssue(
            title=template.title,
            body=template.body,
            labels=template.labels,
        )
        return await self.create_issue(issue)

    async def create_provider_failure_issue(
        self,
        provider: str,
        error_count: int,
        error_messages: list[str],
        urls: list[str],
    ) -> dict[str, Any] | None:
        """Create an issue for provider failure."""
        template = IssueTemplate.for_provider_failure(
            provider=provider,
            error_count=error_count,
            error_messages=error_messages,
            urls=urls,
        )
        issue = GitHubIssue(
            title=template.title,
            body=template.body,
            labels=template.labels,
        )
        return await self.create_issue(issue)

    async def create_url_change_issue(
        self,
        provider: str,
        old_url: str,
        suggested_url: str | None,
        error_message: str,
    ) -> dict[str, Any] | None:
        """Create an issue for URL change detection."""
        template = IssueTemplate.for_url_change(
            provider=provider,
            old_url=old_url,
            suggested_url=suggested_url,
            error_message=error_message,
        )
        issue = GitHubIssue(
            title=template.title,
            body=template.body,
            labels=template.labels,
        )
        return await self.create_issue(issue)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


@lru_cache(maxsize=1)
def get_github_creator() -> GitHubIssueCreator | None:
    """Get the singleton GitHub issue creator."""
    try:
        return GitHubIssueCreator()
    except ValueError:
        # GitHub not configured
        return None
