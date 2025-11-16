import os
import logging
from dataclasses import dataclass
from typing import Optional

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
        ADAPT_RCA_MAX_EVENTS: Maximum events to process (default: 5000)
        ADAPT_RCA_TIME_WINDOW: Time window for grouping in minutes (default: 15)
    """
    llm_provider: str = os.getenv("ADAPT_RCA_LLM_PROVIDER", "none")
    llm_model: str = os.getenv("ADAPT_RCA_LLM_MODEL", "")
    max_events: int = _get_int_env("ADAPT_RCA_MAX_EVENTS", 5000)
    time_window_minutes: int = _get_int_env("ADAPT_RCA_TIME_WINDOW", 15)

    def validate(self) -> None:
        """Validate configuration values."""
        if self.max_events <= 0:
            raise ValueError(f"max_events must be positive, got {self.max_events}")
        if self.time_window_minutes <= 0:
            raise ValueError(
                f"time_window_minutes must be positive, got {self.time_window_minutes}"
            )
