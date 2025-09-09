# Makefile for formatting and linting Python code

# Default Python command
PYTHON ?= python3
SRC_DIR ?= src

# Help target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  format     - Format code with black"
	@echo "  isort      - Sort imports with isort"
	@echo "  lint       - Lint code with pylint"
	@echo "  flake8     - Lint code with flake8"
	@echo "  mypy       - Type check with mypy"
	@echo "  check      - Run all checks"
	@echo "  fix        - Auto-fix issues"
	@echo "  install    - Install dev dependencies"

# Install development dependencies
.PHONY: install
install:
	$(PYTHON) -m pip install black pylint flake8 mypy isort

# Format code
.PHONY: format
format:
	black $(SRC_DIR)

# Sort imports
.PHONY: isort
isort:
	isort $(SRC_DIR)

# Lint code
.PHONY: lint
lint:
	pylint --rcfile=.pylintrc $(SRC_DIR)

# Lint with flake8
.PHONY: flake8
flake8:
	flake8 --config=.flake8 $(SRC_DIR)

# Type checking
.PHONY: mypy
mypy:
	mypy --config-file=mypy.ini $(SRC_DIR)

# Run all checks
.PHONY: check
check: format isort lint flake8 mypy

# Auto-fix issues
.PHONY: fix
fix: format isort