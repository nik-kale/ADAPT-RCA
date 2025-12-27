# Configuration File Support - Implementation Summary

## Overview

Added comprehensive configuration file support to ADAPT-RCA, enabling configuration via YAML and TOML files with environment variable overrides.

## Files Created

### 1. `/src/adapt_rca/config_loader.py` (New)
Main configuration loader module with the following functions:

- **`load_yaml_file(path: Path) -> dict`**: Load YAML configuration files
- **`load_toml_file(path: Path) -> dict`**: Load TOML configuration files
- **`load_config_file(path: str) -> dict`**: Auto-detect format and load config
- **`find_config_file() -> Optional[Path]`**: Search standard locations for config files
- **`get_env_config() -> dict`**: Extract configuration from environment variables
- **`deep_merge(base: dict, override: dict) -> dict`**: Deep merge configurations
- **`flatten_config(config: dict) -> dict`**: Flatten nested config to match RCAConfig
- **`merge_config(file_config: dict, env_config: dict) -> dict`**: Merge file and env configs
- **`load_config_with_overrides(config_path: Optional[str]) -> dict`**: Load with all overrides

### 2. `/src/adapt_rca/config.py` (Updated)
Enhanced the RCAConfig dataclass:

**New Fields:**
- `use_causal_graph: bool = True` - Enable/disable causal graph analysis
- `confidence_threshold: float = 0.6` - Analysis confidence threshold
- `log_level: str = "INFO"` - Logging level
- `log_file: Optional[str] = None` - Optional log file path

**New Methods:**
- `RCAConfig.from_env()` - Load from environment variables only (legacy support)
- `RCAConfig.from_file(config_path)` - Load from file with env overrides
- `RCAConfig.load(config_path, use_file)` - **Recommended method** with auto-fallback

**Enhanced Validation:**
- Validates confidence threshold range (0.0 - 1.0)
- Validates log level against standard levels
- All existing validations preserved

### 3. Example Configuration Files

**`/adapt-rca.yaml.example`**: Complete YAML configuration template
**`/adapt-rca.toml.example`**: Complete TOML configuration template

### 4. Documentation

**`/docs/configuration.md`**: Comprehensive configuration guide covering:
- Configuration priority and search paths
- All configuration options with descriptions
- Usage examples
- Best practices
- Troubleshooting

### 5. Tests

**`/tests/test_config_loader.py`**: Comprehensive test suite with 30+ tests covering:
- YAML and TOML file loading
- Environment variable extraction
- Configuration merging and flattening
- Error handling
- End-to-end configuration loading

### 6. Demo

**`/examples/config_demo.py`**: Interactive demonstration showing:
- Default configuration
- Environment variable configuration
- YAML and TOML file loading
- Environment variable overrides
- Configuration validation

## Configuration Search Path

Configuration files are searched in the following order:

1. `./adapt-rca.yaml`
2. `./adapt-rca.toml`
3. `~/.adapt-rca.yaml`
4. `~/.adapt-rca.toml`
5. `/etc/adapt-rca.yaml`
6. `/etc/adapt-rca.toml`

## Priority Order

1. **Environment variables** (highest priority)
2. Configuration files
3. Default values (lowest priority)

## Configuration Structure

### YAML Example
```yaml
llm:
  provider: openai
  model: gpt-4
  timeout: 30

processing:
  max_events: 5000
  time_window_minutes: 15
  max_file_size_mb: 100

analysis:
  use_causal_graph: true
  confidence_threshold: 0.6

logging:
  level: INFO
  file: /var/log/adapt-rca.log
```

### TOML Example
```toml
[llm]
provider = "openai"
model = "gpt-4"
timeout = 30

[processing]
max_events = 5000
time_window_minutes = 15
max_file_size_mb = 100

[analysis]
use_causal_graph = true
confidence_threshold = 0.6

[logging]
level = "INFO"
file = "/var/log/adapt-rca.log"
```

## Environment Variables

All configuration options can be overridden with environment variables:

**LLM Configuration:**
- `ADAPT_RCA_LLM_PROVIDER`
- `ADAPT_RCA_LLM_MODEL`
- `ADAPT_RCA_LLM_TIMEOUT`

**Processing Configuration:**
- `ADAPT_RCA_MAX_EVENTS`
- `ADAPT_RCA_TIME_WINDOW`
- `ADAPT_RCA_MAX_FILE_SIZE_MB`

**Analysis Configuration:**
- `ADAPT_RCA_USE_CAUSAL_GRAPH`
- `ADAPT_RCA_CONFIDENCE_THRESHOLD`

**Logging Configuration:**
- `ADAPT_RCA_LOG_LEVEL`
- `ADAPT_RCA_LOG_FILE`

## Usage Examples

### Recommended: Auto-load with fallback
```python
from adapt_rca.config import RCAConfig

# Searches for config file, falls back to env vars
config = RCAConfig.load()
config.validate()
```

### Explicit config file
```python
from adapt_rca.config import RCAConfig

config = RCAConfig.load("my-config.yaml")
config.validate()
```

### Environment variables only
```python
from adapt_rca.config import RCAConfig

config = RCAConfig.load(use_file=False)
# or
config = RCAConfig.from_env()
```

### Direct instantiation
```python
from adapt_rca.config import RCAConfig

config = RCAConfig(
    llm_provider="openai",
    llm_model="gpt-4",
    max_events=10000,
    use_causal_graph=True
)
config.validate()
```

## Dependencies Added

Updated `/requirements.txt`:
- `pyyaml>=6.0` - For YAML support
- `tomli>=2.0.0; python_version < '3.11'` - For TOML support (built-in for Python 3.11+)

## Backward Compatibility

All existing code continues to work:
- Default instantiation `RCAConfig()` still uses environment variables
- All existing environment variables work as before
- New fields have sensible defaults

## Testing

Run the demo:
```bash
python3 examples/config_demo.py
```

Run tests:
```bash
pytest tests/test_config_loader.py -v
```

## Migration Guide

1. Install dependencies:
   ```bash
   pip install pyyaml tomli
   ```

2. Create a config file:
   ```bash
   cp adapt-rca.yaml.example adapt-rca.yaml
   # Edit adapt-rca.yaml with your settings
   ```

3. Update your code to use the new loader:
   ```python
   # Old
   config = RCAConfig()

   # New (recommended)
   config = RCAConfig.load()
   ```

4. Optionally migrate environment variables to config file

## Benefits

1. **Easier Configuration Management**: Config files are easier to edit and version control
2. **Better Organization**: Grouped configuration by category (llm, processing, analysis, logging)
3. **Environment Flexibility**: Different configs for dev/test/prod
4. **Override Support**: Environment variables still work for CI/CD and containers
5. **Validation**: Comprehensive validation with helpful error messages
6. **Documentation**: Clear examples and comprehensive guide
7. **Backward Compatible**: Existing code continues to work

## Next Steps

- Consider using config files in CLI tools (when they're created)
- Add config file validation to CI/CD pipeline
- Create environment-specific config templates (dev, staging, prod)
