# Makefile for AlibabaCloud Container Service MCP Server
.PHONY: help test test-verbose test-architecture test-coverage install clean build build-binary build-local build-spec build-all-platforms docker-build

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies using uv
	pip install -r requirements.txt

test: ## Run all tests
	python -m pytest src/tests/ -v

test-verbose: ## Run tests with verbose output
	python -m pytest src/tests/ -vv

test-coverage: ## Run tests with coverage report
	python -m pytest src/tests/ --cov=src --cov-report=html --cov-report=term

test-fast: ## Run tests excluding slow tests
	python -m pytest src/tests/ -v -m "not slow"

test-integration: ## Run integration tests only
	python -m pytest src/tests/ -v -m "integration"

test-unit: ## Run unit tests only
	python -m pytest src/tests/ -v -m "unit"

lint: ## Run code linting, need install ruff
	python -m ruff check src/
	python -m mypy src/ --ignore-missing-imports

lint-fix: # Strict linting (with auto-fix)
	python -m ruff check src/ --fix

format: ## Format code, need install ruff
	python -m ruff format src/

dev-setup: install ## Set up development environment
	@echo "Development environment setup complete!"

run: ## Run the MCP server in development mode
	PYTHONPATH=src python -m src.main_server

run-http: ## Run the MCP server with Streaming HTTP transport
	PYTHONPATH=src python -m src.main_server --transport http --allow-write --host 0.0.0.0 --port 8000

run-sse: ## Run the MCP server with SSE transport
	PYTHONPATH=src python -m src.main_server --transport sse --allow-write --host 0.0.0.0 --port 8000

run-stdio: ## Run the MCP server with stdio transport
	PYTHONPATH=src python -m src.main_server --transport stdio --allow-write

check: lint test ## Run linting and tests
	@echo "All checks passed!"

pre-commit: format lint test ## Run pre-commit checks (format, lint, test)
	@echo "Pre-commit checks completed!"

build: ## Build the package
	python -m build

docker-build-amd64: ## Build Docker image for AMD64 platform
	docker build -t ack-mcp-server:1.0 . -f ./deploy/Dockerfile --platform linux/amd64

docker-build-arm64: ## Build Docker image for ARM64 platform
	docker build -t ack-mcp-server:1.0 . -f ./deploy/Dockerfile --platform linux/arm64

build-binary: ## Build standalone binary using PyInstaller
	@echo "Building standalone binary..."
	@if [ -f ".venv/bin/activate" ]; then \
		echo "Using virtual environment..."; \
		. .venv/bin/activate && python -m pip install pyinstaller; \
		. .venv/bin/activate && python -m PyInstaller --onefile \
		--name alibabacloud-cs-mcp-server \
		--add-data "src/prometheus_metrics_guidance:prometheus_metrics_guidance" \
		--hidden-import fastmcp \
		--hidden-import fastmcp.server \
		--hidden-import fastmcp.client \
		--hidden-import fastmcp.transport \
		--hidden-import loguru \
		--hidden-import pydantic \
		--hidden-import pydantic.fields \
		--hidden-import pydantic.main \
		--hidden-import alibabacloud_cs20151215 \
		--hidden-import alibabacloud_credentials \
		--hidden-import kubernetes \
		--hidden-import kubernetes.client \
		--hidden-import kubernetes.config \
		--hidden-import yaml \
		--hidden-import dotenv \
		--hidden-import aiofiles \
		--hidden-import aiohttp \
		--hidden-import requests \
		--collect-all fastmcp \
		--collect-all pydantic \
		--collect-all loguru \
		--collect-all alibabacloud_cs20151215 \
		--collect-all alibabacloud_credentials \
		--collect-all kubernetes \
		--hidden-import ack_audit_log_handler \
		--hidden-import ack_controlplane_log_handler \
		--hidden-import config \
		--hidden-import interfaces.runtime_provider \
		--hidden-import runtime_provider \
		--hidden-import ack_cluster_handler \
		--hidden-import kubectl_handler \
		--hidden-import ack_prometheus_handler \
		--hidden-import ack_diagnose_handler \
		--hidden-import ack_inspect_handler \
		--hidden-import kubeconfig_context_manager \
		--hidden-import models \
		--hidden-import utils.api_error \
		--hidden-import utils.utils \
		--distpath dist/binary \
		src/main_server.py; \
	else \
		echo "No virtual environment found, using system Python..."; \
		python3 -m pip install pyinstaller; \
		python3 -m PyInstaller --onefile \
		--name alibabacloud-cs-mcp-server \
		--add-data "src/prometheus_metrics_guidance:prometheus_metrics_guidance" \
		--hidden-import fastmcp \
		--hidden-import fastmcp.server \
		--hidden-import fastmcp.client \
		--hidden-import fastmcp.transport \
		--hidden-import loguru \
		--hidden-import pydantic \
		--hidden-import pydantic.fields \
		--hidden-import pydantic.main \
		--hidden-import alibabacloud_cs20151215 \
		--hidden-import alibabacloud_credentials \
		--hidden-import kubernetes \
		--hidden-import kubernetes.client \
		--hidden-import kubernetes.config \
		--hidden-import yaml \
		--hidden-import dotenv \
		--hidden-import aiofiles \
		--hidden-import aiohttp \
		--hidden-import requests \
		--collect-all fastmcp \
		--collect-all pydantic \
		--collect-all loguru \
		--collect-all alibabacloud_cs20151215 \
		--collect-all alibabacloud_credentials \
		--collect-all kubernetes \
		--hidden-import ack_audit_log_handler \
		--hidden-import ack_controlplane_log_handler \
		--hidden-import config \
		--hidden-import interfaces.runtime_provider \
		--hidden-import runtime_provider \
		--hidden-import ack_cluster_handler \
		--hidden-import kubectl_handler \
		--hidden-import ack_prometheus_handler \
		--hidden-import ack_diagnose_handler \
		--hidden-import ack_inspect_handler \
		--hidden-import kubeconfig_context_manager \
		--hidden-import models \
		--hidden-import utils.api_error \
		--hidden-import utils.utils \
		--distpath dist/binary \
		src/main_server.py; \
	fi
	@echo "Binary built successfully in dist/binary/"

build-spec: ## Build binary using PyInstaller spec file
	@echo "Building binary using spec file..."
	@if [ -f ".venv/bin/activate" ]; then \
		echo "Using virtual environment..."; \
		. .venv/bin/activate && python -m pip install pyinstaller; \
		. .venv/bin/activate && python -m PyInstaller alibabacloud-cs-mcp-server.spec; \
	else \
		echo "No virtual environment found, using system Python..."; \
		python3 -m pip install pyinstaller; \
		python3 -m PyInstaller alibabacloud-cs-mcp-server.spec; \
	fi
	@echo "Binary built successfully in dist/"

clean: ## Clean up cache and temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage
	rm -rf build/ dist/ *.egg-info/
	rm -rf dist/binary/
	rm -rf build-scripts/
	rm -f *.spec

.DEFAULT_GOAL := help