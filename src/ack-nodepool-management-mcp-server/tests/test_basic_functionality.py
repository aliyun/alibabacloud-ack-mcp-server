#!/usr/bin/env python3
"""Basic functionality tests for ACK NodePool Management MCP Server."""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handler
import runtime_provider
import server


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration fixture with session scope for reuse."""
    return {
        "allow_write": True,
        "access_key_id": "test_key_id",
        "access_key_secret": "test_secret_key",
        "region_id": "cn-hangzhou",
        "default_cluster_id": "cluster-test123",
        "max_nodes_per_operation": 10,
        "scaling_timeout": 300
    }


@pytest.fixture
def mock_server():
    """Mock FastMCP server fixture with optimized tool registration."""
    server = Mock()
    server._registered_tools = {}
    
    def mock_tool(**kwargs):
        def decorator(func):
            tool_name = kwargs.get('name')
            server._registered_tools[tool_name] = func
            return func
        return decorator
    
    server.tool = mock_tool
    server.name = "ack-nodepool-management-mcp-server"
    return server


class TestBasicFunctionality:
    """Test basic functionality of the ACK NodePool Management server."""
    
    def test_server_creation_with_config(self, test_config):
        """Test server creation with valid configuration."""
        server_instance = server.create_mcp_server(test_config)
        assert server_instance is not None
        assert hasattr(server_instance, 'name')
        assert server_instance.name == "ack-nodepool-management-mcp-server"
    
    def test_server_creation_without_config(self):
        """Test server creation without configuration."""
        server_instance = server.create_mcp_server()
        assert server_instance is not None
        assert hasattr(server_instance, 'name')
    
    @pytest.mark.parametrize("allow_write,expected", [
        (True, True),
        (False, False)
    ])
    def test_handler_initialization(self, mock_server, test_config, allow_write, expected):
        """Test handler initialization with different write settings."""
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=allow_write,
            settings=test_config
        )
        assert handler_instance.server == mock_server
        assert handler_instance.allow_write is expected
        if expected:
            assert handler_instance.settings == test_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])