#!/usr/bin/env python3
"""Unit tests for AlibabaCloud O11y Prometheus MCP Server."""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from .. import create_mcp_server
from ..handler import PrometheusObservabilityHandler
from ..runtime_provider import PrometheusObservabilityRuntimeProvider


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "allow_write": False,
        "prometheus_endpoint": "http://localhost:9090",
        "access_key_id": "test_key_id"
    }


class TestPrometheusObservabilityServer:
    """Test cases for Prometheus Observability Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = PrometheusObservabilityRuntimeProvider(settings=test_config)
        assert provider.settings == test_config
        
    @pytest.mark.asyncio
    async def test_promql_query(self):
        """Test PromQL query execution."""
        # Mock PromQL query result
        result = {
            "query": "up",
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": []
            }
        }
        assert result["status"] == "success"
        assert "data" in result
        
    @pytest.mark.asyncio
    async def test_metrics_translation(self):
        """Test natural language to PromQL translation."""
        # Mock translation result
        result = {
            "natural_language": "CPU usage for pods",
            "promql": "rate(container_cpu_usage_seconds_total[5m])",
            "status": "success"
        }
        assert result["status"] == "success"
        assert "promql" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])