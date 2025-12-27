"""
Tests for circuit breaker pattern implementation.

Verifies circuit state transitions and failure protection.
"""

import pytest
import asyncio
import time
from src.adapt_rca.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerError,
)


def test_circuit_breaker_initial_state():
    """Test circuit breaker starts in CLOSED state."""
    breaker = CircuitBreaker(name="test")
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_stays_closed_on_success():
    """Test circuit breaker stays CLOSED with successful calls."""
    breaker = CircuitBreaker(failure_threshold=3, name="test")
    
    @breaker.protected
    def successful_call():
        return "success"
    
    for _ in range(10):
        result = successful_call()
        assert result == "success"
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after failure threshold."""
    breaker = CircuitBreaker(failure_threshold=3, name="test")
    
    @breaker.protected
    def failing_call():
        raise ConnectionError("Service unavailable")
    
    # First 3 failures should open the circuit
    for i in range(3):
        with pytest.raises(ConnectionError):
            failing_call()
    
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3


def test_circuit_breaker_blocks_when_open():
    """Test circuit breaker blocks calls when OPEN."""
    breaker = CircuitBreaker(failure_threshold=2, name="test")
    
    @breaker.protected
    def failing_call():
        raise ConnectionError("Service unavailable")
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            failing_call()
    
    assert breaker.state == CircuitState.OPEN
    
    # Next call should raise CircuitBreakerError immediately
    with pytest.raises(CircuitBreakerError) as exc_info:
        failing_call()
    
    assert "OPEN" in str(exc_info.value)


def test_circuit_breaker_half_open_after_timeout():
    """Test circuit breaker enters HALF_OPEN after timeout."""
    breaker = CircuitBreaker(
        failure_threshold=2,
        timeout=0.1,  # 100ms timeout
        name="test"
    )
    
    @breaker.protected
    def call():
        return "success"
    
    # Open the circuit
    @breaker.protected
    def failing_call():
        raise ConnectionError("Fail")
    
    for _ in range(2):
        with pytest.raises(ConnectionError):
            failing_call()
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(0.15)
    
    # Next call should trigger HALF_OPEN
    result = call()
    assert result == "success"


def test_circuit_breaker_closes_after_success_threshold():
    """Test circuit breaker closes after success threshold in HALF_OPEN."""
    breaker = CircuitBreaker(
        failure_threshold=2,
        success_threshold=2,
        timeout=0.1,
        name="test"
    )
    
    @breaker.protected
    def call(should_fail=False):
        if should_fail:
            raise ConnectionError("Fail")
        return "success"
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            call(should_fail=True)
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(0.15)
    
    # Make successful calls to close circuit
    call()  # First success in HALF_OPEN
    call()  # Second success should close circuit
    
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_reopens_on_failure_in_half_open():
    """Test circuit breaker reopens if call fails in HALF_OPEN."""
    breaker = CircuitBreaker(
        failure_threshold=2,
        timeout=0.1,
        name="test"
    )
    
    @breaker.protected
    def call(should_fail=False):
        if should_fail:
            raise ConnectionError("Fail")
        return "success"
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            call(should_fail=True)
    
    assert breaker.state == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(0.15)
    
    # Fail during HALF_OPEN
    with pytest.raises(ConnectionError):
        call(should_fail=True)
    
    # Should be back to OPEN
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_async_success():
    """Test circuit breaker with async functions."""
    breaker = CircuitBreaker(failure_threshold=3, name="test_async")
    
    @breaker.protected
    async def async_call():
        await asyncio.sleep(0.01)
        return "async success"
    
    result = await async_call()
    assert result == "async success"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_async_failure():
    """Test circuit breaker opens with async failures."""
    breaker = CircuitBreaker(failure_threshold=2, name="test_async")
    
    @breaker.protected
    async def async_failing_call():
        await asyncio.sleep(0.01)
        raise ConnectionError("Async fail")
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await async_failing_call()
    
    assert breaker.state == CircuitState.OPEN
    
    # Should block next call
    with pytest.raises(CircuitBreakerError):
        await async_failing_call()


def test_circuit_breaker_reset():
    """Test manual circuit breaker reset."""
    breaker = CircuitBreaker(failure_threshold=2, name="test")
    
    @breaker.protected
    def failing_call():
        raise ConnectionError("Fail")
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            failing_call()
    
    assert breaker.state == CircuitState.OPEN
    
    # Reset
    breaker.reset()
    
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_circuit_breaker_stats():
    """Test circuit breaker statistics."""
    breaker = CircuitBreaker(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
        name="test_stats"
    )
    
    stats = breaker.get_stats()
    
    assert stats["name"] == "test_stats"
    assert stats["state"] == "closed"
    assert stats["failure_count"] == 0
    assert stats["config"]["failure_threshold"] == 5
    assert stats["config"]["success_threshold"] == 2
    assert stats["config"]["timeout"] == 60.0


def test_circuit_breaker_specific_exceptions():
    """Test circuit breaker only triggers on specific exceptions."""
    breaker = CircuitBreaker(
        failure_threshold=2,
        expected_exceptions=(ConnectionError,),
        name="test"
    )
    
    @breaker.protected
    def call(error_type=None):
        if error_type == "connection":
            raise ConnectionError("Connection failed")
        elif error_type == "value":
            raise ValueError("Value error")
        return "success"
    
    # ValueError should not trigger circuit
    with pytest.raises(ValueError):
        call(error_type="value")
    
    assert breaker.state == CircuitState.CLOSED
    
    # ConnectionError should trigger circuit
    for _ in range(2):
        with pytest.raises(ConnectionError):
            call(error_type="connection")
    
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_preserves_function_signature():
    """Test circuit breaker decorator preserves function signature."""
    breaker = CircuitBreaker(name="test")
    
    @breaker.protected
    def func_with_args(a, b, c=None):
        return f"{a}-{b}-{c}"
    
    result = func_with_args("x", "y", c="z")
    assert result == "x-y-z"

