"""Tests for error recovery and monitoring."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.errors.recovery import (
    HealthCheck,
    HealthStatus,
    ProviderHealth,
    RecoveryAttempt,
    RecoveryMonitor,
    RecoveryStrategy,
    get_recovery_monitor,
)


class TestHealthStatus:
    """Test health status enum."""

    def test_status_values(self):
        """Test health status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestHealthCheck:
    """Test health check model."""

    def test_health_check_creation(self):
        """Test creating a health check."""
        check = HealthCheck(
            provider="openai",
            url="https://api.openai.com/v1/models",
            status=HealthStatus.HEALTHY,
            response_time_ms=150,
            error_message=None,
        )
        assert check.provider == "openai"
        assert check.url == "https://api.openai.com/v1/models"
        assert check.status == HealthStatus.HEALTHY
        assert check.response_time_ms == 150
        assert check.error_message is None
        assert isinstance(check.timestamp, datetime)

    def test_health_check_with_error(self):
        """Test health check with error."""
        check = HealthCheck(
            provider="anthropic",
            url="https://api.anthropic.com",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=None,
            error_message="Connection timeout",
        )
        assert check.status == HealthStatus.UNHEALTHY
        assert check.error_message == "Connection timeout"
        assert check.response_time_ms is None


class TestProviderHealth:
    """Test provider health tracking."""

    def test_provider_health_creation(self):
        """Test creating provider health."""
        health = ProviderHealth(
            provider="openai",
            current_status=HealthStatus.HEALTHY,
            consecutive_failures=0,
            last_success=datetime.now(UTC),
            last_failure=None,
            success_rate=0.95,
            avg_response_time_ms=200,
        )
        assert health.provider == "openai"
        assert health.current_status == HealthStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.success_rate == 0.95

    def test_is_recoverable(self):
        """Test checking if provider is recoverable."""
        # Healthy provider
        health = ProviderHealth(
            provider="test",
            current_status=HealthStatus.HEALTHY,
            consecutive_failures=0,
        )
        assert health.is_recoverable() is True
        
        # Degraded but recoverable
        health.current_status = HealthStatus.DEGRADED
        health.consecutive_failures = 5
        assert health.is_recoverable() is True
        
        # Too many failures
        health.consecutive_failures = 11
        assert health.is_recoverable() is False

    def test_update_with_success(self):
        """Test updating health with successful check."""
        health = ProviderHealth(
            provider="test",
            current_status=HealthStatus.DEGRADED,
            consecutive_failures=3,
        )
        
        check = HealthCheck(
            provider="test",
            url="https://test.com",
            status=HealthStatus.HEALTHY,
            response_time_ms=100,
        )
        
        health.update_with_check(check)
        assert health.current_status == HealthStatus.HEALTHY
        assert health.consecutive_failures == 0
        assert health.last_success is not None

    def test_update_with_failure(self):
        """Test updating health with failed check."""
        health = ProviderHealth(
            provider="test",
            current_status=HealthStatus.HEALTHY,
            consecutive_failures=0,
        )
        
        check = HealthCheck(
            provider="test",
            url="https://test.com",
            status=HealthStatus.UNHEALTHY,
            error_message="Connection failed",
        )
        
        health.update_with_check(check)
        assert health.current_status == HealthStatus.UNHEALTHY
        assert health.consecutive_failures == 1
        assert health.last_failure is not None


class TestRecoveryAttempt:
    """Test recovery attempt model."""

    def test_recovery_attempt_creation(self):
        """Test creating recovery attempt."""
        attempt = RecoveryAttempt(
            provider="openai",
            strategy=RecoveryStrategy.RETRY,
            success=True,
            error_message=None,
            duration_ms=500,
        )
        assert attempt.provider == "openai"
        assert attempt.strategy == RecoveryStrategy.RETRY
        assert attempt.success is True
        assert attempt.duration_ms == 500


class TestRecoveryMonitor:
    """Test recovery monitor."""

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = MagicMock()
        config.error_handling.max_retries = 3
        config.error_handling.retry_delay = 60
        config.error_handling.recovery_check_interval = 3600
        return config

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config):
        """Test monitor initialization."""
        monitor = RecoveryMonitor(config=mock_config)
        assert monitor.config == mock_config
        assert monitor.provider_health == {}
        assert monitor.recovery_history == []

    @pytest.mark.asyncio
    async def test_check_provider_health_success(self, mock_config):
        """Test successful health check."""
        monitor = RecoveryMonitor(config=mock_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = MagicMock(total_seconds=MagicMock(return_value=0.15))
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            check = await monitor.check_provider_health("openai", "https://api.openai.com")
            assert check.status == HealthStatus.HEALTHY
            assert check.response_time_ms == 150
            assert check.error_message is None

    @pytest.mark.asyncio
    async def test_check_provider_health_failure(self, mock_config):
        """Test failed health check."""
        monitor = RecoveryMonitor(config=mock_config)
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectTimeout("Connection timeout")
            
            check = await monitor.check_provider_health("openai", "https://api.openai.com")
            assert check.status == HealthStatus.UNHEALTHY
            assert check.response_time_ms is None
            assert "Connection timeout" in check.error_message

    @pytest.mark.asyncio
    async def test_attempt_recovery_retry_strategy(self, mock_config):
        """Test recovery with retry strategy."""
        monitor = RecoveryMonitor(config=mock_config)
        
        # Set up unhealthy provider
        monitor.provider_health["openai"] = ProviderHealth(
            provider="openai",
            current_status=HealthStatus.UNHEALTHY,
            consecutive_failures=2,
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = MagicMock(total_seconds=MagicMock(return_value=0.2))
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            attempt = await monitor.attempt_recovery(
                provider="openai",
                url="https://api.openai.com",
                strategy=RecoveryStrategy.RETRY,
            )
            assert attempt.success is True
            assert attempt.strategy == RecoveryStrategy.RETRY
            
            # Check that health was updated
            assert monitor.provider_health["openai"].current_status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_attempt_recovery_backoff_strategy(self, mock_config):
        """Test recovery with exponential backoff."""
        monitor = RecoveryMonitor(config=mock_config)
        
        monitor.provider_health["openai"] = ProviderHealth(
            provider="openai",
            current_status=HealthStatus.UNHEALTHY,
            consecutive_failures=3,
        )
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.elapsed = MagicMock(total_seconds=MagicMock(return_value=0.2))
            
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_response
                
                attempt = await monitor.attempt_recovery(
                    provider="openai",
                    url="https://api.openai.com",
                    strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                )
                
                # Should have slept with exponential backoff (2^3 = 8 seconds)
                mock_sleep.assert_called_once_with(8)
                assert attempt.success is True

    @pytest.mark.asyncio
    async def test_monitor_all_providers(self, mock_config):
        """Test monitoring all providers."""
        monitor = RecoveryMonitor(config=mock_config)
        
        providers = [
            ("openai", "https://api.openai.com"),
            ("anthropic", "https://api.anthropic.com"),
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = MagicMock(total_seconds=MagicMock(return_value=0.1))
        
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            results = await monitor.monitor_all_providers(providers)
            assert len(results) == 2
            assert all(check.status == HealthStatus.HEALTHY for check in results)
            assert len(monitor.provider_health) == 2

    @pytest.mark.asyncio
    async def test_get_provider_status(self, mock_config):
        """Test getting provider status."""
        monitor = RecoveryMonitor(config=mock_config)
        
        # Unknown provider
        status = monitor.get_provider_status("unknown")
        assert status == HealthStatus.UNKNOWN
        
        # Known provider
        monitor.provider_health["openai"] = ProviderHealth(
            provider="openai",
            current_status=HealthStatus.HEALTHY,
            consecutive_failures=0,
        )
        status = monitor.get_provider_status("openai")
        assert status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_generate_health_report(self, mock_config):
        """Test generating health report."""
        monitor = RecoveryMonitor(config=mock_config)
        
        # Add some provider health data
        monitor.provider_health["openai"] = ProviderHealth(
            provider="openai",
            current_status=HealthStatus.HEALTHY,
            consecutive_failures=0,
            success_rate=0.95,
        )
        monitor.provider_health["anthropic"] = ProviderHealth(
            provider="anthropic",
            current_status=HealthStatus.DEGRADED,
            consecutive_failures=3,
            success_rate=0.70,
        )
        
        # Add recovery attempts
        monitor.recovery_history.append(
            RecoveryAttempt(
                provider="anthropic",
                strategy=RecoveryStrategy.RETRY,
                success=True,
            )
        )
        
        report = monitor.generate_health_report()
        assert "# Provider Health Report" in report
        assert "openai" in report
        assert "HEALTHY" in report
        assert "anthropic" in report
        assert "DEGRADED" in report
        assert "Recovery Attempts" in report


class TestGetRecoveryMonitor:
    """Test recovery monitor singleton."""

    def test_singleton_pattern(self):
        """Test that get_recovery_monitor returns the same instance."""
        monitor1 = get_recovery_monitor()
        monitor2 = get_recovery_monitor()
        assert monitor1 is monitor2