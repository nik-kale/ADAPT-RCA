# ADAPT-RCA Troubleshooting Guide

This guide helps you diagnose and resolve common issues when using ADAPT-RCA.

## Table of Contents

- [Installation Issues](#installation-issues)
- [File Loading Errors](#file-loading-errors)
- [LLM Integration Problems](#llm-integration-problems)
- [Performance Issues](#performance-issues)
- [Analysis Quality Issues](#analysis-quality-issues)
- [Configuration Problems](#configuration-problems)
- [Common Error Messages](#common-error-messages)

---

## Installation Issues

### Problem: `ModuleNotFoundError: No module named 'adapt_rca'`

**Cause:** Package not installed or not in Python path.

**Solution:**
```bash
# Install in development mode
pip install -e .

# Or install from PyPI (when published)
pip install adapt-rca
```

**Verify installation:**
```bash
python -c "import adapt_rca; print(adapt_rca.__version__)"
```

### Problem: Missing optional dependencies

**Error:** `ImportError: No module named 'openai'` or `'anthropic'`

**Solution:**
```bash
# Install LLM support
pip install adapt-rca[llm]

# Install web dashboard support
pip install adapt-rca[web]

# Install everything
pip install adapt-rca[all]
```

---

## File Loading Errors

### Problem: `File too large` error

**Error:**
```
ValueError: File size 150.00 MB exceeds maximum allowed size of 100.00 MB
```

**Solution 1:** Increase file size limit via environment variable
```bash
export ADAPT_RCA_MAX_FILE_SIZE_MB=200
```

**Solution 2:** Split large files
```bash
# Split into 100MB chunks
split -b 100M large_log.jsonl log_chunk_

# Process each chunk
for chunk in log_chunk_*; do
    adapt-rca "$chunk" --output "${chunk}_result.json"
done
```

**Solution 3:** Use streaming/batch processing
```python
from adapt_rca.ingestion import load_jsonl

# Process in batches
batch_size = 1000
events = []

for event_dict in load_jsonl("large_file.jsonl"):
    events.append(Event(**event_dict))

    if len(events) >= batch_size:
        # Process batch
        result = analyze_incident_group(events)
        events = []  # Clear for next batch
```

### Problem: `UnicodeDecodeError`

**Error:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0
```

**Cause:** File is not in UTF-8 encoding.

**Solution:** Convert file to UTF-8
```bash
# Check current encoding
file -i your_log_file.log

# Convert from ISO-8859-1 to UTF-8
iconv -f ISO-8859-1 -t UTF-8 your_log_file.log > log_utf8.log

# Use the converted file
adapt-rca log_utf8.log
```

### Problem: `JSON parse error` in JSONL files

**Error:**
```
WARNING: Skipping invalid JSON at line 42: Expecting value: line 1 column 1
```

**Cause:** Malformed JSON on specific lines.

**Solution 1:** Use non-strict mode (default)
```python
# Non-strict mode skips invalid lines
events = list(load_jsonl("file.jsonl", strict=False))
```

**Solution 2:** Validate and clean file
```bash
# Find invalid JSON lines
cat file.jsonl | jq -c . > valid.jsonl 2> errors.log

# Check errors
cat errors.log
```

### Problem: CSV field mapping doesn't work

**Symptoms:** Events missing timestamp, service, or other fields.

**Solution:** Provide explicit field mapping
```python
from adapt_rca.ingestion import load_csv

# Your CSV has columns: time, component, severity, msg
field_mapping = {
    "time": "timestamp",
    "component": "service",
    "severity": "level",
    "msg": "message"
}

events = load_csv("logs.csv", field_mapping=field_mapping)
```

---

## LLM Integration Problems

### Problem: `API key not found`

**Error:**
```
Error: Missing API key for OpenAI
```

**Solution:** Set API key environment variable
```bash
# For OpenAI
export OPENAI_API_KEY="sk-your-key-here"

# For Anthropic
export ANTHROPIC_API_KEY="your-key-here"

# Verify it's set
echo $OPENAI_API_KEY
```

**Permanent solution (add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export OPENAI_API_KEY="sk-your-key"' >> ~/.bashrc
source ~/.bashrc
```

### Problem: LLM timeout errors

**Error:**
```
Error: OpenAI API timeout after 30 seconds
```

**Solution 1:** Increase timeout
```bash
export ADAPT_RCA_LLM_TIMEOUT=60  # 60 seconds
```

**Solution 2:** In Python
```python
from adapt_rca.llm.factory import get_llm_provider

provider = get_llm_provider(
    "openai",
    model="gpt-4",
    timeout=90  # 90 seconds
)
```

### Problem: LLM rate limiting

**Error:**
```
Error: Rate limit exceeded for API requests
```

**Solution:** Add retry logic with exponential backoff
```python
import time
from adapt_rca.reasoning.llm_agent import analyze_with_llm

max_retries = 3
for attempt in range(max_retries):
    try:
        result = analyze_with_llm(incident, llm_provider, graph_dict)
        break
    except Exception as e:
        if "rate" in str(e).lower() and attempt < max_retries - 1:
            wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            raise
```

### Problem: High LLM costs

**Symptoms:** Unexpected API charges.

**Solution 1:** Use cheaper models
```python
# Instead of gpt-4
provider = get_llm_provider("openai", model="gpt-3.5-turbo")

# Or use Anthropic Claude Haiku (cheaper)
provider = get_llm_provider("anthropic", model="claude-3-haiku-20240307")
```

**Solution 2:** Limit token usage
```python
result = llm_provider.complete(
    messages,
    max_tokens=500,  # Limit response length
    temperature=0.3
)
```

**Solution 3:** Fall back to heuristics
```python
# Only use LLM for complex incidents
if len(incident.events) > 100 or len(incident.services) > 5:
    result = analyze_with_llm(incident, llm_provider, graph_dict)
else:
    result = analyze_incident_group(incident)  # Free heuristic analysis
```

---

## Performance Issues

### Problem: Analysis is slow for large incidents

**Symptoms:** Takes minutes to analyze 10K+ events.

**Cause:** O(n²) graph building algorithm.

**Solution 1:** Limit events processed
```bash
export ADAPT_RCA_MAX_EVENTS=5000
```

**Solution 2:** Use time-window grouping
```python
from adapt_rca.reasoning import time_window_grouping

# Break into 15-minute windows
groups = time_window_grouping(events, window_minutes=15)

# Analyze each window separately (can be parallelized)
results = [analyze_incident_group(g) for g in groups]
```

**Solution 3:** Pre-filter events
```python
# Only analyze ERROR and CRITICAL events
critical_events = [e for e in events if e.level in ["ERROR", "CRITICAL", "FATAL"]]
result = analyze_incident_group(critical_events)
```

### Problem: High memory usage

**Symptoms:** Process killed with `OOMKilled` or `MemoryError`.

**Solution:** Use streaming processing
```python
def process_in_batches(file_path, batch_size=1000):
    batch = []

    for event_dict in load_jsonl(file_path):
        batch.append(Event(**event_dict))

        if len(batch) >= batch_size:
            yield IncidentGroup.from_events(batch)
            batch = []

    if batch:
        yield IncidentGroup.from_events(batch)

# Process each batch
for incident in process_in_batches("huge_file.jsonl"):
    result = analyze_incident_group(incident)
    # Store or export result immediately
    export_json(result, f"result_{incident.start_time}.json")
```

---

## Analysis Quality Issues

### Problem: No root causes identified

**Symptoms:** `probable_root_causes` is empty or generic.

**Possible causes:**
1. Events lack timestamps (temporal analysis fails)
2. Events missing service names (can't build graph)
3. Incident too small (< 3 events)
4. All events from same service

**Solution 1:** Check data quality
```python
# Verify events have required fields
for i, event in enumerate(events[:10]):
    print(f"Event {i}:")
    print(f"  Timestamp: {event.timestamp}")
    print(f"  Service: {event.service}")
    print(f"  Level: {event.level}")
    print(f"  Message: {event.message[:50]}...")
```

**Solution 2:** Use LLM for better analysis
```python
# LLM can work without perfect timestamps
result = analyze_with_llm(incident, llm_provider, graph_dict)
```

### Problem: Incorrect root cause identified

**Symptoms:** Analysis points to wrong service.

**Cause:** Timestamps may be incorrect or events lack causality.

**Solution:** Manually verify causal graph
```python
graph = CausalGraph.from_incident_group(incident)

# Check graph structure
print(f"Nodes: {list(graph.nodes.keys())}")
print(f"Root causes: {graph.get_root_causes()}")

# Examine edges
for edge in graph.edges:
    print(f"{edge.from_node} → {edge.to_node} (confidence: {edge.confidence:.2f})")
```

### Problem: Too many recommendations

**Symptoms:** 20+ recommended actions, hard to prioritize.

**Solution:** Filter by priority
```python
# Only show high-priority actions
critical_actions = [
    action for action in result.recommended_actions
    if action.priority <= 2  # Priority 1 or 2 only
]

for action in critical_actions:
    print(f"[P{action.priority}] {action.description}")
```

---

## Configuration Problems

### Problem: Configuration validation fails

**Error:**
```
ValueError: Configuration validation failed:
  - max_events must be positive, got -1
  - llm_provider must be one of {'none', 'openai', 'anthropic'}, got 'gpt4'
```

**Solution:** Fix configuration values
```bash
# Check current values
python -c "from adapt_rca.config import RCAConfig; c = RCAConfig(); print(vars(c))"

# Set correct values
export ADAPT_RCA_MAX_EVENTS=5000
export ADAPT_RCA_LLM_PROVIDER=openai  # not 'gpt4'
```

### Problem: Environment variables not recognized

**Symptoms:** Settings don't change despite setting env vars.

**Solution 1:** Verify environment variables are exported
```bash
# These won't work (only set for current shell)
ADAPT_RCA_MAX_EVENTS=10000

# Correct - export to make available to subprocesses
export ADAPT_RCA_MAX_EVENTS=10000
```

**Solution 2:** Set in Python directly
```python
from adapt_rca.config import RCAConfig

config = RCAConfig()
config.max_events = 10000
config.validate()
```

---

## Common Error Messages

### `PathValidationError: Source node 'api' does not exist in graph`

**Cause:** Trying to add edge before adding nodes.

**Solution:** This is a bug in custom code. Always add nodes before edges:
```python
graph = CausalGraph()
graph.add_node("api")
graph.add_node("db")
graph.add_edge("api", "db")  # Now this works
```

### `ValueError: Confidence must be between 0.0 and 1.0, got 1.5`

**Cause:** Invalid confidence score.

**Solution:** Use valid range [0.0, 1.0]:
```python
root_cause = RootCause(
    description="Database failure",
    confidence=0.95,  # Not 1.5
    evidence=["..."]
)
```

### `TypeError: Event() missing required argument: 'message'`

**Cause:** Creating Event without required field.

**Solution:** Provide all required fields:
```python
event = Event(
    message="Error occurred",  # Required
    level="ERROR",
    service="api",
    timestamp=datetime.now()
)
```

### `ImportError: cannot import name 'analyze_incident' from 'adapt_rca.reasoning'`

**Cause:** Import path changed or function doesn't exist.

**Solution:** Use correct import:
```python
# Correct
from adapt_rca.reasoning import analyze_incident_group

# Or for legacy compatibility
from adapt_rca.reasoning.agent import analyze_incident
```

---

## Getting Help

If you're still experiencing issues:

1. **Check logs:** Enable debug logging
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Search existing issues:** https://github.com/yourusername/ADAPT-RCA/issues

3. **Create a minimal reproduction:**
   ```python
   # Minimal example that reproduces the issue
   from adapt_rca.models import Event
   from adapt_rca.reasoning import analyze_incident_group

   events = [
       Event(message="Test", level="ERROR", service="test")
   ]
   result = analyze_incident_group(events)
   print(result.incident_summary)
   ```

4. **Open an issue:** Include:
   - ADAPT-RCA version
   - Python version
   - Operating system
   - Complete error message
   - Minimal reproduction code

5. **Community support:**
   - GitHub Discussions
   - Stack Overflow (tag: `adapt-rca`)

---

## Performance Benchmarks

Expected performance on common hardware (M1 Mac / modern x86):

| Events | Services | Analysis Time | Memory Usage |
|--------|----------|---------------|--------------|
| 100    | 3        | < 1s          | ~50MB        |
| 1,000  | 10       | ~2s           | ~100MB       |
| 10,000 | 20       | ~15s          | ~500MB       |
| 100,000| 50       | ~3min         | ~2GB         |

If your performance is significantly worse, see [Performance Issues](#performance-issues).

---

## Debug Checklist

When reporting issues, include:

- [ ] ADAPT-RCA version: `python -c "import adapt_rca; print(adapt_rca.__version__)"`
- [ ] Python version: `python --version`
- [ ] Operating system and version
- [ ] Complete error message and stack trace
- [ ] Sample data (if possible)
- [ ] Configuration values
- [ ] Steps to reproduce

---

**Last updated:** 2025-11-16
**Version:** 0.1.0
