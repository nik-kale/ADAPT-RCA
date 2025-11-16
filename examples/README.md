# ADAPT-RCA Examples

This directory contains comprehensive examples demonstrating various features of ADAPT-RCA.

## Directory Structure

```
examples/
├── data/               # Sample log files
│   ├── sample_csv.csv           # CSV format logs
│   ├── sample_syslog.log        # Syslog format
│   └── sample_multi_service.jsonl  # Multi-service incident (JSONL)
├── scripts/            # Example scripts
│   ├── analyze_csv.py           # Basic CSV analysis
│   ├── analyze_with_llm.py      # LLM-powered analysis
│   └── visualize_graph.py       # Graph visualization
├── output/             # Generated output files (created on first run)
└── README.md           # This file
```

## Quick Start

### 1. Basic CSV Analysis

Analyze a CSV log file and export results in multiple formats:

```bash
python examples/scripts/analyze_csv.py
```

**Output:**
- Console summary of incident analysis
- JSON export (`output/analysis_result.json`)
- Markdown report (`output/analysis_report.md`)
- Mermaid causal graph (`output/causal_graph.mmd`)

### 2. LLM-Powered Analysis

Use OpenAI GPT-4 or Anthropic Claude for AI-powered root cause analysis:

```bash
# With OpenAI
export OPENAI_API_KEY="your-api-key-here"
python examples/scripts/analyze_with_llm.py

# Or with Anthropic
export ANTHROPIC_API_KEY="your-api-key-here"
python examples/scripts/analyze_with_llm.py
```

**Features:**
- Compares LLM vs heuristic analysis
- Shows token usage and cost
- Provides more detailed insights

### 3. Causal Graph Visualization

Build and visualize temporal dependency graphs:

```bash
python examples/scripts/visualize_graph.py
```

**Output:**
- Mermaid diagram (view at https://mermaid.live)
- DOT format for Graphviz

To generate a PNG image from DOT:
```bash
dot -Tpng examples/output/causal_graph.dot -o graph.png
```

## Using the CLI

ADAPT-RCA also provides a command-line interface:

### Analyze CSV logs
```bash
adapt-rca examples/data/sample_csv.csv --format csv --output results.json
```

### Analyze with LLM
```bash
export OPENAI_API_KEY="your-key"
adapt-rca examples/data/sample_multi_service.jsonl \
  --use-llm \
  --llm-provider openai \
  --llm-model gpt-4 \
  --export-markdown report.md \
  --export-graph graph.mmd
```

### Analyze syslog
```bash
adapt-rca examples/data/sample_syslog.log --format syslog
```

## Sample Data Descriptions

### sample_csv.csv
A database connection pool exhaustion incident affecting multiple services:
- **Root cause:** Database connection limit reached
- **Impact:** API gateway timeouts, frontend errors
- **Duration:** ~40 seconds
- **Services:** database, api-gateway, web-frontend, cache-service

### sample_syslog.log
Same incident as CSV but in syslog format. Demonstrates ADAPT-RCA's ability to parse different log formats.

### sample_multi_service.jsonl
Complex e-commerce system incident with cascading failures:
- **Root cause:** Payment service database deadlock
- **Impact:** Order processing, inventory, notifications
- **Services affected:** 10+ microservices
- **Demonstrates:**
  - Temporal causality detection
  - Circuit breaker patterns
  - Service dependency chains

## Advanced Usage

### Custom Field Mapping (CSV)

```python
from adapt_rca.ingestion import load_csv

# Map your CSV columns to ADAPT-RCA fields
field_mapping = {
    "time": "timestamp",
    "component": "service",
    "severity": "level",
    "msg": "message"
}

events = load_csv("custom.csv", field_mapping=field_mapping)
```

### Custom Log Patterns (Text)

```python
from adapt_rca.ingestion import load_text_log

# Define a custom regex pattern with named groups
custom_pattern = r'^(?P<timestamp>\\d{4}-\\d{2}-\\d{2}) (?P<level>\\w+) (?P<message>.+)$'

events = load_text_log("custom.log", custom_pattern=custom_pattern)
```

### Time-Window Grouping

```python
from adapt_rca.reasoning import time_window_grouping

# Group events that occur within 15-minute windows
groups = time_window_grouping(events, window_minutes=15)

for group in groups:
    result = analyze_incident_group(group)
    print(f"Incident at {group.start_time}: {result.incident_summary}")
```

## Configuration

### Environment Variables

```bash
# LLM configuration
export ADAPT_RCA_LLM_PROVIDER=openai
export ADAPT_RCA_LLM_MODEL=gpt-4
export ADAPT_RCA_LLM_TIMEOUT=30

# Processing limits
export ADAPT_RCA_MAX_EVENTS=5000
export ADAPT_RCA_MAX_FILE_SIZE_MB=100
export ADAPT_RCA_TIME_WINDOW=15
```

### Python Configuration

```python
from adapt_rca.config import RCAConfig

config = RCAConfig()
config.max_events = 10000
config.time_window_minutes = 30
config.llm_timeout = 60
config.validate()  # Validates all settings
```

## Troubleshooting

### "File too large" error
Increase the file size limit:
```bash
export ADAPT_RCA_MAX_FILE_SIZE_MB=200
```

### LLM timeout
Increase timeout for slower API responses:
```bash
export ADAPT_RCA_LLM_TIMEOUT=60
```

### Missing dependencies
Install optional dependencies:
```bash
pip install adapt-rca[llm]  # For LLM support
pip install adapt-rca[web]  # For web dashboard
pip install adapt-rca[all]  # Everything
```

## Further Reading

- [Main README](../README.md) - Project overview
- [API Documentation](../docs/) - Full API reference
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute
- [CODE_REVIEW.md](../CODE_REVIEW.md) - Improvement roadmap

## Questions or Issues?

Please open an issue on GitHub: https://github.com/yourusername/ADAPT-RCA/issues
