#!/usr/bin/env python3
"""
Configuration Loading Demo

This script demonstrates the various ways to load and use configuration
in ADAPT-RCA.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path for running from examples directory
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapt_rca.config import RCAConfig


def demo_default_config():
    """Demonstrate loading default configuration."""
    print("=" * 70)
    print("DEMO 1: Default Configuration")
    print("=" * 70)

    config = RCAConfig()
    print(f"LLM Provider: {config.llm_provider}")
    print(f"Max Events: {config.max_events}")
    print(f"Time Window: {config.time_window_minutes} minutes")
    print(f"Use Causal Graph: {config.use_causal_graph}")
    print(f"Confidence Threshold: {config.confidence_threshold}")
    print(f"Log Level: {config.log_level}")
    print()


def demo_env_config():
    """Demonstrate loading configuration from environment variables."""
    print("=" * 70)
    print("DEMO 2: Environment Variable Configuration")
    print("=" * 70)

    # Set environment variables
    os.environ["ADAPT_RCA_LLM_PROVIDER"] = "openai"
    os.environ["ADAPT_RCA_LLM_MODEL"] = "gpt-4"
    os.environ["ADAPT_RCA_MAX_EVENTS"] = "10000"
    os.environ["ADAPT_RCA_USE_CAUSAL_GRAPH"] = "false"

    config = RCAConfig.from_env()

    print(f"LLM Provider: {config.llm_provider}")
    print(f"LLM Model: {config.llm_model}")
    print(f"Max Events: {config.max_events}")
    print(f"Use Causal Graph: {config.use_causal_graph}")
    print()

    # Clean up
    for key in ["ADAPT_RCA_LLM_PROVIDER", "ADAPT_RCA_LLM_MODEL",
                "ADAPT_RCA_MAX_EVENTS", "ADAPT_RCA_USE_CAUSAL_GRAPH"]:
        os.environ.pop(key, None)


def demo_yaml_config():
    """Demonstrate loading configuration from YAML file."""
    print("=" * 70)
    print("DEMO 3: YAML Configuration File")
    print("=" * 70)

    # Create temporary YAML config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
llm:
  provider: anthropic
  model: claude-3-sonnet-20240229
  timeout: 60

processing:
  max_events: 8000
  time_window_minutes: 20
  max_file_size_mb: 150

analysis:
  use_causal_graph: true
  confidence_threshold: 0.7

logging:
  level: DEBUG
""")
        config_file = f.name

    try:
        config = RCAConfig.from_file(config_file)

        print(f"Loaded from: {config_file}")
        print(f"LLM Provider: {config.llm_provider}")
        print(f"LLM Model: {config.llm_model}")
        print(f"LLM Timeout: {config.llm_timeout} seconds")
        print(f"Max Events: {config.max_events}")
        print(f"Time Window: {config.time_window_minutes} minutes")
        print(f"Max File Size: {config.max_file_size_mb} MB")
        print(f"Use Causal Graph: {config.use_causal_graph}")
        print(f"Confidence Threshold: {config.confidence_threshold}")
        print(f"Log Level: {config.log_level}")
        print()

    finally:
        os.unlink(config_file)


def demo_toml_config():
    """Demonstrate loading configuration from TOML file."""
    print("=" * 70)
    print("DEMO 4: TOML Configuration File")
    print("=" * 70)

    # Create temporary TOML config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[llm]
provider = "openai"
model = "gpt-4-turbo"
timeout = 45

[processing]
max_events = 15000
time_window_minutes = 10
max_file_size_mb = 200

[analysis]
use_causal_graph = false
confidence_threshold = 0.8

[logging]
level = "WARNING"
file = "/var/log/adapt-rca.log"
""")
        config_file = f.name

    try:
        config = RCAConfig.from_file(config_file)

        print(f"Loaded from: {config_file}")
        print(f"LLM Provider: {config.llm_provider}")
        print(f"LLM Model: {config.llm_model}")
        print(f"Max Events: {config.max_events}")
        print(f"Time Window: {config.time_window_minutes} minutes")
        print(f"Confidence Threshold: {config.confidence_threshold}")
        print(f"Log Level: {config.log_level}")
        print(f"Log File: {config.log_file}")
        print()

    finally:
        os.unlink(config_file)


def demo_env_override():
    """Demonstrate environment variable override of file configuration."""
    print("=" * 70)
    print("DEMO 5: Environment Variable Override")
    print("=" * 70)

    # Create temporary YAML config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
llm:
  provider: openai
  model: gpt-3.5-turbo
  timeout: 30

processing:
  max_events: 5000
""")
        config_file = f.name

    try:
        # Set environment variables to override file settings
        os.environ["ADAPT_RCA_LLM_MODEL"] = "gpt-4"
        os.environ["ADAPT_RCA_MAX_EVENTS"] = "20000"

        config = RCAConfig.from_file(config_file)

        print(f"File config - LLM Model: gpt-3.5-turbo")
        print(f"File config - Max Events: 5000")
        print()
        print(f"Env override - LLM Model: {os.environ['ADAPT_RCA_LLM_MODEL']}")
        print(f"Env override - Max Events: {os.environ['ADAPT_RCA_MAX_EVENTS']}")
        print()
        print(f"Final config - LLM Provider: {config.llm_provider} (from file)")
        print(f"Final config - LLM Model: {config.llm_model} (from env override)")
        print(f"Final config - Max Events: {config.max_events} (from env override)")
        print()

    finally:
        os.unlink(config_file)
        os.environ.pop("ADAPT_RCA_LLM_MODEL", None)
        os.environ.pop("ADAPT_RCA_MAX_EVENTS", None)


def demo_validation():
    """Demonstrate configuration validation."""
    print("=" * 70)
    print("DEMO 6: Configuration Validation")
    print("=" * 70)

    # Valid configuration
    print("Testing valid configuration...")
    config = RCAConfig(
        llm_provider="openai",
        llm_model="gpt-4",
        max_events=5000,
        confidence_threshold=0.7
    )
    try:
        config.validate()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")

    print()

    # Invalid configuration - missing model
    print("Testing invalid configuration (missing model)...")
    config = RCAConfig(
        llm_provider="openai",
        llm_model="",  # Missing model
    )
    try:
        config.validate()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ Validation failed (expected): {e}")

    print()

    # Invalid configuration - bad confidence threshold
    print("Testing invalid configuration (bad threshold)...")
    config = RCAConfig(
        confidence_threshold=1.5  # Must be between 0.0 and 1.0
    )
    try:
        config.validate()
        print("✓ Configuration is valid")
    except ValueError as e:
        print(f"✗ Validation failed (expected): {e}")

    print()


def main():
    """Run all configuration demos."""
    print("\nADAPT-RCA Configuration Loading Demonstration\n")

    demo_default_config()
    demo_env_config()
    demo_yaml_config()
    demo_toml_config()
    demo_env_override()
    demo_validation()

    print("=" * 70)
    print("All demos completed!")
    print("=" * 70)
    print()
    print("For more information, see docs/configuration.md")


if __name__ == "__main__":
    main()
