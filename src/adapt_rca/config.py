"""Configuration management for ADAPT-RCA.

This module provides configuration loading and validation for the ADAPT-RCA system.
Configuration can be loaded from environment variables, YAML/TOML files, or direct
instantiation.

Classes:
    RCAConfig: Main configuration dataclass with validation.

Functions:
    _get_int_env: Safely extract integer values from environment variables.

Example:
    >>> from adapt_rca.config import RCAConfig
    >>>
    >>> # Load from environment variables
    >>> config = RCAConfig.from_env()
    >>>
    >>> # Load from file with env overrides
    >>> config = RCAConfig.from_file("config.yaml")
    >>>
    >>> # Recommended: automatic loading with fallback
    >>> config = RCAConfig.load()
    >>> config.validate()
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional

from .constants import (
    DEFAULT_MAX_EVENTS,
    DEFAULT_TIME_WINDOW_MINUTES,
    DEFAULT_MAX_FILE_SIZE_MB,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    VALID_LLM_PROVIDERS,
    MEDIUM_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _get_int_env(key: str, default: int) -> int:
    """Safely get an integer from environment variable.

    Attempts to parse an environment variable as an integer with validation.
    Returns the default value if the variable is not set, cannot be parsed,
    or is not a positive integer.

    Args:
        key: Environment variable name to read.
        default: Default value to return if variable is invalid or missing.

    Returns:
        Integer value from environment variable if valid and positive,
        otherwise the default value.

    Example:
        >>> import os
        >>> os.environ['TEST_VAR'] = '100'
        >>> _get_int_env('TEST_VAR', 50)
        100
        >>> _get_int_env('MISSING_VAR', 50)
        50
        >>> os.environ['BAD_VAR'] = 'not_a_number'
        >>> _get_int_env('BAD_VAR', 50)  # Logs warning, returns default
        50
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

    Configuration can be loaded from:
    1. Configuration files (YAML or TOML)
    2. Environment variables (override file settings)
    3. Direct instantiation with parameters

    Environment variables:
        ADAPT_RCA_LLM_PROVIDER: LLM provider (default: "none")
        ADAPT_RCA_LLM_MODEL: Model identifier (default: "")
        ADAPT_RCA_LLM_TIMEOUT: LLM API timeout in seconds (default: 30)
        ADAPT_RCA_MAX_EVENTS: Maximum events to process (default: 5000)
        ADAPT_RCA_TIME_WINDOW: Time window for grouping in minutes (default: 15)
        ADAPT_RCA_MAX_FILE_SIZE_MB: Maximum file size in MB (default: 100)
        ADAPT_RCA_USE_CAUSAL_GRAPH: Enable causal graph analysis (default: true)
        ADAPT_RCA_CONFIDENCE_THRESHOLD: Confidence threshold for analysis (default: 0.6)
        ADAPT_RCA_LOG_LEVEL: Logging level (default: "INFO")
        ADAPT_RCA_LOG_FILE: Log file path (optional)

    Config file locations (searched in order):
        ./adapt-rca.yaml, ./adapt-rca.toml
        ~/.adapt-rca.yaml, ~/.adapt-rca.toml
        /etc/adapt-rca.yaml, /etc/adapt-rca.toml
    """
    # LLM configuration
    llm_provider: str = "none"
    llm_model: str = ""
    llm_timeout: int = DEFAULT_LLM_TIMEOUT_SECONDS

    # Processing configuration
    max_events: int = DEFAULT_MAX_EVENTS
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB

    # Analysis configuration
    use_causal_graph: bool = True
    confidence_threshold: float = MEDIUM_CONFIDENCE_THRESHOLD

    # Logging configuration
    log_level: str = "INFO"
    log_file: Optional[str] = None

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid
        """
        errors = []

        # Validate positive integers
        if self.max_events <= 0:
            errors.append(f"max_events must be positive, got {self.max_events}")
        if self.time_window_minutes <= 0:
            errors.append(f"time_window_minutes must be positive, got {self.time_window_minutes}")
        if self.llm_timeout <= 0:
            errors.append(f"llm_timeout must be positive, got {self.llm_timeout}")
        if self.max_file_size_mb <= 0:
            errors.append(f"max_file_size_mb must be positive, got {self.max_file_size_mb}")

        # Validate LLM configuration
        if self.llm_provider not in VALID_LLM_PROVIDERS:
            errors.append(
                f"llm_provider must be one of {VALID_LLM_PROVIDERS}, got '{self.llm_provider}'"
            )

        if self.llm_provider != "none" and not self.llm_model:
            errors.append("llm_model must be specified when llm_provider is not 'none'")

        # Validate confidence threshold
        if not (0.0 <= self.confidence_threshold <= 1.0):
            errors.append(
                f"confidence_threshold must be between 0.0 and 1.0, got {self.confidence_threshold}"
            )

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            errors.append(
                f"log_level must be one of {valid_log_levels}, got '{self.log_level}'"
            )

        if errors:
            raise ValueError("Configuration validation failed:\n  - " + "\n  - ".join(errors))

    @classmethod
    def from_env(cls) -> 'RCAConfig':
        """
        Create configuration from environment variables only.

        This is the legacy method that maintains backward compatibility.

        Returns:
            RCAConfig instance populated from environment variables
        """
        return cls(
            llm_provider=os.getenv("ADAPT_RCA_LLM_PROVIDER", "none"),
            llm_model=os.getenv("ADAPT_RCA_LLM_MODEL", ""),
            llm_timeout=_get_int_env("ADAPT_RCA_LLM_TIMEOUT", DEFAULT_LLM_TIMEOUT_SECONDS),
            max_events=_get_int_env("ADAPT_RCA_MAX_EVENTS", DEFAULT_MAX_EVENTS),
            time_window_minutes=_get_int_env("ADAPT_RCA_TIME_WINDOW", DEFAULT_TIME_WINDOW_MINUTES),
            max_file_size_mb=_get_int_env("ADAPT_RCA_MAX_FILE_SIZE_MB", DEFAULT_MAX_FILE_SIZE_MB),
            use_causal_graph=os.getenv("ADAPT_RCA_USE_CAUSAL_GRAPH", "true").lower() in ("true", "1", "yes"),
            confidence_threshold=float(os.getenv("ADAPT_RCA_CONFIDENCE_THRESHOLD", str(MEDIUM_CONFIDENCE_THRESHOLD))),
            log_level=os.getenv("ADAPT_RCA_LOG_LEVEL", "INFO"),
            log_file=os.getenv("ADAPT_RCA_LOG_FILE"),
        )

    @classmethod
    def from_file(cls, config_path: Optional[str] = None) -> 'RCAConfig':
        """
        Create configuration from file with environment variable overrides.

        Loads configuration from YAML or TOML file and applies environment
        variable overrides. If no path is provided, searches standard locations.

        Args:
            config_path: Optional explicit path to config file.
                        If None, searches standard locations.

        Returns:
            RCAConfig instance with merged configuration

        Raises:
            FileNotFoundError: If explicit config_path doesn't exist
            ImportError: If required YAML/TOML libraries are not installed
            Exception: If config parsing fails

        Example:
            >>> config = RCAConfig.from_file("my-config.yaml")
            >>> config = RCAConfig.from_file()  # Auto-search
        """
        try:
            from .config_loader import load_config_with_overrides
        except ImportError as e:
            logger.error(f"Failed to import config_loader: {e}")
            logger.warning("Falling back to environment variable configuration")
            return cls.from_env()

        try:
            config_dict = load_config_with_overrides(config_path)
            return cls(**config_dict)
        except Exception as e:
            logger.error(f"Failed to load configuration from file: {e}")
            logger.warning("Falling back to environment variable configuration")
            return cls.from_env()

    @classmethod
    def load(cls, config_path: Optional[str] = None, use_file: bool = True) -> 'RCAConfig':
        """
        Load configuration with automatic fallback.

        This is the recommended method for loading configuration.

        Args:
            config_path: Optional explicit path to config file
            use_file: If True, attempts to load from file before env vars

        Returns:
            RCAConfig instance

        Example:
            >>> # Try file, fall back to env vars
            >>> config = RCAConfig.load()
            >>>
            >>> # Use specific file
            >>> config = RCAConfig.load("my-config.yaml")
            >>>
            >>> # Only use env vars
            >>> config = RCAConfig.load(use_file=False)
        """
        if use_file:
            return cls.from_file(config_path)
        else:
            return cls.from_env()
