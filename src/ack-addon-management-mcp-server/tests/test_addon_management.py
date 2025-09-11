#!/usr/bin/env python3
"""Unit tests for ACK Addon Management MCP Server."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List
import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, project_root)

# 直接导入模块
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from handler import ACKAddonManagementHandler
from runtime_provider import ACKAddonManagementRuntimeProvider
from server import create_mcp_server


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
    # 创建一个字典来存储注册的工具
    tools = {}
    
    def mock_tool(**kwargs):
        def decorator(func):
            tool_name = kwargs.get('name', func.__name__)
            tools[tool_name] = func
            return func
        return decorator
    
    server.tool = mock_tool
    server.name = "ack-addon-management-mcp-server"
    server.tools = tools
    return server


@pytest.fixture
def mock_context():
    """Mock FastMCP context fixture."""
    context = Mock()
    context.request_context = Mock()
    context.request_context.lifespan_context = Mock()
    
    # 模拟providers数据
    providers = {
        "cs_client": {
            "client": Mock()
        }
    }
    
    def mock_get(key, default=None):
        if key == "providers":
            return providers
        return default
    
    context.request_context.lifespan_context.get = mock_get
    return context


@pytest.fixture
def mock_cs_client():
    """Mock CS client fixture."""
    client = Mock()
    
    # Mock describe_cluster_addons response
    describe_response = Mock()
    describe_response.body = Mock()
    describe_response.body.addons = [
        {
            "name": "nginx-ingress",
            "version": "1.0.0",
            "description": "Nginx Ingress Controller"
        },
        {
            "name": "cluster-autoscaler",
            "version": "2.0.0",
            "description": "Cluster Autoscaler"
        }
    ]
    describe_response.body.request_id = "test-request-id-123"
    client.describe_cluster_addons_with_options_async = AsyncMock(return_value=describe_response)
    
    # Mock install_cluster_addons response
    install_response = Mock()
    install_response.body = Mock()
    install_response.body.task_id = "install-task-123"
    install_response.request_id = "install-request-123"
    client.install_cluster_addons_with_options_async = AsyncMock(return_value=install_response)
    
    # Mock uninstall_cluster_addons response
    uninstall_response = Mock()
    uninstall_response.body = Mock()
    uninstall_response.body.task_id = "uninstall-task-123"
    uninstall_response.request_id = "uninstall-request-123"
    client.un_install_cluster_addons_with_options_async = AsyncMock(return_value=uninstall_response)
    
    # Mock describe_cluster_addon_info response
    info_response = Mock()
    info_response.body = {
        "name": "nginx-ingress",
        "version": "1.0.0",
        "description": "Nginx Ingress Controller",
        "config": {},
        "status": "running"
    }
    info_response.request_id = "info-request-123"
    client.describe_cluster_addon_info_with_options_async = AsyncMock(return_value=info_response)
    
    # Mock modify_cluster_addons response
    modify_response = Mock()
    modify_response.body = Mock()
    modify_response.body.task_id = "modify-task-123"
    modify_response.request_id = "modify-request-123"
    client.modify_cluster_addons_with_options_async = AsyncMock(return_value=modify_response)
    
    return client


class TestACKAddonManagementServer:
    """Test cases for ACK Addon Management Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_handler_initialization(self, mock_server, test_config):
        """Test handler initialization."""
        handler = ACKAddonManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        assert handler.server == mock_server
        assert handler.allow_write == test_config["allow_write"]
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = ACKAddonManagementRuntimeProvider(settings=test_config)
        assert provider.settings == test_config


class TestACKAddonManagementTools:
    """Test cases for ACK Addon Management Tools."""
    
    @pytest.fixture
    def handler_with_tools(self, mock_server, test_config):
        """Create handler with registered tools."""
        handler = ACKAddonManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        return handler, mock_server.tools
    
    @pytest.mark.asyncio
    async def test_describe_cluster_addons(self, handler_with_tools, mock_context, mock_cs_client):
        """Test describe_cluster_addons tool."""
        handler, tools = handler_with_tools
        describe_cluster_addons_func = tools["describe_cluster_addons"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试基本调用
        result = await describe_cluster_addons_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert result["status"] == "success"
        assert result["cluster_id"] == "test-cluster-123"
        assert "addons" in result
        assert len(result["addons"]) == 2
        assert result["addons"][0]["name"] == "nginx-ingress"
        
        # 验证调用参数
        mock_cs_client.describe_cluster_addons_with_options_async.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_describe_cluster_addons_with_filters(self, handler_with_tools, mock_context, mock_cs_client):
        """Test describe_cluster_addons tool with filters."""
        handler, tools = handler_with_tools
        describe_cluster_addons_func = tools["describe_cluster_addons"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试带过滤条件的调用
        result = await describe_cluster_addons_func(
            cluster_id="test-cluster-123",
            addon_name="nginx-ingress",
            component_name="controller",
            ctx=mock_context
        )
        
        assert result["status"] == "success"
        assert result["cluster_id"] == "test-cluster-123"
        
    @pytest.mark.asyncio
    async def test_install_cluster_addons(self, handler_with_tools, mock_context, mock_cs_client):
        """Test install_cluster_addons tool."""
        handler, tools = handler_with_tools
        install_cluster_addons_func = tools["install_cluster_addons"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试安装插件
        addons = [
            {
                "name": "nginx-ingress",
                "version": "1.0.0",
                "config": {"replicaCount": 2}
            }
        ]
        
        result = await install_cluster_addons_func(
            cluster_id="test-cluster-123",
            addons=addons,
            ctx=mock_context
        )
        
        assert result["status"] == "installing"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["task_id"] == "install-task-123"
        
        # 验证调用参数
        mock_cs_client.install_cluster_addons_with_options_async.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_uninstall_cluster_addons(self, handler_with_tools, mock_context, mock_cs_client):
        """Test uninstall_cluster_addons tool."""
        handler, tools = handler_with_tools
        uninstall_cluster_addons_func = tools["uninstall_cluster_addons"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试卸载插件
        addons = [
            {
                "name": "nginx-ingress"
            }
        ]
        
        result = await uninstall_cluster_addons_func(
            cluster_id="test-cluster-123",
            addons=addons,
            ctx=mock_context
        )
        
        assert result["status"] == "uninstalling"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["task_id"] == "uninstall-task-123"
        
        # 验证调用参数
        mock_cs_client.un_install_cluster_addons_with_options_async.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_describe_cluster_addon_info(self, handler_with_tools, mock_context, mock_cs_client):
        """Test describe_cluster_addon_info tool."""
        handler, tools = handler_with_tools
        describe_cluster_addon_info_func = tools["describe_cluster_addon_info"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试获取插件详情
        result = await describe_cluster_addon_info_func(
            cluster_id="test-cluster-123",
            addon_name="nginx-ingress",
            ctx=mock_context
        )
        
        assert result["status"] == "success"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["addon_name"] == "nginx-ingress"
        assert "addon_info" in result
        
    @pytest.mark.asyncio
    async def test_modify_cluster_addons(self, handler_with_tools, mock_context, mock_cs_client):
        """Test modify_cluster_addons tool."""
        handler, tools = handler_with_tools
        modify_cluster_addons_func = tools["modify_cluster_addons"]
        
        # 设置mock客户端
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {
                "client": mock_cs_client
            }
        }
        
        # 测试修改插件
        addons = [
            {
                "name": "nginx-ingress",
                "config": {"replicaCount": 3}
            }
        ]
        
        result = await modify_cluster_addons_func(
            cluster_id="test-cluster-123",
            addons=addons,
            ctx=mock_context
        )
        
        assert result["status"] == "modifying"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["task_id"] == "modify-task-123"
        
        # 验证调用参数
        mock_cs_client.modify_cluster_addons_with_options_async.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_write_operations_disabled(self, mock_server, mock_context, test_config):
        """Test write operations when disabled."""
        # 创建不允许写操作的handler
        handler = ACKAddonManagementHandler(
            server=mock_server,
            allow_write=False,  # 禁用写操作
            settings=test_config
        )
        
        tools = mock_server.tools
        install_cluster_addons_func = tools["install_cluster_addons"]
        
        # 测试安装插件（应该失败）
        addons = [
            {
                "name": "nginx-ingress"
            }
        ]
        
        result = await install_cluster_addons_func(
            cluster_id="test-cluster-123",
            addons=addons,
            ctx=mock_context
        )
        
        assert result["error"] == "Write operations are disabled"
        assert result["status"] == "failed"
        
    @pytest.mark.asyncio
    async def test_no_client_in_context(self, handler_with_tools, mock_context):
        """Test handling when no client in context."""
        handler, tools = handler_with_tools
        describe_cluster_addons_func = tools["describe_cluster_addons"]
        
        # 模拟没有客户端的情况
        mock_context.request_context.lifespan_context.get.return_value = {
            "cs_client": {}
        }
        
        result = await describe_cluster_addons_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert result["error"] == "CS client not available in lifespan context"
        assert result["status"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])