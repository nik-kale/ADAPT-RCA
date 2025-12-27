# Configuration Guide

ADAPT-RCA supports flexible configuration through multiple methods:
1. Configuration files (YAML or TOML)
2. Environment variables
3. Direct instantiation

## Configuration Priority

Configuration values are loaded with the following priority (highest to lowest):
1. **Environment variables** (highest priority)
2. Configuration files
3. Default values (lowest priority)

This means environment variables will always override values from configuration files.

## Configuration Files

### Supported Formats

ADAPT-RCA supports two configuration file formats:
- **YAML**: `.yaml` or `.yml` extension
- **TOML**: `.toml` extension

### File Search Path

If no explicit configuration file is provided, ADAPT-RCA searches for configuration files in the following order:

1. `./adapt-rca.yaml`
2. `./adapt-rca.toml`
3. `~/.adapt-rca.yaml`
4. `~/.adapt-rca.toml`
5. `/etc/adapt-rca.yaml`
6. `/etc/adapt-rca.toml`

The first file found will be used.

### YAML Configuration Example

```yaml
# adapt-rca.yaml

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

### TOML Configuration Example

```toml
# adapt-rca.toml

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

## Configuration Options

### LLM Configuration

Controls LLM integration for enhanced analysis.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `llm.provider` | string | `"none"` | LLM provider: `"none"`, `"openai"`, or `"anthropic"` |
| `llm.model` | string | `""` | Model identifier (required if provider is not `"none"`) |
| `llm.timeout` | integer | `30` | API timeout in seconds |

**Environment Variables:**
- `ADAPT_RCA_LLM_PROVIDER`
- `ADAPT_RCA_LLM_MODEL`
- `ADAPT_RCA_LLM_TIMEOUT`

### Processing Configuration

Controls event processing behavior.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `processing.max_events` | integer | `5000` | Maximum number of events to process |
| `processing.time_window_minutes` | integer | `15` | Time window for event grouping (minutes) |
| `processing.max_file_size_mb` | integer | `100` | Maximum log file size (MB) |

**Environment Variables:**
- `ADAPT_RCA_MAX_EVENTS`
- `ADAPT_RCA_TIME_WINDOW`
- `ADAPT_RCA_MAX_FILE_SIZE_MB`

### Analysis Configuration

Controls analysis behavior and thresholds.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `analysis.use_causal_graph` | boolean | `true` | Enable causal graph analysis |
| `analysis.confidence_threshold` | float | `0.6` | Confidence threshold for recommendations (0.0 - 1.0) |

**Environment Variables:**
- `ADAPT_RCA_USE_CAUSAL_GRAPH` (values: `true`, `false`, `1`, `0`, `yes`, `no`)
- `ADAPT_RCA_CONFIDENCE_THRESHOLD`

### Logging Configuration

Controls logging behavior.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `logging.level` | string | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logging.file` | string | `null` | Optional log file path (omit to log to console only) |

**Environment Variables:**
- `ADAPT_RCA_LOG_LEVEL`
- `ADAPT_RCA_LOG_FILE`

## Usage Examples

### Using Configuration Files

#### Auto-search for configuration file

```python
from adapt_rca.config import RCAConfig

# Searches standard locations for config file
config = RCAConfig.load()
```

#### Specify configuration file explicitly

```python
from adapt_rca.config import RCAConfig

# Use specific YAML file
config = RCAConfig.load("my-config.yaml")

# Use specific TOML file
config = RCAConfig.load("my-config.toml")
```

### Using Environment Variables Only

```python
from adapt_rca.config import RCAConfig

# Ignore config files, use only environment variables
config = RCAConfig.load(use_file=False)

# Alternative: explicit method
config = RCAConfig.from_env()
```

### Direct Instantiation

```python
from adapt_rca.config import RCAConfig

# Create config with explicit values
config = RCAConfig(
    llm_provider="openai",
    llm_model="gpt-4",
    max_events=10000,
    use_causal_graph=True,
    confidence_threshold=0.7
)
```

### Environment Variable Overrides

Environment variables always take precedence over file-based configuration:

```bash
# Create config file
cat > adapt-rca.yaml <<EOF
llm:
  provider: openai
  model: gpt-3.5-turbo
EOF

# Override model with environment variable
export ADAPT_RCA_LLM_MODEL=gpt-4

# Load configuration (gpt-4 will be used)
python -c "from adapt_rca.config import RCAConfig; c = RCAConfig.load(); print(c.llm_model)"
# Output: gpt-4
```

## Installation

To use configuration file support, install the required dependencies:

```bash
# Install with YAML and TOML support
pip install pyyaml tomli  # tomli only needed for Python < 3.11

# Or install from requirements
pip install -r requirements.txt
```

## Validation

Configuration values are automatically validated when loaded:

```python
from adapt_rca.config import RCAConfig

config = RCAConfig.load()

# Validate configuration (raises ValueError if invalid)
config.validate()
```

Validation checks include:
- All numeric values are positive
- LLM provider is valid (`"none"`, `"openai"`, or `"anthropic"`)
- LLM model is specified when provider is not `"none"`
- Confidence threshold is between 0.0 and 1.0
- Log level is valid

## Best Practices

### Development vs Production

**Development:**
```yaml
# dev-config.yaml
llm:
  provider: none  # Disable LLM for faster testing

processing:
  max_events: 100  # Process fewer events

logging:
  level: DEBUG
```

**Production:**
```yaml
# prod-config.yaml
llm:
  provider: openai
  model: gpt-4

processing:
  max_events: 50000

logging:
  level: INFO
  file: /var/log/adapt-rca.log
```

### Security

- **Never commit API keys** to configuration files
- Use environment variables for sensitive data:
  ```bash
  export OPENAI_API_KEY=sk-...
  export ANTHROPIC_API_KEY=sk-ant-...
  ```

### Per-User Configuration

Users can override system-wide configuration:

```bash
# System-wide config
sudo cp adapt-rca.yaml /etc/adapt-rca.yaml

# User-specific override
cp adapt-rca.yaml ~/.adapt-rca.yaml
# Edit ~/.adapt-rca.yaml with user preferences
```

### Project-Specific Configuration

Place configuration in your project directory:

```bash
cd my-project/
cp /path/to/adapt-rca.yaml.example ./adapt-rca.yaml
# Edit adapt-rca.yaml for this project
```

## Troubleshooting

### Configuration not loading

1. Check file permissions:
   ```bash
   ls -la adapt-rca.yaml
   ```

2. Verify file syntax:
   ```bash
   # For YAML
   python -c "import yaml; yaml.safe_load(open('adapt-rca.yaml'))"

   # For TOML (Python 3.11+)
   python -c "import tomllib; tomllib.load(open('adapt-rca.toml', 'rb'))"
   ```

3. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)

   from adapt_rca.config import RCAConfig
   config = RCAConfig.load()
   ```

### Environment variables not working

Ensure variables are exported:
```bash
# Wrong (only set in current shell)
ADAPT_RCA_LLM_PROVIDER=openai

# Correct (exported to child processes)
export ADAPT_RCA_LLM_PROVIDER=openai
```

### Missing dependencies

If you see import errors, install the required packages:

```bash
pip install pyyaml tomli
```

## Migration from Environment-Only Configuration

Existing code using environment variables will continue to work:

```python
# Old code (still works)
from adapt_rca.config import RCAConfig
config = RCAConfig()  # Uses environment variables by default

# New recommended approach
config = RCAConfig.load()  # Tries config files first, then env vars
```

To migrate to configuration files:

1. Document your current environment variables:
   ```bash
   env | grep ADAPT_RCA_ > current-config.txt
   ```

2. Create a configuration file:
   ```bash
   cp adapt-rca.yaml.example adapt-rca.yaml
   # Edit adapt-rca.yaml based on current-config.txt
   ```

3. Test the configuration:
   ```python
   from adapt_rca.config import RCAConfig
   config = RCAConfig.load()
   config.validate()
   ```

4. Optionally remove environment variables once configuration file is working
