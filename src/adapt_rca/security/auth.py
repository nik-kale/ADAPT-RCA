"""
Authentication and authorization utilities.
"""
import os
import secrets
import logging
from functools import wraps
from typing import Set, Optional, Callable
from passlib.hash import argon2

logger = logging.getLogger(__name__)


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key.

    Args:
        length: Length of the key in bytes (will be base64 encoded)

    Returns:
        URL-safe base64-encoded API key

    Example:
        >>> key = generate_api_key()
        >>> print(f"Your API key: {key}")
    """
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using Argon2.

    Args:
        api_key: Plain text API key

    Returns:
        Hashed API key
    """
    return argon2.hash(api_key)


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        api_key: Plain text API key to verify
        hashed_key: Hashed API key to compare against

    Returns:
        True if valid, False otherwise
    """
    try:
        return argon2.verify(api_key, hashed_key)
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
        return False


def get_valid_api_keys() -> Set[str]:
    """
    Load valid API keys from environment variable.

    Returns:
        Set of valid API keys
    """
    keys_str = os.getenv('ADAPT_RCA_API_KEYS', '')
    if not keys_str:
        logger.warning("No API keys configured. Set ADAPT_RCA_API_KEYS environment variable.")
        return set()

    # Support both comma-separated plain keys and hashed keys
    keys = set(k.strip() for k in keys_str.split(',') if k.strip())
    logger.info(f"Loaded {len(keys)} API keys")
    return keys


def validate_api_key(api_key: Optional[str]) -> bool:
    """
    Validate an API key.

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False

    valid_keys = get_valid_api_keys()
    if not valid_keys:
        # If no keys configured, allow access (development mode)
        logger.warning("No API keys configured - allowing access (insecure!)")
        return True

    # Check for exact match (plain key) or hash match
    for valid_key in valid_keys:
        # Check if it's a hashed key (starts with $argon2)
        if valid_key.startswith('$argon2'):
            if verify_api_key(api_key, valid_key):
                return True
        else:
            # Plain key - constant time comparison
            if secrets.compare_digest(api_key, valid_key):
                return True

    return False


def require_api_key(f: Callable) -> Callable:
    """
    Decorator to require API key authentication for Flask routes.

    Usage:
        @app.route('/analyze', methods=['POST'])
        @require_api_key
        def analyze():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from flask import request, jsonify
        except ImportError:
            logger.error("Flask not available - cannot enforce authentication")
            return f(*args, **kwargs)

        # Get API key from header
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')

        if not api_key:
            return jsonify({'error': 'API key required', 'hint': 'Provide X-API-Key header'}), 401

        if not validate_api_key(api_key):
            logger.warning(f"Invalid API key attempt from {request.remote_addr}")
            return jsonify({'error': 'Invalid API key'}), 403

        return f(*args, **kwargs)

    return decorated_function
