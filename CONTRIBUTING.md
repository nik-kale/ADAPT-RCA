# Contributing to ADAPT-RCA

Thank you for your interest in contributing to ADAPT-RCA! We welcome contributions from the community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a new branch for your changes
4. Make your changes
5. Push to your fork
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip and virtualenv

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/ADAPT-RCA.git
cd ADAPT-RCA

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-kafka-ingestion` - New features
- `fix/timestamp-parsing-bug` - Bug fixes
- `docs/update-readme` - Documentation updates
- `refactor/improve-logging` - Code refactoring

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
feat: add Kafka log ingestion support
fix: resolve timestamp parsing for ISO 8601 dates
docs: update installation instructions
test: add tests for event grouping
refactor: simplify causal graph building
chore: update dependencies
```

## Submitting Changes

1. **Test your changes**: Ensure all tests pass
   ```bash
   pytest
   ```

2. **Run linters**: Fix any linting issues
   ```bash
   black src/ tests/
   ruff check src/ tests/ --fix
   mypy src/
   ```

3. **Update documentation**: If you've added features or changed behavior

4. **Create a pull request**:
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changed and why
   - Include examples if applicable

### Pull Request Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] No merge conflicts
- [ ] Added/updated tests for changes

## Code Style

We use several tools to maintain code quality:

### Black (Code Formatting)
```bash
black src/ tests/
```

### Ruff (Linting)
```bash
ruff check src/ tests/ --fix
```

### MyPy (Type Checking)
```bash
mypy src/
```

### Pre-commit Hooks

Pre-commit hooks automatically run these checks before each commit:
```bash
pre-commit install
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=adapt_rca --cov-report=html

# Run specific test file
pytest tests/test_parsing.py

# Run specific test
pytest tests/test_parsing.py::test_normalize_event_basic
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names
- Test both happy paths and error cases

Example:
```python
def test_time_window_grouping_creates_separate_groups():
    """Events outside time window should be in separate groups."""
    # Test implementation
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Short description.

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When something is wrong
    """
```

### README and Docs

- Update README.md for user-facing changes
- Update docs/ for architectural changes
- Include examples for new features

## Adding New Features

When adding significant new features:

1. **Discuss first**: Open an issue to discuss the feature
2. **Design**: Document the design in the issue
3. **Implement**: Create implementation with tests
4. **Document**: Add documentation and examples
5. **Review**: Submit PR for review

## Reporting Bugs

When reporting bugs, include:

- Python version
- ADAPT-RCA version
- Operating system
- Minimal reproduction example
- Expected vs actual behavior
- Error messages/stack traces

## Questions?

- Open an issue for questions
- Check existing issues and documentation
- Be respectful and patient

Thank you for contributing! 🎉
