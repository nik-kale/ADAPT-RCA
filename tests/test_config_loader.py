"""
Tests for configuration file loader.
"""

import os
import tempfile
from pathlib import Path
import pytest

from adapt_rca.config_loader import (
    load_yaml_file,
    load_toml_file,
    load_config_file,
    find_config_file,
    get_env_config,
    deep_merge,
    flatten_config,
    merge_config,
    load_config_with_overrides,
)


class TestLoadYAMLFile:
    """Tests for YAML file loading."""

    def test_load_valid_yaml(self, tmp_path):
        """Test loading a valid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
llm:
  provider: openai
  model: gpt-4
processing:
  max_events: 1000
""")

        config = load_yaml_file(config_file)

        assert config["llm"]["provider"] == "openai"
        assert config["llm"]["model"] == "gpt-4"
        assert config["processing"]["max_events"] == 1000

    def test_load_empty_yaml(self, tmp_path):
        """Test loading an empty YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = load_yaml_file(config_file)

        assert config == {}

    def test_load_nonexistent_yaml(self, tmp_path):
        """Test loading a non-existent YAML file."""
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_yaml_file(config_file)


class TestLoadTOMLFile:
    """Tests for TOML file loading."""

    def test_load_valid_toml(self, tmp_path):
        """Test loading a valid TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[llm]
provider = "openai"
model = "gpt-4"

[processing]
max_events = 1000
""")

        config = load_toml_file(config_file)

        assert config["llm"]["provider"] == "openai"
        assert config["llm"]["model"] == "gpt-4"
        assert config["processing"]["max_events"] == 1000

    def test_load_empty_toml(self, tmp_path):
        """Test loading an empty TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("")

        config = load_toml_file(config_file)

        assert config == {}

    def test_load_nonexistent_toml(self, tmp_path):
        """Test loading a non-existent TOML file."""
        config_file = tmp_path / "nonexistent.toml"

        with pytest.raises(FileNotFoundError):
            load_toml_file(config_file)


class TestLoadConfigFile:
    """Tests for generic config file loading."""

    def test_load_yaml_by_extension(self, tmp_path):
        """Test that YAML files are loaded correctly."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: openai")

        config = load_config_file(str(config_file))

        assert config["llm"]["provider"] == "openai"

    def test_load_toml_by_extension(self, tmp_path):
        """Test that TOML files are loaded correctly."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[llm]\nprovider = "openai"')

        config = load_config_file(str(config_file))

        assert config["llm"]["provider"] == "openai"

    def test_unsupported_extension(self, tmp_path):
        """Test that unsupported extensions raise an error."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with pytest.raises(ValueError, match="Unsupported config file format"):
            load_config_file(str(config_file))


class TestGetEnvConfig:
    """Tests for environment variable configuration."""

    def test_llm_env_vars(self, monkeypatch):
        """Test LLM environment variables."""
        monkeypatch.setenv("ADAPT_RCA_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ADAPT_RCA_LLM_MODEL", "claude-3")
        monkeypatch.setenv("ADAPT_RCA_LLM_TIMEOUT", "60")

        config = get_env_config()

        assert config["llm"]["provider"] == "anthropic"
        assert config["llm"]["model"] == "claude-3"
        assert config["llm"]["timeout"] == 60

    def test_processing_env_vars(self, monkeypatch):
        """Test processing environment variables."""
        monkeypatch.setenv("ADAPT_RCA_MAX_EVENTS", "10000")
        monkeypatch.setenv("ADAPT_RCA_TIME_WINDOW", "30")
        monkeypatch.setenv("ADAPT_RCA_MAX_FILE_SIZE_MB", "200")

        config = get_env_config()

        assert config["processing"]["max_events"] == 10000
        assert config["processing"]["time_window_minutes"] == 30
        assert config["processing"]["max_file_size_mb"] == 200

    def test_analysis_env_vars(self, monkeypatch):
        """Test analysis environment variables."""
        monkeypatch.setenv("ADAPT_RCA_USE_CAUSAL_GRAPH", "false")
        monkeypatch.setenv("ADAPT_RCA_CONFIDENCE_THRESHOLD", "0.8")

        config = get_env_config()

        assert config["analysis"]["use_causal_graph"] is False
        assert config["analysis"]["confidence_threshold"] == 0.8

    def test_logging_env_vars(self, monkeypatch):
        """Test logging environment variables."""
        monkeypatch.setenv("ADAPT_RCA_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("ADAPT_RCA_LOG_FILE", "/var/log/test.log")

        config = get_env_config()

        assert config["logging"]["level"] == "DEBUG"
        assert config["logging"]["file"] == "/var/log/test.log"

    def test_empty_env(self):
        """Test with no environment variables set."""
        # Clear all ADAPT_RCA env vars
        for key in list(os.environ.keys()):
            if key.startswith("ADAPT_RCA_"):
                del os.environ[key]

        config = get_env_config()

        assert config == {}


class TestDeepMerge:
    """Tests for deep dictionary merging."""

    def test_simple_merge(self):
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        base = {"llm": {"provider": "openai", "model": "gpt-3"}}
        override = {"llm": {"model": "gpt-4"}}

        result = deep_merge(base, override)

        assert result == {"llm": {"provider": "openai", "model": "gpt-4"}}

    def test_no_override(self):
        """Test merge with empty override."""
        base = {"a": 1, "b": 2}
        override = {}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 2}


class TestFlattenConfig:
    """Tests for configuration flattening."""

    def test_flatten_llm_config(self):
        """Test flattening LLM configuration."""
        config = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "timeout": 60
            }
        }

        result = flatten_config(config)

        assert result == {
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "llm_timeout": 60
        }

    def test_flatten_processing_config(self):
        """Test flattening processing configuration."""
        config = {
            "processing": {
                "max_events": 10000,
                "time_window_minutes": 30,
                "max_file_size_mb": 200
            }
        }

        result = flatten_config(config)

        assert result == {
            "max_events": 10000,
            "time_window_minutes": 30,
            "max_file_size_mb": 200
        }

    def test_flatten_analysis_config(self):
        """Test flattening analysis configuration."""
        config = {
            "analysis": {
                "use_causal_graph": False,
                "confidence_threshold": 0.8
            }
        }

        result = flatten_config(config)

        assert result == {
            "use_causal_graph": False,
            "confidence_threshold": 0.8
        }

    def test_flatten_logging_config(self):
        """Test flattening logging configuration."""
        config = {
            "logging": {
                "level": "DEBUG",
                "file": "/var/log/test.log"
            }
        }

        result = flatten_config(config)

        assert result == {
            "log_level": "DEBUG",
            "log_file": "/var/log/test.log"
        }

    def test_flatten_complete_config(self):
        """Test flattening a complete configuration."""
        config = {
            "llm": {"provider": "openai", "model": "gpt-4"},
            "processing": {"max_events": 5000},
            "analysis": {"use_causal_graph": True},
            "logging": {"level": "INFO"}
        }

        result = flatten_config(config)

        assert result == {
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "max_events": 5000,
            "use_causal_graph": True,
            "log_level": "INFO"
        }


class TestMergeConfig:
    """Tests for configuration merging and flattening."""

    def test_merge_file_and_env(self):
        """Test merging file and environment configs."""
        file_config = {
            "llm": {"provider": "openai", "model": "gpt-3"},
            "processing": {"max_events": 1000}
        }
        env_config = {
            "llm": {"model": "gpt-4"},
            "processing": {"max_events": 5000}
        }

        result = merge_config(file_config, env_config)

        assert result == {
            "llm_provider": "openai",
            "llm_model": "gpt-4",  # Env override
            "max_events": 5000  # Env override
        }

    def test_merge_with_empty_env(self):
        """Test merging with empty environment config."""
        file_config = {
            "llm": {"provider": "openai", "model": "gpt-4"}
        }
        env_config = {}

        result = merge_config(file_config, env_config)

        assert result == {
            "llm_provider": "openai",
            "llm_model": "gpt-4"
        }


class TestLoadConfigWithOverrides:
    """Tests for complete configuration loading with overrides."""

    def test_load_yaml_with_env_override(self, tmp_path, monkeypatch):
        """Test loading YAML config with environment override."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
llm:
  provider: openai
  model: gpt-3
  timeout: 30
processing:
  max_events: 1000
""")

        monkeypatch.setenv("ADAPT_RCA_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("ADAPT_RCA_MAX_EVENTS", "5000")

        config = load_config_with_overrides(str(config_file))

        assert config["llm_provider"] == "openai"
        assert config["llm_model"] == "gpt-4"  # Env override
        assert config["llm_timeout"] == 30
        assert config["max_events"] == 5000  # Env override

    def test_load_toml_with_env_override(self, tmp_path, monkeypatch):
        """Test loading TOML config with environment override."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[llm]
provider = "anthropic"
model = "claude-3"

[processing]
max_events = 2000
""")

        monkeypatch.setenv("ADAPT_RCA_LLM_MODEL", "claude-4")

        config = load_config_with_overrides(str(config_file))

        assert config["llm_provider"] == "anthropic"
        assert config["llm_model"] == "claude-4"  # Env override
        assert config["max_events"] == 2000

    def test_load_without_file(self, monkeypatch):
        """Test loading with only environment variables."""
        monkeypatch.setenv("ADAPT_RCA_LLM_PROVIDER", "openai")
        monkeypatch.setenv("ADAPT_RCA_LLM_MODEL", "gpt-4")

        config = load_config_with_overrides(None)

        assert config["llm_provider"] == "openai"
        assert config["llm_model"] == "gpt-4"
