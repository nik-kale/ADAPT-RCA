.PHONY: help install install-dev test lint format type-check clean build docker-build docker-run

help:
	@echo "ADAPT-RCA Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install package"
	@echo "  make install-dev      Install package with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test            Run tests"
	@echo "  make test-cov        Run tests with coverage"
	@echo "  make lint            Run linters"
	@echo "  make format          Format code"
	@echo "  make type-check      Run type checker"
	@echo "  make pre-commit      Run pre-commit hooks"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build    Build Docker image"
	@echo "  make docker-run      Run Docker container"
	@echo "  make docker-dev      Run development container"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove build artifacts"
	@echo "  make clean-all       Remove all generated files"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest

test-cov:
	pytest --cov=adapt_rca --cov-report=html --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	black src/ tests/
	ruff check src/ tests/ --fix

type-check:
	mypy src/adapt_rca

pre-commit:
	pre-commit run --all-files

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .eggs/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage coverage.xml

clean-all: clean
	rm -rf .venv/
	find . -type d -name "*.egg" -exec rm -rf {} +

build:
	python -m build

docker-build:
	docker-compose build adapt-rca

docker-run:
	docker-compose up adapt-rca

docker-dev:
	docker-compose --profile dev up adapt-rca-dev

docker-clean:
	docker-compose down -v
	docker image rm adapt-rca:latest adapt-rca:dev 2>/dev/null || true
