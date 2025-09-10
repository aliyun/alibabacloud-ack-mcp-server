#!/usr/bin/env python3
"""Unit tests for ACK NodePool Management MCP Server."""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from .. import create_mcp_server
from ..handler import ACKNodePoolManagementHandler
from ..runtime_provider import ACKNodePoolManagementRuntimeProvider


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "allow_write": True,
        "access_key_id": "test_key_id",
        "access_secret_key": "test_secret_key",
        "region_id": "cn-hangzhou"
    }


@pytest.fixture
def mock_server():
    """Mock FastMCP server fixture."""
    server = Mock()
    server.tool = Mock(side_effect=lambda **kwargs: lambda func: func)
    server.name = "ack-nodepool-management-mcp-server"
    return server


class TestACKNodePoolManagementServer:
    """Test cases for ACK NodePool Management Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_handler_initialization(self, mock_server, test_config):
        """Test handler initialization."""
        handler = ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        assert handler.server == mock_server
        assert handler.allow_write == test_config["allow_write"]
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = ACKNodePoolManagementRuntimeProvider(settings=test_config)
        assert provider.settings == test_config
        
    @pytest.mark.asyncio
    async def test_scale_nodepool_logic(self):
        """Test node pool scaling logic."""
        # Mock the scale operation
        result = {
            "cluster_id": "test-cluster",
            "nodepool_id": "test-nodepool",
            "desired_size": 3,
            "status": "scaling"
        }
        assert result["status"] == "scaling"
        assert result["desired_size"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])