"""
Rate limiting middleware for API endpoints.

Implements token bucket algorithm for rate limiting.
"""

import time
from typing import Dict
from threading import Lock


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Limits requests per time window using token bucket algorithm.
    Thread-safe implementation.
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.rate = requests_per_minute
        self.tokens_per_second = requests_per_minute / 60.0
        self.max_tokens = requests_per_minute
        
        self._buckets: Dict[str, Dict] = {}
        self._lock = Lock()
    
    async def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed for given key.
        
        Args:
            key: Unique identifier (e.g., user_id, ip_address)
            
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        return self._check_and_update(key)
    
    def _check_and_update(self, key: str) -> bool:
        """Check rate limit and update token bucket."""
        now = time.time()
        
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = {
                    'tokens': self.max_tokens - 1,
                    'last_update': now
                }
                return True
            
            bucket = self._buckets[key]
            
            # Add tokens based on time elapsed
            elapsed = now - bucket['last_update']
            bucket['tokens'] = min(
                self.max_tokens,
                bucket['tokens'] + (elapsed * self.tokens_per_second)
            )
            bucket['last_update'] = now
            
            # Check if tokens available
            if bucket['tokens'] >= 1.0:
                bucket['tokens'] -= 1.0
                return True
            
            return False
    
    def reset(self, key: str) -> None:
        """
        Reset rate limit for a key.
        
        Args:
            key: Key to reset
        """
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]

