"""
Constants for ADAPT-RCA.

This module centralizes all configuration constants, thresholds, and magic numbers
used throughout the codebase.
"""

# File handling constants
DEFAULT_MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = DEFAULT_MAX_FILE_SIZE_MB * 1024 * 1024

# Event processing constants
DEFAULT_MAX_EVENTS = 5000
SAMPLE_EVENTS_DISPLAY_COUNT = 5

# Time window constants
DEFAULT_TIME_WINDOW_MINUTES = 15
TIME_CORRELATION_WINDOW_MINUTES = 5  # For causal graph temporal correlation
TIME_CORRELATION_WINDOW_SECONDS = TIME_CORRELATION_WINDOW_MINUTES * 60

# LLM constants
DEFAULT_LLM_TIMEOUT_SECONDS = 30
DEFAULT_LLM_TEMPERATURE = 0.3
DEFAULT_LLM_MAX_TOKENS = 1500
LLM_ANALYSIS_TEMPERATURE = 0.3

# Analysis thresholds
REPEATED_ERROR_THRESHOLD = 0.3  # 30% of events
HIGH_CONFIDENCE_THRESHOLD = 0.7
MEDIUM_CONFIDENCE_THRESHOLD = 0.6
LOW_CONFIDENCE_THRESHOLD = 0.4
MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0

# Priority levels
PRIORITY_CRITICAL = 1
PRIORITY_HIGH = 2
PRIORITY_MEDIUM = 3
PRIORITY_LOW = 4
PRIORITY_INFO = 5

# Graph visualization
MAX_TOP_SERVICES_DISPLAY = 5  # Top services to show in analysis
MAX_EDGES_DISPLAY = 5  # Top edges to show in output
MAX_ERROR_MESSAGE_LENGTH = 100  # Max chars for error messages in output

# Web dashboard
WEB_UPLOAD_MAX_SIZE_MB = 50
WEB_ALLOWED_EXTENSIONS = {".jsonl", ".json", ".csv", ".log", ".txt"}

# Supported categories
VALID_ACTION_CATEGORIES = {"investigate", "fix", "monitor", "document"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}
VALID_LLM_PROVIDERS = {"none", "openai", "anthropic"}

# Default models
DEFAULT_OPENAI_MODEL = "gpt-4"
DEFAULT_ANTHROPIC_MODEL = "claude-3-sonnet-20240229"

# Text parsing
MAX_LOG_LINE_LENGTH = 10000  # Prevent memory issues with very long lines
GENERIC_LOG_PATTERN_GROUPS = 4  # Number of capture groups in generic pattern
