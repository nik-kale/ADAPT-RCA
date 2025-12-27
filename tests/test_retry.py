"""
Tests for retry logic with exponential backoff.

Verifies retry behavior, backoff calculation, and error handling.
"""

import pytest
import asyncio
import time
from src.adapt_rca.retry import (
    retry_sync,
    retry_async,
    calculate_backoff,
    RetryableError,
    NonRetryableError,
)


def test_calculate_backoff_no_jitter():
    """Test backoff calculation without jitter."""
    # Attempt 0: 1.0 * (2^0) * 1.0 = 1.0
    assert calculate_backoff(0, 1.0, 1.0, 30.0, False) == 1.0

    # Attempt 1: 1.0 * (2^1) * 1.0 = 2.0
    assert calculate_backoff(1, 1.0, 1.0, 30.0, False) == 2.0

    # Attempt 2: 1.0 * (2^2) * 1.0 = 4.0
    assert calculate_backoff(2, 1.0, 1.0, 30.0, False) == 4.0

    # Test max cap
    assert calculate_backoff(10, 1.0, 1.0, 30.0, False) == 30.0


def test_calculate_backoff_with_jitter():
    """Test backoff calculation with jitter."""
    # With jitter, result should be between 50-100% of base
    for attempt in range(5):
        base = min(30.0, 1.0 * (2 ** attempt))
        result = calculate_backoff(attempt, 1.0, 1.0, 30.0, True)
        assert base * 0.5 <= result <= base


def test_retry_sync_success_first_try():
    """Test successful operation on first attempt."""
    call_count = 0

    @retry_sync(max_attempts=3, min_wait=0.01, max_wait=0.1)
    def succeeds_immediately():
        nonlocal call_count
        call_count += 1
        return "success"

    result = succeeds_immediately()
    assert result == "success"
    assert call_count == 1


def test_retry_sync_success_after_retries():
    """Test successful operation after retries."""
    call_count = 0

    @retry_sync(max_attempts=3, min_wait=0.01, max_wait=0.1)
    def succeeds_on_third_try():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RetryableError("Temporary failure")
        return "success"

    result = succeeds_on_third_try()
    assert result == "success"
    assert call_count == 3


def test_retry_sync_max_attempts_exceeded():
    """Test max retry attempts exceeded."""
    call_count = 0

    @retry_sync(
        max_attempts=3,
        min_wait=0.01,
        max_wait=0.1,
        retryable_exceptions=(RetryableError,)
    )
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError):
        always_fails()

    assert call_count == 3


def test_retry_sync_non_retryable_error():
    """Test non-retryable errors are not retried."""
    call_count = 0

    @retry_sync(
        max_attempts=3,
        min_wait=0.01,
        max_wait=0.1,
        retryable_exceptions=(RetryableError,)
    )
    def raises_non_retryable():
        nonlocal call_count
        call_count += 1
        raise NonRetryableError("Should not retry")

    with pytest.raises(NonRetryableError):
        raises_non_retryable()

    # Should only be called once (no retries)
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_async_success_first_try():
    """Test async successful operation on first attempt."""
    call_count = 0

    @retry_async(max_attempts=3, min_wait=0.01, max_wait=0.1)
    async def succeeds_immediately():
        nonlocal call_count
        call_count += 1
        return "async success"

    result = await succeeds_immediately()
    assert result == "async success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_async_success_after_retries():
    """Test async successful operation after retries."""
    call_count = 0

    @retry_async(max_attempts=3, min_wait=0.01, max_wait=0.1)
    async def succeeds_on_second_try():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RetryableError("Temporary failure")
        return "async success"

    result = await succeeds_on_second_try()
    assert result == "async success"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_async_max_attempts_exceeded():
    """Test async max retry attempts exceeded."""
    call_count = 0

    @retry_async(
        max_attempts=3,
        min_wait=0.01,
        max_wait=0.1,
        retryable_exceptions=(RetryableError,)
    )
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise RetryableError("Always fails")

    with pytest.raises(RetryableError):
        await always_fails()

    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_async_timing():
    """Test that retry respects backoff timing."""
    call_times = []

    @retry_async(
        max_attempts=3,
        min_wait=0.1,
        max_wait=1.0,
        backoff_factor=1.0,
        jitter=False
    )
    async def fails_twice():
        nonlocal call_times
        call_times.append(time.time())
        if len(call_times) < 3:
            raise RetryableError("Temporary failure")
        return "success"

    await fails_twice()

    # Check timing between attempts
    # First retry should wait ~0.1s, second retry ~0.2s
    assert len(call_times) == 3

    # Allow some margin for execution time
    wait1 = call_times[1] - call_times[0]
    wait2 = call_times[2] - call_times[1]

    assert 0.08 <= wait1 <= 0.15  # ~0.1s
    assert 0.15 <= wait2 <= 0.25  # ~0.2s


def test_retry_sync_with_args_kwargs():
    """Test retry decorator preserves function arguments."""
    @retry_sync(max_attempts=2, min_wait=0.01, max_wait=0.1)
    def function_with_args(a, b, c=None):
        return f"{a}-{b}-{c}"

    result = function_with_args("x", "y", c="z")
    assert result == "x-y-z"


@pytest.mark.asyncio
async def test_retry_async_with_args_kwargs():
    """Test async retry decorator preserves function arguments."""
    @retry_async(max_attempts=2, min_wait=0.01, max_wait=0.1)
    async def async_function_with_args(a, b, c=None):
        return f"{a}-{b}-{c}"

    result = await async_function_with_args("x", "y", c="z")
    assert result == "x-y-z"


def test_backoff_factor():
    """Test different backoff factors."""
    # Backoff factor 2.0 should double the wait time
    wait1 = calculate_backoff(1, 2.0, 1.0, 30.0, False)
    wait2 = calculate_backoff(1, 1.0, 1.0, 30.0, False)

    assert wait1 == wait2 * 2

