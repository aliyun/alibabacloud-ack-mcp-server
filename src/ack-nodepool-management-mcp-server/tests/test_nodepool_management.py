#!/usr/bin/env python3
"""Unit tests for ACK NodePool Management MCP Server."""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
import handler
import runtime_provider


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Test configuration fixture with session scope for better performance."""
    return {
        "allow_write": True,
        "access_key_id": "test_key_id",
        "access_key_secret": "test_secret_key",
        "region_id": "cn-hangzhou"
    }


@pytest.fixture
def mock_server():
    """Mock FastMCP server fixture."""
    server = Mock()
    # Store registered tools
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


@pytest.fixture
def mock_cs_client():
    """Mock CS client fixture."""
    client = Mock()
    # Set up all required async mock methods
    async_methods = [
        "describe_cluster_node_pools_with_options_async",
        "describe_cluster_node_pool_detail_with_options_async",
        "scale_cluster_node_pool_with_options_async",
        "remove_node_pool_nodes_with_options_async",
        "create_cluster_node_pool_with_options_async",
        "delete_cluster_nodepool_with_options_async",
        "modify_cluster_node_pool_with_options_async",
        "modify_node_pool_node_config_with_options_async",
        "upgrade_cluster_nodepool_with_options_async",
        "describe_node_pool_vuls_with_options_async",
        "fix_node_pool_vuls_with_options_async",
        "repair_cluster_node_pool_with_options_async",
        "sync_cluster_node_pool_with_options_async",
        "attach_instances_to_node_pool_with_options_async",
        "create_autoscaling_config_with_options_async",
        "describe_cluster_attach_scripts_with_options_async"
    ]
    
    for method_name in async_methods:
        setattr(client, method_name, AsyncMock())
    
    return client


@pytest.fixture
def mock_context(mock_cs_client):
    """Mock FastMCP context fixture."""
    context = Mock()
    context.request_context = Mock()
    context.request_context.lifespan_context = {
        "providers": {
            "cs_client": {
                "client": mock_cs_client,
                "type": "alibaba_cloud_cs",
                "region": "cn-hangzhou",
                "initialized": True
            }
        }
    }
    return context


class TestHelpers:
    """Helper methods for tests to reduce duplication."""
    
    @staticmethod
    def create_handler_and_get_tool(mock_server, test_config, tool_name: str):
        """Create handler instance and get tool function."""
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        tool_func = mock_server._registered_tools.get(tool_name)
        assert tool_func is not None, f"Tool {tool_name} not found in registered tools"
        return handler_instance, tool_func
    
    @staticmethod
    def create_mock_response(body_data: Optional[Dict] = None, request_id: str = "test-request-123"):
        """Create a standardized mock response."""
        mock_response = Mock()
        mock_response.request_id = request_id
        
        if body_data:
            if isinstance(body_data, dict):
                mock_response.body = Mock()
                for key, value in body_data.items():
                    setattr(mock_response.body, key, value)
            else:
                mock_response.body = body_data
        else:
            mock_response.body = Mock()
            
        return mock_response


class TestACKNodePoolManagementServer:
    """Test cases for ACK NodePool Management Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server_instance = server.create_mcp_server(test_config)
        assert server_instance is not None
        assert hasattr(server_instance, 'name')
        
    def test_handler_initialization(self, mock_server, test_config):
        """Test handler initialization."""
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        assert handler_instance.server == mock_server
        assert handler_instance.allow_write == test_config["allow_write"]
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = runtime_provider.ACKNodePoolManagementRuntimeProvider(test_config)
        assert provider.config is not None
        assert provider.config["region_id"] == "cn-hangzhou"
    
    @pytest.mark.asyncio
    async def test_describe_cluster_node_pools(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test describe cluster node pools functionality."""
        # Setup mock response using helper
        mock_response = TestHelpers.create_mock_response({
            "nodepools": [{
                "nodepool_id": "np-test123",
                "name": "test-nodepool",
                "type": "ess",
                "status": {"state": "active", "healthy_nodes": 3}
            }]
        }, "req-test123")
        mock_cs_client.describe_cluster_node_pools_with_options_async.return_value = mock_response
        
        # Create handler and get tool using helper
        handler_instance, describe_tool = TestHelpers.create_handler_and_get_tool(
            mock_server, test_config, 'describe_cluster_node_pools'
        )
        
        # Test the function
        result = await describe_tool(
            cluster_id="cluster-test123",
            nodepool_name="test-nodepool",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepools" in result
        assert result["cluster_id"] == "cluster-test123"
        
        # Test with container_runtime parameter
        result_with_runtime = await describe_tool(
            cluster_id="cluster-test123",
            nodepool_name="test-nodepool",
            container_runtime="containerd",
            ctx=mock_context
        )
        
        assert "cluster_id" in result_with_runtime
        assert "nodepools" in result_with_runtime
        assert result_with_runtime["cluster_id"] == "cluster-test123"
        assert result_with_runtime["runtime_filter"] == "containerd"
    
    @pytest.mark.asyncio
    async def test_describe_cluster_node_pool_detail(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test describe cluster node pool detail functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = {
            "nodepool_id": "np-test123",
            "name": "test-nodepool",
            "scaling_group": {"desired_size": 3, "instance_types": ["ecs.g6.large"]}
        }
        mock_cs_client.describe_cluster_node_pool_detail_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        detail_tool = mock_server._registered_tools.get('describe_cluster_node_pool_detail')
        assert detail_tool is not None
        
        # Test the function
        result = await detail_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "nodepool_info" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
    
    @pytest.mark.asyncio
    async def test_scale_nodepool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test node pool scaling functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "task-scale123"
        mock_response.request_id = "req-scale123"
        mock_cs_client.scale_cluster_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        scale_tool = mock_server._registered_tools.get('scale_nodepool')
        assert scale_tool is not None
        
        # Test the function
        result = await scale_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            desired_size=5,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "desired_size" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["desired_size"] == 5
        assert result["status"] == "scaling"
    
    @pytest.mark.asyncio
    async def test_remove_nodepool_nodes(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test remove node pool nodes functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "task-remove123"
        mock_response.request_id = "req-remove123"
        mock_cs_client.remove_node_pool_nodes_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        remove_tool = mock_server._registered_tools.get('remove_nodepool_nodes')
        assert remove_tool is not None
        
        # Test the function
        result = await remove_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            instance_ids=["i-test123", "i-test456"],
            release_node=True,
            drain_node=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "instance_ids" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["instance_ids"] == ["i-test123", "i-test456"]
        assert result["status"] == "removing"
    
    @pytest.mark.asyncio
    async def test_write_operations_disabled(self, mock_server, mock_context, test_config):
        """Test that write operations are properly disabled when allow_write=False."""
        # Create handler with write disabled
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=False,  # Disable write operations
            settings=test_config
        )
        
        # Get the scale tool
        scale_tool = mock_server._registered_tools.get('scale_nodepool')
        assert scale_tool is not None
        
        # Test that write operation is blocked
        result = await scale_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            desired_size=5,
            ctx=mock_context
        )
        
        assert "error" in result
        assert "Write operations are disabled" in result["error"]
    
    @pytest.mark.asyncio
    async def test_context_access_failure(self, mock_server, test_config):
        """Test handling of context access failure."""
        # Create invalid context
        invalid_context = Mock()
        invalid_context.request_context = None
        
        # Create handler
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the describe tool
        describe_tool = mock_server._registered_tools.get('describe_cluster_node_pools')
        assert describe_tool is not None
        
        # Test context access failure
        result = await describe_tool(
            cluster_id="cluster-test123",
            ctx=invalid_context
        )
        
        assert "error" in result
        assert "Failed to access lifespan context" in result["error"]

    @pytest.mark.asyncio
    async def test_describe_nodepool_vuls(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test describe nodepool vulnerabilities functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.vul_records = [{
            "instance_id": "i-test123",
            "node_name": "cn-hangzhou.192.168.1.1",
            "vul_list": [{
                "name": "oval:com.redhat.rhsa:def:20193197",
                "alias_name": "RHSA-2019:3197-Important: sudo security update",
                "necessity": "asap",
                "cve_list": ["CVE-2017-10268"],
                "need_reboot": False
            }]
        }]
        mock_response.request_id = "test-vuls-request-123"
        mock_cs_client.describe_node_pool_vuls_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        describe_vuls_tool = mock_server._registered_tools.get('describe_nodepool_vuls')
        assert describe_vuls_tool is not None
        
        # Test the function
        result = await describe_vuls_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            necessity="asap",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "vulnerability_info" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["necessity_filter"] == "asap"
    
    @pytest.mark.asyncio
    async def test_fix_nodepool_vuls(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test fix nodepool vulnerabilities functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "test-fix-vuls-task-123"
        mock_response.request_id = "test-fix-vuls-request-123"
        mock_cs_client.fix_node_pool_vuls_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        fix_vuls_tool = mock_server._registered_tools.get('fix_nodepool_vuls')
        assert fix_vuls_tool is not None
        
        # Test the function
        result = await fix_vuls_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            vuls=["oval:com.redhat.rhsa:def:20193197"],
            nodes=["cn-hangzhou.192.168.1.1"],
            max_parallelism=2,
            auto_restart=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "fixing"
        assert result["vuls_count"] == 1
        assert result["nodes_count"] == 1
        assert result["max_parallelism"] == 2
        assert result["auto_restart"] == True
    
    @pytest.mark.asyncio
    async def test_repair_cluster_node_pool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test repair cluster node pool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "test-repair-task-123"
        mock_response.request_id = "test-repair-request-123"
        mock_cs_client.repair_cluster_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        repair_tool = mock_server._registered_tools.get('repair_cluster_node_pool')
        assert repair_tool is not None
        
        # Test the function
        result = await repair_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            nodes=["cn-hangzhou.192.168.1.1"],
            operations=[{
                "operation_id": "restart.kubelet",
                "args": []
            }],
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "repairing"
        assert result["nodes_count"] == 1
        assert result["operations_count"] == 1
    
    @pytest.mark.asyncio
    async def test_sync_cluster_node_pool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test sync cluster node pool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.request_id = "test-sync-request-123"
        mock_cs_client.sync_cluster_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        sync_tool = mock_server._registered_tools.get('sync_cluster_node_pool')
        assert sync_tool is not None
        
        # Test the function
        result = await sync_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "status" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "syncing"
    
    @pytest.mark.asyncio
    async def test_attach_instances_to_node_pool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test attach instances to node pool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "test-attach-task-123"
        mock_response.request_id = "test-attach-request-123"
        mock_cs_client.attach_instances_to_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        attach_tool = mock_server._registered_tools.get('attach_instances_to_node_pool')
        assert attach_tool is not None
        
        # Test the function
        result = await attach_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            instances=["i-instance123", "i-instance456"],
            password="test-password",
            format_disk=False,
            keep_instance_name=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "attaching"
        assert result["instances_count"] == 2
        assert result["instances"] == ["i-instance123", "i-instance456"]
        assert result["format_disk"] == False
        assert result["keep_instance_name"] == True
    
    @pytest.mark.asyncio
    async def test_create_autoscaling_config(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test create autoscaling config functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.request_id = "test-autoscaling-request-123"
        mock_cs_client.create_autoscaling_config_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        autoscaling_tool = mock_server._registered_tools.get('create_autoscaling_config')
        assert autoscaling_tool is not None
        
        # Test the function
        result = await autoscaling_tool(
            cluster_id="test-cluster-123",
            cool_down_duration="10m",
            unneeded_duration="30m",
            utilize_utilization_threshold="0.5",
            gpu_utilization_threshold="0.8",
            scan_interval="30s",
            scale_down_enabled=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "status" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["status"] == "created"
        assert result["cool_down_duration"] == "10m"
        assert result["unneeded_duration"] == "30m"
        assert result["utilize_utilization_threshold"] == "0.5"
        assert result["gpu_utilization_threshold"] == "0.8"
        assert result["scan_interval"] == "30s"
        assert result["scale_down_enabled"] == True
    
    @pytest.mark.asyncio
    async def test_describe_cluster_attach_scripts(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test describe cluster attach scripts functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.scripts = "#!/bin/bash\n# Attach script content\necho 'Attaching node to cluster'"
        mock_response.request_id = "test-scripts-request-123"
        mock_cs_client.describe_cluster_attach_scripts_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        attach_scripts_tool = mock_server._registered_tools.get('describe_cluster_attach_scripts')
        assert attach_scripts_tool is not None
        
        # Test the function
        result = await attach_scripts_tool(
            cluster_id="test-cluster-123",
            nodepool_id="np-test123",
            format_disk=False,
            keep_instance_name=True,
            arch="amd64",
            options="--debug",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "scripts_info" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["nodepool_id"] == "np-test123"
        assert result["format_disk"] == False
        assert result["keep_instance_name"] == True
        assert result["arch"] == "amd64"
        assert result["options"] == "--debug"
    
    @pytest.mark.asyncio
    async def test_create_cluster_node_pool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test create cluster node pool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.nodepool_id = "np-new123"
        mock_response.body.task_id = "task-create123"
        mock_response.request_id = "req-create123"
        mock_cs_client.create_cluster_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        create_tool = mock_server._registered_tools.get('create_cluster_node_pool')
        assert create_tool is not None
        
        # Test the function
        result = await create_tool(
            cluster_id="cluster-test123",
            nodepool_name="test-new-nodepool",
            instance_types=["ecs.g6.large"],
            vswitch_ids=["vsw-test123"],
            desired_size=3,
            max_size=5,
            min_size=1,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-new123"
        assert result["status"] == "creating"
    
    @pytest.mark.asyncio
    async def test_delete_cluster_nodepool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test delete cluster nodepool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "task-delete123"
        mock_response.request_id = "req-delete123"
        mock_cs_client.delete_cluster_nodepool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        delete_tool = mock_server._registered_tools.get('delete_cluster_nodepool')
        assert delete_tool is not None
        
        # Test the function
        result = await delete_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            force=False,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "deleting"
    
    @pytest.mark.asyncio
    async def test_modify_cluster_node_pool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test modify cluster node pool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.request_id = "req-modify123"
        mock_cs_client.modify_cluster_node_pool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        modify_tool = mock_server._registered_tools.get('modify_cluster_node_pool')
        assert modify_tool is not None
        
        # Test the function
        result = await modify_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            nodepool_name="updated-nodepool",
            desired_size=5,
            max_size=10,
            min_size=2,
            enable_auto_scaling=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "modified"
    
    @pytest.mark.asyncio
    async def test_modify_nodepool_node_config(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test modify nodepool node config functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "task-config123"
        mock_response.request_id = "req-config123"
        mock_cs_client.modify_node_pool_node_config_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        config_tool = mock_server._registered_tools.get('modify_nodepool_node_config')
        assert config_tool is not None
        
        # Test the function
        result = await config_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            kubelet_config={"maxPods": 110},
            os_config={"sysctl": {"vm.max_map_count": "262144"}},
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["status"] == "configuring"
    
    @pytest.mark.asyncio
    async def test_upgrade_cluster_nodepool(self, mock_server, mock_context, mock_cs_client, test_config):
        """Test upgrade cluster nodepool functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.body = Mock()
        mock_response.body.task_id = "task-upgrade123"
        mock_response.request_id = "req-upgrade123"
        mock_cs_client.upgrade_cluster_nodepool_with_options_async.return_value = mock_response
        
        # Create handler and test
        handler_instance = handler.ACKNodePoolManagementHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        # Get the registered function
        upgrade_tool = mock_server._registered_tools.get('upgrade_cluster_nodepool')
        assert upgrade_tool is not None
        
        # Test the function
        result = await upgrade_tool(
            cluster_id="cluster-test123",
            nodepool_id="np-test123",
            kubernetes_version="1.28.3-aliyun.1",
            image_id="m-test123",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "nodepool_id" in result
        assert "kubernetes_version" in result
        assert "status" in result
        assert result["cluster_id"] == "cluster-test123"
        assert result["nodepool_id"] == "np-test123"
        assert result["kubernetes_version"] == "1.28.3-aliyun.1"
        assert result["status"] == "upgrading"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])