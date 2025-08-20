"""Error recovery and monitoring system."""

import asyncio
from datetime import UTC, datetime
from enum import Enum
from functools import lru_cache

import httpx
from pydantic import BaseModel, Field

from src.config import Settings, get_settings


class HealthStatus(Enum):
    """Health status for providers."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Recovery strategies for failed providers."""

    RETRY = "retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK = "fallback"


class HealthCheck(BaseModel):
    """Result of a health check."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    url: str
    status: HealthStatus
    response_time_ms: int | None = None
    error_message: str | None = None


class ProviderHealth(BaseModel):
    """Health tracking for a provider."""

    provider: str
    current_status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    success_rate: float = 1.0
    avg_response_time_ms: float | None = None
    health_checks: list[HealthCheck] = Field(default_factory=list)

    def is_recoverable(self) -> bool:
        """Check if provider is still recoverable."""
        # Consider unrecoverable after too many consecutive failures
        return self.consecutive_failures < 10

    def update_with_check(self, check: HealthCheck) -> None:
        """Update health status with a new check."""
        self.health_checks.append(check)

        # Keep only last 100 checks
        if len(self.health_checks) > 100:
            self.health_checks = self.health_checks[-100:]

        if check.status == HealthStatus.HEALTHY:
            self.current_status = HealthStatus.HEALTHY
            self.consecutive_failures = 0
            self.last_success = check.timestamp
        else:
            self.current_status = check.status
            self.consecutive_failures += 1
            self.last_failure = check.timestamp

        # Calculate success rate
        recent_checks = self.health_checks[-20:]  # Last 20 checks
        if recent_checks:
            successful = sum(
                1 for c in recent_checks if c.status == HealthStatus.HEALTHY
            )
            self.success_rate = successful / len(recent_checks)

        # Calculate average response time
        response_times = [
            c.response_time_ms
            for c in recent_checks
            if c.response_time_ms is not None
        ]
        if response_times:
            self.avg_response_time_ms = sum(response_times) / len(response_times)


class RecoveryAttempt(BaseModel):
    """Record of a recovery attempt."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    strategy: RecoveryStrategy
    success: bool
    error_message: str | None = None
    duration_ms: int | None = None


class RecoveryMonitor:
    """Monitors provider health and attempts recovery."""

    def __init__(self, config: Settings | None = None) -> None:
        """Initialize recovery monitor."""
        self.config = config or get_settings()
        self.provider_health: dict[str, ProviderHealth] = {}
        self.recovery_history: list[RecoveryAttempt] = []
        self.client = httpx.AsyncClient(timeout=10.0)

    async def check_provider_health(
        self, provider: str, url: str
    ) -> HealthCheck:
        """Check health of a provider."""
        check = HealthCheck(
            provider=provider,
            url=url,
            status=HealthStatus.UNKNOWN,
        )

        try:
            # Perform health check request
            response = await self.client.get(url)

            # Calculate response time
            response_time_ms = int(response.elapsed.total_seconds() * 1000)
            check.response_time_ms = response_time_ms

            # Determine health status
            if response.status_code == 200:
                check.status = HealthStatus.HEALTHY
            elif 400 <= response.status_code < 500:
                check.status = HealthStatus.DEGRADED
                check.error_message = f"HTTP {response.status_code}"
            else:
                check.status = HealthStatus.UNHEALTHY
                check.error_message = f"HTTP {response.status_code}"

        except httpx.TimeoutException as e:
            check.status = HealthStatus.UNHEALTHY
            check.error_message = f"Timeout: {str(e)}"
        except httpx.ConnectTimeout as e:
            check.status = HealthStatus.UNHEALTHY
            check.error_message = f"Connection timeout: {str(e)}"
        except Exception as e:
            check.status = HealthStatus.UNHEALTHY
            check.error_message = str(e)

        # Update provider health
        if provider not in self.provider_health:
            self.provider_health[provider] = ProviderHealth(provider=provider)

        self.provider_health[provider].update_with_check(check)

        return check

    async def attempt_recovery(
        self,
        provider: str,
        url: str,
        strategy: RecoveryStrategy = RecoveryStrategy.RETRY,
    ) -> RecoveryAttempt:
        """Attempt to recover a failed provider."""
        start_time = datetime.now(UTC)
        attempt = RecoveryAttempt(
            provider=provider,
            strategy=strategy,
            success=False,
        )

        try:
            if strategy == RecoveryStrategy.RETRY:
                # Simple retry
                check = await self.check_provider_health(provider, url)
                attempt.success = check.status == HealthStatus.HEALTHY

            elif strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                # Exponential backoff based on consecutive failures
                failures = self.provider_health.get(provider, ProviderHealth(provider=provider)).consecutive_failures
                wait_time = min(2 ** failures, 300)  # Max 5 minutes
                await asyncio.sleep(wait_time)

                check = await self.check_provider_health(provider, url)
                attempt.success = check.status == HealthStatus.HEALTHY

            elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                # Circuit breaker pattern
                health = self.provider_health.get(provider)
                if health and not health.is_recoverable():
                    attempt.error_message = "Circuit breaker open - too many failures"
                    return attempt

                check = await self.check_provider_health(provider, url)
                attempt.success = check.status == HealthStatus.HEALTHY

            else:  # FALLBACK
                # Fallback strategy would use alternative provider
                attempt.error_message = "Fallback strategy not implemented"

        except Exception as e:
            attempt.error_message = str(e)

        # Calculate duration
        duration = datetime.now(UTC) - start_time
        attempt.duration_ms = int(duration.total_seconds() * 1000)

        # Add to history
        self.recovery_history.append(attempt)

        return attempt

    async def monitor_all_providers(
        self, providers: list[tuple[str, str]]
    ) -> list[HealthCheck]:
        """Monitor health of all providers."""
        checks = []
        for provider, url in providers:
            check = await self.check_provider_health(provider, url)
            checks.append(check)
        return checks

    def get_provider_status(self, provider: str) -> HealthStatus:
        """Get current status of a provider."""
        if provider in self.provider_health:
            return self.provider_health[provider].current_status
        return HealthStatus.UNKNOWN

    def get_unhealthy_providers(self) -> list[str]:
        """Get list of unhealthy providers."""
        return [
            provider
            for provider, health in self.provider_health.items()
            if health.current_status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]

    def generate_health_report(self) -> str:
        """Generate a health report for all providers."""
        lines = [
            "# Provider Health Report",
            f"\n**Generated:** {datetime.now(UTC).isoformat()}",
            "\n## Provider Status",
        ]

        for provider, health in sorted(self.provider_health.items()):
            lines.append(f"\n### {provider}")
            lines.append(f"- **Status:** {health.current_status.value.upper()}")
            lines.append(f"- **Consecutive Failures:** {health.consecutive_failures}")
            lines.append(f"- **Success Rate:** {health.success_rate:.1%}")

            if health.avg_response_time_ms:
                lines.append(f"- **Avg Response Time:** {health.avg_response_time_ms:.0f}ms")

            if health.last_success:
                lines.append(f"- **Last Success:** {health.last_success.isoformat()}")

            if health.last_failure:
                lines.append(f"- **Last Failure:** {health.last_failure.isoformat()}")

        # Add recovery attempts
        recent_attempts = self.recovery_history[-10:]  # Last 10 attempts
        if recent_attempts:
            lines.append("\n## Recent Recovery Attempts")
            for attempt in recent_attempts:
                status = "✓" if attempt.success else "✗"
                lines.append(
                    f"- {status} {attempt.provider} ({attempt.strategy.value}) "
                    f"@ {attempt.timestamp.isoformat()}"
                )
                if attempt.error_message:
                    lines.append(f"  Error: {attempt.error_message}")

        return "\n".join(lines)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


@lru_cache(maxsize=1)
def get_recovery_monitor() -> RecoveryMonitor:
    """Get the singleton recovery monitor instance."""
    return RecoveryMonitor()
