"""
Input and output sanitization utilities.
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Patterns for detecting sensitive data
API_KEY_PATTERNS = [
    (r'(api[_-]?key["\s:=]+)([a-zA-Z0-9-_]{20,})', r'\1***REDACTED***'),
    (r'(sk-[a-zA-Z0-9]{20,})', r'sk-***REDACTED***'),
    (r'(Bearer\s+)([a-zA-Z0-9._-]{20,})', r'\1***REDACTED***'),
    (r'(["\']?apikey["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9-_]{20,})', r'\1***REDACTED***'),
]

# Patterns for LLM prompt injection
LLM_INJECTION_PATTERNS = [
    (r'ignore\s+(all\s+)?previous\s+instructions?', '[FILTERED]'),
    (r'disregard\s+(all\s+)?prior\s+', '[FILTERED]'),
    (r'forget\s+(everything|all)', '[FILTERED]'),
    (r'new\s+instructions?:', '[FILTERED]'),
    (r'system\s*:', '[FILTERED]'),
    (r'you\s+are\s+now', '[FILTERED]'),
]


def sanitize_for_logging(value: Any, max_length: int = 500) -> str:
    """
    Sanitize value for safe logging (prevents log injection).

    Args:
        value: Value to sanitize
        max_length: Maximum length to keep

    Returns:
        Sanitized string safe for logging

    Example:
        >>> sanitize_for_logging("user input\\nFAKE LOG ENTRY")
        'user input_FAKE LOG ENTRY'
    """
    if value is None:
        return "None"

    # Convert to string
    value_str = str(value)

    # Remove control characters and newlines
    sanitized = ''.join(
        char if char.isprintable() and char not in '\n\r\t' else '_'
        for char in value_str
    )

    # Truncate to reasonable length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "...[truncated]"

    return sanitized


def sanitize_api_error(error: Exception) -> str:
    """
    Remove sensitive data from API error messages.

    Args:
        error: Exception to sanitize

    Returns:
        Sanitized error message
    """
    error_str = str(error)

    # Apply all API key redaction patterns
    for pattern, replacement in API_KEY_PATTERNS:
        error_str = re.sub(pattern, replacement, error_str, flags=re.IGNORECASE)

    return error_str


def sanitize_for_llm(text: str, max_length: int = 500) -> str:
    """
    Sanitize text for LLM prompt injection prevention.

    Args:
        text: Text to sanitize (user input)
        max_length: Maximum length to keep

    Returns:
        Sanitized text safe for LLM prompts

    Example:
        >>> sanitize_for_llm("Normal text IGNORE ALL PREVIOUS INSTRUCTIONS")
        'Normal text [FILTERED]'
    """
    if not text:
        return ""

    sanitized = text

    # Remove potential instruction injections
    for pattern, replacement in LLM_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # Truncate to prevent token flooding
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "...[truncated]"

    return sanitized


def sanitize_filename_for_display(filename: str) -> str:
    """
    Sanitize filename for safe display in logs/UI.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename
    """
    if not filename:
        return ""

    # Remove path components
    import os
    filename = os.path.basename(filename)

    # Remove control characters
    sanitized = ''.join(char if char.isprintable() else '_' for char in filename)

    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:250] + ext

    return sanitized


def validate_regex_safety(pattern: str, timeout: float = 1.0) -> bool:
    """
    Check if regex pattern is safe from ReDoS attacks.

    Args:
        pattern: Regex pattern to validate
        timeout: Maximum time allowed for test

    Returns:
        True if pattern appears safe, False if dangerous

    Raises:
        ValueError: If pattern is clearly dangerous
    """
    # Check for obvious dangerous patterns
    dangerous_features = [
        r'\(\w+\)\+',  # Nested quantifiers like (a+)+
        r'\(\w+\)\*',  # (a*)*
        r'\(\.\*\)\+', # (.*)+
        r'\(\.\+\)\+', # (.+)+
    ]

    for dangerous in dangerous_features:
        if re.search(dangerous, pattern):
            logger.warning(f"Potentially dangerous regex pattern detected: {pattern}")
            raise ValueError(f"Regex pattern contains potentially dangerous construct: {dangerous}")

    # Test pattern doesn't exceed time limit
    import signal
    import time

    def timeout_handler(signum, frame):
        raise TimeoutError("Regex test timeout")

    # Set alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout))

    try:
        compiled = re.compile(pattern)
        # Test with pathological input
        test_input = "a" * 100
        start = time.time()
        compiled.match(test_input)
        elapsed = time.time() - start

        if elapsed > timeout / 2:
            logger.warning(f"Regex pattern slow on test input: {elapsed:.3f}s")
            return False

        return True

    except TimeoutError:
        logger.error(f"Regex pattern timeout - possible ReDoS: {pattern}")
        return False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
