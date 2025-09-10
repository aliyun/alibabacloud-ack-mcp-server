#!/bin/bash
# Test runner script for AlibabaCloud Container Service MCP Server

set -e

echo "🚀 AlibabaCloud Container Service MCP Server Test Suite"
echo "=================================================="

# Change to project root directory
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    echo "📦 Installing test dependencies..."
    pip install pytest pytest-asyncio
fi

# Run tests based on argument
case "${1:-all}" in
    "architecture"|"arch")
        echo "🏗️ Running architecture tests..."
        python -m pytest src/tests/test_architecture.py -v
        ;;
    "fast")
        echo "⚡ Running fast tests..."
        python -m pytest src/tests/ -v -m "not slow"
        ;;
    "verbose"|"v")
        echo "📝 Running all tests with verbose output..."
        python -m pytest src/tests/ -vv
        ;;
    "coverage"|"cov")
        echo "📊 Running tests with coverage..."
        python -m pytest src/tests/ --cov=src --cov-report=term-missing
        ;;
    "all"|*)
        echo "🧪 Running all tests..."
        python -m pytest src/tests/ -v
        ;;
esac

echo ""
echo "✅ Test execution completed!"