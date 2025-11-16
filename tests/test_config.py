"""
Tests for configuration module.
"""
import os
import pytest
from adapt_rca.config import RCAConfig, _get_int_env


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default configuration values."""
    # Clear environment variables
    monkeypatch.delenv("ADAPT_RCA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ADAPT_RCA_LLM_MODEL", raising=False)
    monkeypatch.delenv("ADAPT_RCA_MAX_EVENTS", raising=False)
    monkeypatch.delenv("ADAPT_RCA_TIME_WINDOW", raising=False)

    config = RCAConfig()

    assert config.llm_provider == "none"
    assert config.llm_model == ""
    assert config.max_events == 5000
    assert config.time_window_minutes == 15


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test configuration from environment variables."""
    monkeypatch.setenv("ADAPT_RCA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("ADAPT_RCA_LLM_MODEL", "gpt-4")
    monkeypatch.setenv("ADAPT_RCA_MAX_EVENTS", "1000")
    monkeypatch.setenv("ADAPT_RCA_TIME_WINDOW", "30")

    config = RCAConfig()

    assert config.llm_provider == "openai"
    assert config.llm_model == "gpt-4"
    assert config.max_events == 1000
    assert config.time_window_minutes == 30


def test_config_invalid_int(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid integers use defaults."""
    monkeypatch.setenv("ADAPT_RCA_MAX_EVENTS", "not-a-number")
    monkeypatch.setenv("ADAPT_RCA_TIME_WINDOW", "invalid")

    config = RCAConfig()

    assert config.max_events == 5000  # Default
    assert config.time_window_minutes == 15  # Default


def test_config_negative_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that negative values use defaults."""
    monkeypatch.setenv("ADAPT_RCA_MAX_EVENTS", "-100")
    monkeypatch.setenv("ADAPT_RCA_TIME_WINDOW", "0")

    config = RCAConfig()

    assert config.max_events == 5000  # Default
    assert config.time_window_minutes == 15  # Default


def test_config_validation_success() -> None:
    """Test successful configuration validation."""
    config = RCAConfig()
    config.validate()  # Should not raise


def test_config_validation_invalid_max_events() -> None:
    """Test validation fails for invalid max_events."""
    config = RCAConfig()
    config.max_events = -1

    with pytest.raises(ValueError, match="max_events must be positive"):
        config.validate()


def test_config_validation_invalid_time_window() -> None:
    """Test validation fails for invalid time_window."""
    config = RCAConfig()
    config.time_window_minutes = 0

    with pytest.raises(ValueError, match="time_window_minutes must be positive"):
        config.validate()


def test_get_int_env_valid() -> None:
    """Test _get_int_env with valid values."""
    os.environ["TEST_INT"] = "42"
    assert _get_int_env("TEST_INT", 10) == 42
    del os.environ["TEST_INT"]


def test_get_int_env_missing() -> None:
    """Test _get_int_env with missing variable."""
    assert _get_int_env("NONEXISTENT_VAR", 123) == 123


def test_get_int_env_invalid() -> None:
    """Test _get_int_env with invalid value."""
    os.environ["TEST_INVALID"] = "not-an-int"
    assert _get_int_env("TEST_INVALID", 99) == 99
    del os.environ["TEST_INVALID"]
