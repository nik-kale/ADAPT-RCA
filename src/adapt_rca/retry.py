"""
Retry logic with exponential backoff for reliable external operations.

This module provides decorators and utilities for retrying failed operations
with configurable exponential backoff and jitter.
"""

import asyncio
import random
import functools
import logging
from typing import TypeVar, Callable, Optional, Tuple, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (default 1.0)
        min_wait: Minimum wait time in seconds (default 1)
        max_wait: Maximum wait time in seconds (default 30)
        jitter: Whether to add random jitter to wait time (default True)
        retryable_exceptions: Tuple of exception types to retry
    """
    max_attempts: int = 3
    backoff_factor: float = 1.0
    min_wait: float = 1.0
    max_wait: float = 30.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


def calculate_backoff(
    attempt: int,
    backoff_factor: float,
    min_wait: float,
    max_wait: float,
    jitter: bool
) -> float:
    """
    Calculate exponential backoff wait time.

    Args:
        attempt: Current attempt number (0-indexed)
        backoff_factor: Multiplier for exponential backoff
        min_wait: Minimum wait time
        max_wait: Maximum wait time
        jitter: Whether to add random jitter

    Returns:
        Wait time in seconds
    """
    # Exponential backoff: wait = min(max_wait, min_wait * (2^attempt) * backoff_factor)
    wait = min(max_wait, min_wait * (2 ** attempt) * backoff_factor)

    # Add jitter: randomize between 50-100% of calculated wait
    if jitter:
        wait = wait * (0.5 + random.random() * 0.5)

    return wait


def retry_sync(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for synchronous retry with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        backoff_factor: Backoff multiplier
        min_wait: Minimum wait seconds
        max_wait: Maximum wait seconds
        jitter: Add random jitter
        retryable_exceptions: Exception types to retry

    Returns:
        Decorated function

    Example:
        @retry_sync(max_attempts=3, backoff_factor=2.0)
        def fetch_data():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt + 1 >= max_attempts:
                        logger.error(
                            f"Max retries ({max_attempts}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    wait_time = calculate_backoff(
                        attempt, backoff_factor, min_wait, max_wait, jitter
                    )

                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                        f"after {wait_time:.2f}s: {e}"
                    )

                    import time
                    time.sleep(wait_time)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def retry_async(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for async retry with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        backoff_factor: Backoff multiplier
        min_wait: Minimum wait seconds
        max_wait: Maximum wait seconds
        jitter: Add random jitter
        retryable_exceptions: Exception types to retry

    Returns:
        Decorated async function

    Example:
        @retry_async(max_attempts=3, backoff_factor=2.0)
        async def fetch_data_async():
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com/data") as resp:
                    resp.raise_for_status()
                    return await resp.json()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt + 1 >= max_attempts:
                        logger.error(
                            f"Max retries ({max_attempts}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    wait_time = calculate_backoff(
                        attempt, backoff_factor, min_wait, max_wait, jitter
                    )

                    logger.warning(
                        f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                        f"after {wait_time:.2f}s: {e}"
                    )

                    await asyncio.sleep(wait_time)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RetryableError(Exception):
    """Base exception for retryable errors."""
    pass


class NonRetryableError(Exception):
    """Exception that should not be retried."""
    pass


# Common retry configurations
NETWORK_RETRY = RetryConfig(
    max_attempts=3,
    backoff_factor=1.0,
    min_wait=1.0,
    max_wait=10.0,
    jitter=True,
    retryable_exceptions=(ConnectionError, TimeoutError, RetryableError)
)

DATABASE_RETRY = RetryConfig(
    max_attempts=5,
    backoff_factor=2.0,
    min_wait=0.5,
    max_wait=30.0,
    jitter=True,
    retryable_exceptions=(ConnectionError, RetryableError)
)

API_RETRY = RetryConfig(
    max_attempts=3,
    backoff_factor=1.5,
    min_wait=1.0,
    max_wait=15.0,
    jitter=True,
    retryable_exceptions=(ConnectionError, TimeoutError, RetryableError)
)

