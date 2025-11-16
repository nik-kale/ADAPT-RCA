import os
import logging
from dataclasses import dataclass
from typing import Optional

from .constants import (
    DEFAULT_MAX_EVENTS,
    DEFAULT_TIME_WINDOW_MINUTES,
    DEFAULT_MAX_FILE_SIZE_MB,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    VALID_LLM_PROVIDERS
)

logger = logging.getLogger(__name__)


def _get_int_env(key: str, default: int) -> int:
    """
    Safely get an integer from environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Integer value from environment or default
    """
    value = os.getenv(key)
    if value is None:
        return default

    try:
        result = int(value)
        if result <= 0:
            logger.warning(
                f"Environment variable {key}={value} must be positive. Using default: {default}"
            )
            return default
        return result
    except ValueError:
        logger.warning(
            f"Environment variable {key}={value} is not a valid integer. Using default: {default}"
        )
        return default


@dataclass
class RCAConfig:
    """
    Configuration for ADAPT-RCA.

    Environment variables:
        ADAPT_RCA_LLM_PROVIDER: LLM provider (default: "none")
        ADAPT_RCA_LLM_MODEL: Model identifier (default: "")
        ADAPT_RCA_LLM_TIMEOUT: LLM API timeout in seconds (default: 30)
        ADAPT_RCA_MAX_EVENTS: Maximum events to process (default: 5000)
        ADAPT_RCA_TIME_WINDOW: Time window for grouping in minutes (default: 15)
        ADAPT_RCA_MAX_FILE_SIZE_MB: Maximum file size in MB (default: 100)
    """
    llm_provider: str = os.getenv("ADAPT_RCA_LLM_PROVIDER", "none")
    llm_model: str = os.getenv("ADAPT_RCA_LLM_MODEL", "")
    llm_timeout: int = _get_int_env("ADAPT_RCA_LLM_TIMEOUT", DEFAULT_LLM_TIMEOUT_SECONDS)
    max_events: int = _get_int_env("ADAPT_RCA_MAX_EVENTS", DEFAULT_MAX_EVENTS)
    time_window_minutes: int = _get_int_env("ADAPT_RCA_TIME_WINDOW", DEFAULT_TIME_WINDOW_MINUTES)
    max_file_size_mb: int = _get_int_env("ADAPT_RCA_MAX_FILE_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB)

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid
        """
        errors = []

        if self.max_events <= 0:
            errors.append(f"max_events must be positive, got {self.max_events}")
        if self.time_window_minutes <= 0:
            errors.append(f"time_window_minutes must be positive, got {self.time_window_minutes}")
        if self.llm_timeout <= 0:
            errors.append(f"llm_timeout must be positive, got {self.llm_timeout}")
        if self.max_file_size_mb <= 0:
            errors.append(f"max_file_size_mb must be positive, got {self.max_file_size_mb}")

        if self.llm_provider not in VALID_LLM_PROVIDERS:
            errors.append(
                f"llm_provider must be one of {VALID_LLM_PROVIDERS}, got '{self.llm_provider}'"
            )

        if self.llm_provider != "none" and not self.llm_model:
            errors.append("llm_model must be specified when llm_provider is not 'none'")

        if errors:
            raise ValueError("Configuration validation failed:\n  - " + "\n  - ".join(errors))
