# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Package configuration with `pyproject.toml` for proper installation
- Comprehensive logging infrastructure throughout the codebase
- Path validation utilities to prevent path traversal vulnerabilities
- File size limits for ingestion (100MB default)
- Pydantic models for data validation (Event, IncidentGroup, AnalysisResult)
- Time-window based event grouping implementation
- Service-based event grouping
- CLI verbose and debug flags
- Comprehensive type hints throughout codebase
- Input validation and error handling
- CI/CD pipeline with GitHub Actions
  - Automated testing on Python 3.10, 3.11, 3.12
  - Code quality checks (black, ruff, mypy)
  - Security scanning (bandit, safety)
- Pre-commit hooks configuration
- Development dependencies separated in requirements-dev.txt
- Utility functions for file operations
- .editorconfig for consistent code formatting
- py.typed marker for PEP 561 compliance

### Changed
- Configuration now validates environment variables safely
- File loading now uses UTF-8 encoding explicitly
- Exporters now validate output paths and use UTF-8 encoding
- CLI now has proper error handling and exit codes
- Improved error messages throughout

### Fixed
- Security: Unsafe integer conversion in config.py (CVE potential)
- Security: Path traversal vulnerability in file operations
- Security: Missing file size validation (DoS risk)
- Bug: IndexError risk in CLI when no events found
- Bug: Silent JSON decode errors now logged
- Bug: Missing encoding in file operations could cause Unicode errors

### Security
- Added input path validation
- Added output path validation
- Added file size limits to prevent DoS
- Added safe environment variable parsing
- Added logging for security-relevant events

## [0.1.0] - 2025-11-16

### Added
- Initial project structure
- Basic CLI interface
- JSONL file ingestion
- Simple event normalization
- Placeholder reasoning engine
- Causal graph data structure
- Human-readable and JSON output formats
- Basic test suite
- MIT License
- README documentation
- Architecture documentation

[Unreleased]: https://github.com/YOUR-USERNAME/ADAPT-RCA/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR-USERNAME/ADAPT-RCA/releases/tag/v0.1.0
