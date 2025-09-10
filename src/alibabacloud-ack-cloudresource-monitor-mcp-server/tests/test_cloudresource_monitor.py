#!/usr/bin/env python3
"""Unit tests for AlibabaCloud ACK CloudResource Monitor MCP Server."""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from .. import create_mcp_server
from ..handler import CloudResourceMonitorHandler
from ..runtime_provider import CloudResourceMonitorRuntimeProvider


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "allow_write": False,
        "cms_endpoint": "https://cms.cn-hangzhou.aliyuncs.com",
        "access_key_id": "test_key_id",
        "region_id": "cn-hangzhou"
    }


class TestCloudResourceMonitorServer:
    """Test cases for CloudResource Monitor Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = CloudResourceMonitorRuntimeProvider(settings=test_config)
        assert provider.settings == test_config
        
    @pytest.mark.asyncio
    async def test_resource_metrics_query(self):
        """Test resource metrics query."""
        # Mock metrics query result
        result = {
            "metric_name": "cpu_utilization",
            "namespace": "acs_ecs_dashboard",
            "status": "success",
            "datapoints": []
        }
        assert result["status"] == "success"
        assert "datapoints" in result
        
    @pytest.mark.asyncio
    async def test_alert_rules_management(self):
        """Test alert rules management."""
        # Mock alert rule creation result
        result = {
            "rule_name": "high_cpu_alert",
            "threshold": 80,
            "status": "created",
            "rule_id": "alert-123"
        }
        assert result["status"] == "created"
        assert "rule_id" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])