"""
Circuit Breaker pattern implementation for fault tolerance.

Prevents cascading failures by temporarily blocking calls to failing services.
Implements three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery).
"""

import asyncio
import time
import functools
import logging
from enum import Enum
from typing import Callable, Optional, TypeVar
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit is open, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes in HALF_OPEN to close circuit
        timeout: Seconds to wait before moving to HALF_OPEN
        expected_exceptions: Exception types that count as failures
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    expected_exceptions: tuple = (Exception,)


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker(failure_threshold=3, timeout=30)

        @breaker.protected
        async def call_external_service():
            return await make_api_call()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        expected_exceptions: tuple = (Exception,),
        name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            success_threshold: Successes to close from HALF_OPEN
            timeout: Seconds before attempting recovery
            expected_exceptions: Exceptions that trigger circuit
            name: Circuit breaker name for logging
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exceptions=expected_exceptions
        )
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if self._state != CircuitState.OPEN:
            return False

        if self._last_failure_time is None:
            return False

        return time.time() - self._last_failure_time >= self.config.timeout

    def _record_success(self):
        """Record successful call."""
        with self._lock:
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"Circuit breaker '{self.name}': Success in HALF_OPEN "
                    f"({self._success_count}/{self.config.success_threshold})"
                )

                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}': CLOSED (recovered)")

    def _record_failure(self):
        """Record failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery attempt, back to OPEN
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning(
                    f"Circuit breaker '{self.name}': OPEN (recovery failed)"
                )
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(
                    f"Circuit breaker '{self.name}': OPEN "
                    f"(threshold {self.config.failure_threshold} exceeded)"
                )

    def _before_call(self):
        """Check state before allowing call."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return

            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(f"Circuit breaker '{self.name}': HALF_OPEN (testing recovery)")
                return

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service temporarily unavailable."
                )

    def protected(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker.

        Args:
            func: Function to protect

        Returns:
            Protected function
        """
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                self._before_call()

                try:
                    result = await func(*args, **kwargs)
                    self._record_success()
                    return result
                except self.config.expected_exceptions as e:
                    self._record_failure()
                    raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                self._before_call()

                try:
                    result = func(*args, **kwargs)
                    self._record_success()
                    return result
                except self.config.expected_exceptions as e:
                    self._record_failure()
                    raise

            return sync_wrapper

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            logger.info(f"Circuit breaker '{self.name}': Manually reset to CLOSED")

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.

        Returns:
            Dictionary with state and counters
        """
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                }
            }


# Pre-configured circuit breakers for common services
prometheus_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="prometheus"
)

elasticsearch_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="elasticsearch"
)

github_breaker = CircuitBreaker(
    failure_threshold=3,
    success_threshold=2,
    timeout=30.0,
    name="github"
)

jira_breaker = CircuitBreaker(
    failure_threshold=3,
    success_threshold=2,
    timeout=30.0,
    name="jira"
)


def get_all_breaker_stats() -> list:
    """
    Get statistics for all configured circuit breakers.

    Returns:
        List of stats dictionaries
    """
    return [
        prometheus_breaker.get_stats(),
        elasticsearch_breaker.get_stats(),
        github_breaker.get_stats(),
        jira_breaker.get_stats(),
    ]

