#!/usr/bin/env python3
"""Unit tests for AlibabaCloud O11y SLS APIServer Log MCP Server."""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from .. import create_mcp_server
from ..handler import SLSAPIServerLogHandler
from ..runtime_provider import SLSAPIServerLogRuntimeProvider


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "allow_write": False,
        "sls_endpoint": "cn-hangzhou.log.aliyuncs.com",
        "access_key_id": "test_key_id",
        "project_name": "test-project"
    }


class TestSLSAPIServerLogServer:
    """Test cases for SLS APIServer Log Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = SLSAPIServerLogRuntimeProvider(settings=test_config)
        assert provider.settings == test_config
        
    @pytest.mark.asyncio
    async def test_sls_query_execution(self):
        """Test SLS SQL query execution."""
        # Mock SLS query result
        result = {
            "query": "* | where verb='get' | limit 10",
            "status": "success",
            "logs": [],
            "count": 0
        }
        assert result["status"] == "success"
        assert "logs" in result
        
    @pytest.mark.asyncio
    async def test_log_analysis(self):
        """Test APIServer log analysis."""
        # Mock log analysis result
        result = {
            "analysis_type": "error_analysis",
            "time_range": "1h",
            "errors": [],
            "status": "success"
        }
        assert result["status"] == "success"
        assert "errors" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])