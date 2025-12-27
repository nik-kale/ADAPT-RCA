"""
Tests for rate limiting middleware.

Tests verify rate limiter behavior under various conditions.
"""

import pytest
import asyncio
import time
from src.adapt_rca.middleware.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    """Test that requests under the limit are allowed."""
    limiter = RateLimiter(requests_per_minute=10)

    # Should allow 10 requests
    for i in range(10):
        allowed = await limiter.is_allowed("test_key")
        assert allowed, f"Request {i+1} should be allowed"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    """Test that requests over the limit are blocked."""
    limiter = RateLimiter(requests_per_minute=10)

    # Exhaust the limit
    for _ in range(10):
        await limiter.is_allowed("test_key")

    # Next request should be blocked
    allowed = await limiter.is_allowed("test_key")
    assert not allowed, "Request over limit should be blocked"


@pytest.mark.asyncio
async def test_rate_limiter_different_keys():
    """Test that different keys have independent limits."""
    limiter = RateLimiter(requests_per_minute=5)

    # Exhaust limit for key1
    for _ in range(5):
        await limiter.is_allowed("key1")

    # key1 should be blocked
    assert not await limiter.is_allowed("key1")

    # key2 should still be allowed
    assert await limiter.is_allowed("key2")


@pytest.mark.asyncio
async def test_rate_limiter_token_refill():
    """Test that tokens are refilled over time."""
    # 60 requests per minute = 1 per second
    limiter = RateLimiter(requests_per_minute=60)

    # Use up some tokens
    for _ in range(5):
        await limiter.is_allowed("test_key")

    # Wait for 2 seconds to refill ~2 tokens
    await asyncio.sleep(2.1)

    # Should be able to make 2 more requests
    assert await limiter.is_allowed("test_key")
    assert await limiter.is_allowed("test_key")


@pytest.mark.asyncio
async def test_rate_limiter_reset():
    """Test that reset clears the limit for a key."""
    limiter = RateLimiter(requests_per_minute=5)

    # Exhaust the limit
    for _ in range(5):
        await limiter.is_allowed("test_key")

    # Should be blocked
    assert not await limiter.is_allowed("test_key")

    # Reset the key
    limiter.reset("test_key")

    # Should be allowed again
    assert await limiter.is_allowed("test_key")


@pytest.mark.asyncio
async def test_rate_limiter_zero_rate():
    """Test edge case with very low rate."""
    limiter = RateLimiter(requests_per_minute=1)

    # First request allowed
    assert await limiter.is_allowed("test_key")

    # Second request immediately should be blocked
    assert not await limiter.is_allowed("test_key")


@pytest.mark.asyncio
async def test_rate_limiter_high_rate():
    """Test with high rate limit."""
    limiter = RateLimiter(requests_per_minute=1000)

    # Should handle many requests quickly
    for _ in range(100):
        assert await limiter.is_allowed("test_key")


@pytest.mark.asyncio
async def test_rate_limiter_burst_handling():
    """Test burst request handling."""
    limiter = RateLimiter(requests_per_minute=60)

    # Allow burst up to max tokens
    count = 0
    for _ in range(70):
        if await limiter.is_allowed("burst_key"):
            count += 1

    # Should allow up to max_tokens (60)
    assert count == 60


def test_rate_limiter_initialization():
    """Test rate limiter initialization."""
    limiter = RateLimiter(requests_per_minute=120)

    assert limiter.rate == 120
    assert limiter.max_tokens == 120
    assert limiter.tokens_per_second == 2.0


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_access():
    """Test thread safety with concurrent requests."""
    limiter = RateLimiter(requests_per_minute=100)

    async def make_requests(key: str, count: int) -> int:
        """Make multiple requests and return success count."""
        allowed_count = 0
        for _ in range(count):
            if await limiter.is_allowed(key):
                allowed_count += 1
        return allowed_count

    # Make concurrent requests
    results = await asyncio.gather(
        make_requests("concurrent_key", 50),
        make_requests("concurrent_key", 50),
        make_requests("concurrent_key", 50),
    )

    # Total allowed should not exceed limit
    total_allowed = sum(results)
    assert total_allowed <= 100

