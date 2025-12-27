"""
Configuration file loader for ADAPT-RCA.

Supports loading configuration from YAML and TOML files with environment variable
overrides and a standard search path.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def load_yaml_file(path: Path) -> dict:
    """
    Load configuration from a YAML file.

    Args:
        path: Path to the YAML file

    Returns:
        Dictionary containing configuration data

    Raises:
        ImportError: If PyYAML is not installed
        FileNotFoundError: If file doesn't exist
        Exception: If YAML parsing fails
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required for YAML config files. "
            "Install with: pip install pyyaml"
        )

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            return config if config is not None else {}
    except Exception as e:
        raise Exception(f"Failed to parse YAML config file {path}: {e}")


def load_toml_file(path: Path) -> dict:
    """
    Load configuration from a TOML file.

    Args:
        path: Path to the TOML file

    Returns:
        Dictionary containing configuration data

    Raises:
        ImportError: If tomli/tomllib is not installed
        FileNotFoundError: If file doesn't exist
        Exception: If TOML parsing fails
    """
    try:
        # Python 3.11+ has tomllib built-in
        import tomllib
        open_mode = 'rb'
    except ImportError:
        try:
            # Fallback to tomli for older Python versions
            import tomli as tomllib
            open_mode = 'rb'
        except ImportError:
            raise ImportError(
                "tomli is required for TOML config files on Python < 3.11. "
                "Install with: pip install tomli"
            )

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, open_mode) as f:
            return tomllib.load(f)
    except Exception as e:
        raise Exception(f"Failed to parse TOML config file {path}: {e}")


def load_config_file(path: str) -> dict:
    """
    Load configuration from a YAML or TOML file.

    The file format is determined by the file extension (.yaml, .yml, or .toml).

    Args:
        path: Path to the configuration file

    Returns:
        Dictionary containing configuration data

    Raises:
        ValueError: If file extension is not supported
        FileNotFoundError: If file doesn't exist
        Exception: If parsing fails
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in ['.yaml', '.yml']:
        return load_yaml_file(file_path)
    elif suffix == '.toml':
        return load_toml_file(file_path)
    else:
        raise ValueError(
            f"Unsupported config file format: {suffix}. "
            "Supported formats: .yaml, .yml, .toml"
        )


def find_config_file() -> Optional[Path]:
    """
    Search for a configuration file in standard locations.

    Search order:
    1. ./adapt-rca.yaml
    2. ./adapt-rca.toml
    3. ~/.adapt-rca.yaml
    4. ~/.adapt-rca.toml
    5. /etc/adapt-rca.yaml
    6. /etc/adapt-rca.toml

    Returns:
        Path to the first configuration file found, or None if no file is found
    """
    search_paths = [
        # Current directory
        Path.cwd() / "adapt-rca.yaml",
        Path.cwd() / "adapt-rca.toml",
        # User home directory
        Path.home() / ".adapt-rca.yaml",
        Path.home() / ".adapt-rca.toml",
        # System-wide configuration
        Path("/etc/adapt-rca.yaml"),
        Path("/etc/adapt-rca.toml"),
    ]

    for path in search_paths:
        if path.exists() and path.is_file():
            logger.info(f"Found configuration file: {path}")
            return path

    logger.debug("No configuration file found in standard locations")
    return None


def get_env_config() -> dict:
    """
    Extract configuration from environment variables.

    Environment variables override file-based configuration.

    Returns:
        Dictionary containing configuration from environment variables
    """
    config = {}

    # LLM configuration
    llm_config = {}
    if os.getenv("ADAPT_RCA_LLM_PROVIDER"):
        llm_config["provider"] = os.getenv("ADAPT_RCA_LLM_PROVIDER")
    if os.getenv("ADAPT_RCA_LLM_MODEL"):
        llm_config["model"] = os.getenv("ADAPT_RCA_LLM_MODEL")
    if os.getenv("ADAPT_RCA_LLM_TIMEOUT"):
        try:
            llm_config["timeout"] = int(os.getenv("ADAPT_RCA_LLM_TIMEOUT"))
        except ValueError:
            logger.warning("Invalid ADAPT_RCA_LLM_TIMEOUT, ignoring")

    if llm_config:
        config["llm"] = llm_config

    # Processing configuration
    processing_config = {}
    if os.getenv("ADAPT_RCA_MAX_EVENTS"):
        try:
            processing_config["max_events"] = int(os.getenv("ADAPT_RCA_MAX_EVENTS"))
        except ValueError:
            logger.warning("Invalid ADAPT_RCA_MAX_EVENTS, ignoring")
    if os.getenv("ADAPT_RCA_TIME_WINDOW"):
        try:
            processing_config["time_window_minutes"] = int(os.getenv("ADAPT_RCA_TIME_WINDOW"))
        except ValueError:
            logger.warning("Invalid ADAPT_RCA_TIME_WINDOW, ignoring")
    if os.getenv("ADAPT_RCA_MAX_FILE_SIZE_MB"):
        try:
            processing_config["max_file_size_mb"] = int(os.getenv("ADAPT_RCA_MAX_FILE_SIZE_MB"))
        except ValueError:
            logger.warning("Invalid ADAPT_RCA_MAX_FILE_SIZE_MB, ignoring")

    if processing_config:
        config["processing"] = processing_config

    # Analysis configuration
    analysis_config = {}
    if os.getenv("ADAPT_RCA_USE_CAUSAL_GRAPH"):
        value = os.getenv("ADAPT_RCA_USE_CAUSAL_GRAPH").lower()
        analysis_config["use_causal_graph"] = value in ("true", "1", "yes")
    if os.getenv("ADAPT_RCA_CONFIDENCE_THRESHOLD"):
        try:
            analysis_config["confidence_threshold"] = float(os.getenv("ADAPT_RCA_CONFIDENCE_THRESHOLD"))
        except ValueError:
            logger.warning("Invalid ADAPT_RCA_CONFIDENCE_THRESHOLD, ignoring")

    if analysis_config:
        config["analysis"] = analysis_config

    # Logging configuration
    logging_config = {}
    if os.getenv("ADAPT_RCA_LOG_LEVEL"):
        logging_config["level"] = os.getenv("ADAPT_RCA_LOG_LEVEL")
    if os.getenv("ADAPT_RCA_LOG_FILE"):
        logging_config["file"] = os.getenv("ADAPT_RCA_LOG_FILE")

    if logging_config:
        config["logging"] = logging_config

    return config


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries, with override values taking precedence.

    Args:
        base: Base dictionary
        override: Override dictionary (values take precedence)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def flatten_config(config: dict) -> dict:
    """
    Flatten nested configuration dictionary to match RCAConfig fields.

    Converts structured config (with llm, processing, analysis sections)
    to flat structure expected by RCAConfig.

    Args:
        config: Nested configuration dictionary

    Returns:
        Flattened configuration dictionary
    """
    flat = {}

    # LLM settings
    if "llm" in config:
        llm = config["llm"]
        if "provider" in llm:
            flat["llm_provider"] = llm["provider"]
        if "model" in llm:
            flat["llm_model"] = llm["model"]
        if "timeout" in llm:
            flat["llm_timeout"] = llm["timeout"]

    # Processing settings
    if "processing" in config:
        proc = config["processing"]
        if "max_events" in proc:
            flat["max_events"] = proc["max_events"]
        if "time_window_minutes" in proc:
            flat["time_window_minutes"] = proc["time_window_minutes"]
        if "max_file_size_mb" in proc:
            flat["max_file_size_mb"] = proc["max_file_size_mb"]

    # Analysis settings (for future use)
    if "analysis" in config:
        analysis = config["analysis"]
        if "use_causal_graph" in analysis:
            flat["use_causal_graph"] = analysis["use_causal_graph"]
        if "confidence_threshold" in analysis:
            flat["confidence_threshold"] = analysis["confidence_threshold"]

    # Logging settings (for future use)
    if "logging" in config:
        log = config["logging"]
        if "level" in log:
            flat["log_level"] = log["level"]
        if "file" in log:
            flat["log_file"] = log["file"]

    return flat


def merge_config(file_config: dict, env_config: dict) -> dict:
    """
    Merge file-based and environment-based configuration.

    Environment variables take precedence over file-based configuration.

    Args:
        file_config: Configuration loaded from file
        env_config: Configuration from environment variables

    Returns:
        Merged configuration dictionary (flattened)
    """
    # Deep merge the nested configs (env takes precedence)
    merged = deep_merge(file_config, env_config)

    # Flatten to match RCAConfig structure
    return flatten_config(merged)


def load_config_with_overrides(config_path: Optional[str] = None) -> dict:
    """
    Load configuration from file with environment variable overrides.

    Args:
        config_path: Optional explicit path to config file.
                    If None, searches standard locations.

    Returns:
        Dictionary containing merged configuration

    Raises:
        FileNotFoundError: If explicit config_path is provided but doesn't exist
        Exception: If config parsing fails
    """
    file_config = {}

    # Load from file
    if config_path:
        # Explicit path provided
        file_config = load_config_file(config_path)
        logger.info(f"Loaded configuration from: {config_path}")
    else:
        # Search for config file
        found_path = find_config_file()
        if found_path:
            file_config = load_config_file(str(found_path))
            logger.info(f"Loaded configuration from: {found_path}")

    # Get environment overrides
    env_config = get_env_config()
    if env_config:
        logger.info("Applying environment variable overrides")

    # Merge and return
    return merge_config(file_config, env_config)
