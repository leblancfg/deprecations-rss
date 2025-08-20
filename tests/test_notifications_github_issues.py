"""Tests for GitHub issue creation."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.errors.analyzer import ErrorPattern, ErrorReport, ErrorStats
from src.errors.logger import ErrorCategory
from src.notifications.github_issues import (
    GitHubIssue,
    GitHubIssueCreator,
    IssueTemplate,
    get_github_creator,
)


class TestIssueTemplate:
    """Test issue template."""

    def test_error_report_template(self):
        """Test creating issue template from error report."""
        stats = ErrorStats(
            total_count=10,
            by_category={"network": 5, "parsing": 5},
        )
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            description="Network errors from OpenAI",
            category=ErrorCategory.NETWORK,
            provider="openai",
            occurrence_count=5,
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
        )
        report = ErrorReport(
            report_id="test_report",
            generated_at=datetime.now(UTC),
            time_window_hours=24,
            stats=stats,
            patterns=[pattern],
            critical_issues=["High network failure rate"],
            recommendations=["Check API endpoints"],
        )
        
        template = IssueTemplate.from_error_report(report)
        # Title uses critical issues first if available
        assert "Critical Errors Detected" in template.title
        assert "# Error Analysis Report" in template.body
        assert "network: 5" in template.body
        assert template.labels == ["bug", "automated", "error-report", "critical"]

    def test_provider_failure_template(self):
        """Test creating issue template for provider failure."""
        template = IssueTemplate.for_provider_failure(
            provider="openai",
            error_count=10,
            error_messages=["Connection timeout", "API error"],
            urls=["https://api.openai.com/v1/models"],
        )
        assert "openai" in template.title.lower()
        assert "provider failure" in template.title.lower()
        assert "10 errors detected" in template.body
        assert "Connection timeout" in template.body
        assert "https://api.openai.com/v1/models" in template.body
        assert "provider-issue" in template.labels

    def test_url_change_template(self):
        """Test creating issue template for URL change."""
        old_url = "https://old.api.com"
        suggested_url = "https://new.api.com"
        error_message = "404 Not Found"
        template = IssueTemplate.for_url_change(
            provider="anthropic",
            old_url=old_url,
            suggested_url=suggested_url,
            error_message=error_message,
        )
        assert "URL Change Detected" in template.title
        assert "anthropic" in template.title
        assert old_url in template.body
        assert suggested_url in template.body
        assert error_message in template.body
        assert "url-change" in template.labels


class TestGitHubIssue:
    """Test GitHub issue model."""

    def test_issue_creation(self):
        """Test creating a GitHub issue."""
        issue = GitHubIssue(
            title="Test Issue",
            body="Test body",
            labels=["bug", "test"],
            assignees=["user1"],
            milestone=1,
        )
        assert issue.title == "Test Issue"
        assert issue.body == "Test body"
        assert issue.labels == ["bug", "test"]
        assert issue.assignees == ["user1"]
        assert issue.milestone == 1

    def test_to_api_payload(self):
        """Test converting issue to API payload."""
        issue = GitHubIssue(
            title="Test Issue",
            body="Test body",
            labels=["bug"],
        )
        payload = issue.to_api_payload()
        assert payload["title"] == "Test Issue"
        assert payload["body"] == "Test body"
        assert payload["labels"] == ["bug"]
        assert "assignees" not in payload  # None should be excluded
        assert "milestone" not in payload


class TestGitHubIssueCreator:
    """Test GitHub issue creator."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.github.token = "ghp_test123"
        config.github.repository = "user/repo"
        config.github.labels = ["bug", "automated"]
        return config

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config):
        """Test issue creator initialization."""
        creator = GitHubIssueCreator(config=mock_config)
        assert creator.config == mock_config
        assert creator.repo_owner == "user"
        assert creator.repo_name == "repo"
        assert creator._existing_issues == set()

    @pytest.mark.asyncio
    async def test_check_duplicate_no_existing(self, mock_config):
        """Test checking for duplicate when no existing issues."""
        creator = GitHubIssueCreator(config=mock_config)
        
        with patch.object(creator, "_fetch_existing_issues", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []
            
            is_duplicate = await creator.check_duplicate("Test Issue")
            assert is_duplicate is False
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_duplicate_with_existing(self, mock_config):
        """Test checking for duplicate with existing issue."""
        creator = GitHubIssueCreator(config=mock_config)
        creator._existing_issues = {"existing issue", "another issue"}
        
        with patch.object(creator, "_fetch_existing_issues", new_callable=AsyncMock):
            # Check exact match
            is_duplicate = await creator.check_duplicate("Existing Issue")
            assert is_duplicate is True
            
            # Check partial match
            is_duplicate = await creator.check_duplicate("This is an existing issue case")
            assert is_duplicate is True
            
            # Check no match
            is_duplicate = await creator.check_duplicate("Completely New Issue")
            assert is_duplicate is False

    @pytest.mark.asyncio
    async def test_create_issue_success(self, mock_config):
        """Test successful issue creation."""
        creator = GitHubIssueCreator(config=mock_config)
        
        issue = GitHubIssue(
            title="Test Issue",
            body="Test body",
            labels=["bug"],
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 123,
            "html_url": "https://github.com/user/repo/issues/123",
        }
        
        with patch.object(creator.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await creator.create_issue(issue)
            assert result == {
                "number": 123,
                "html_url": "https://github.com/user/repo/issues/123",
            }
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/repos/user/repo/issues" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_issue_duplicate(self, mock_config):
        """Test issue creation when duplicate exists."""
        creator = GitHubIssueCreator(config=mock_config)
        creator._existing_issues = {"test issue"}
        
        issue = GitHubIssue(
            title="Test Issue",
            body="Test body",
            labels=["bug"],
        )
        
        with patch.object(creator, "_fetch_existing_issues", new_callable=AsyncMock):
            result = await creator.create_issue(issue)
            assert result is None

    @pytest.mark.asyncio
    async def test_create_issue_from_report(self, mock_config):
        """Test creating issue from error report."""
        creator = GitHubIssueCreator(config=mock_config)
        
        report = ErrorReport(
            report_id="test_report",
            generated_at=datetime.now(UTC),
            time_window_hours=24,
            stats=ErrorStats(total_count=10),
            patterns=[],
            critical_issues=["High error rate"],
            recommendations=["Check API"],
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"number": 124}
        
        with patch.object(creator.client, "post", new_callable=AsyncMock) as mock_post:
            with patch.object(creator, "_fetch_existing_issues", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = []
                mock_post.return_value = mock_response
                
                result = await creator.create_issue_from_report(report)
                assert result == {"number": 124}

    @pytest.mark.asyncio
    async def test_fetch_existing_issues(self, mock_config):
        """Test fetching existing issues."""
        creator = GitHubIssueCreator(config=mock_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"title": "Issue 1", "state": "open"},
            {"title": "Issue 2", "state": "open"},
        ]
        
        with patch.object(creator.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            issues = await creator._fetch_existing_issues()
            assert len(issues) == 2
            assert issues[0]["title"] == "Issue 1"

    @pytest.mark.asyncio
    async def test_no_token_raises_error(self):
        """Test that missing token raises error."""
        config = MagicMock()
        config.github.token = None
        config.github.repository = "user/repo"
        
        with pytest.raises(ValueError, match="GitHub token not configured"):
            GitHubIssueCreator(config=config)

    @pytest.mark.asyncio
    async def test_no_repository_raises_error(self):
        """Test that missing repository raises error."""
        config = MagicMock()
        config.github.token = "ghp_test"
        config.github.repository = None
        
        with pytest.raises(ValueError, match="GitHub repository not configured"):
            GitHubIssueCreator(config=config)


class TestGetGitHubCreator:
    """Test GitHub creator singleton."""

    def test_singleton_pattern(self):
        """Test that get_github_creator returns the same instance."""
        creator1 = get_github_creator()
        creator2 = get_github_creator()
        assert creator1 is creator2