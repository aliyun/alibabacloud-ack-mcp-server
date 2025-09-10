# Makefile for AlibabaCloud Container Service MCP Server
.PHONY: help test test-verbose test-architecture test-coverage install clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	uv sync

test: ## Run all tests
	python -m pytest src/tests/ -v

test-verbose: ## Run tests with verbose output
	python -m pytest src/tests/ -vv

test-architecture: ## Run architecture tests only
	python -m pytest src/tests/test_architecture.py -v

test-coverage: ## Run tests with coverage report
	python -m pytest src/tests/ --cov=src --cov-report=html --cov-report=term

test-fast: ## Run tests excluding slow tests
	python -m pytest src/tests/ -v -m "not slow"

test-integration: ## Run integration tests only
	python -m pytest src/tests/ -v -m "integration"

test-unit: ## Run unit tests only
	python -m pytest src/tests/ -v -m "unit"

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage

lint: ## Run code linting
	python -m ruff check src/
	python -m mypy src/ --ignore-missing-imports

format: ## Format code
	python -m ruff format src/

dev-setup: install ## Set up development environment
	@echo "Development environment setup complete!"

.DEFAULT_GOAL := help