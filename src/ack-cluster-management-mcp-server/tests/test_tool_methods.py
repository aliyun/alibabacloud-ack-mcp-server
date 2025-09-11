#!/usr/bin/env python3
"""单元测试 - ACK Cluster Management MCP Server中每个tool方法的独立测试用例.

本测试文件为ACK集群管理MCP服务器中的每个handler tool方法创建独立的单元测试。
测试通过.env文件中的阿里云环境变量进行初始化，确保所有工具方法都能正确运行。

覆盖的工具方法：
1. describe_clusters - 集群列表查询
2. describe_cluster_detail - 集群详情查询
3. modify_cluster - 集群配置修改
4. describe_task_info - 任务信息查询
5. create_cluster - 集群创建
6. delete_cluster - 集群删除
7. upgrade_cluster - 集群升级
8. describe_cluster_logs - 集群日志查询
9. describe_user_quota - 用户配额查询
10. describe_kubernetes_version_metadata - Kubernetes版本元数据查询
"""

import pytest
import pytest_asyncio
import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

# 添加父目录到路径以导入模块
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    # 从项目根目录加载.env文件
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ 已加载环境配置文件: {env_path}")
    else:
        print(f"⚠️  环境配置文件不存在: {env_path}，将使用默认配置")
except ImportError:
    print("⚠️  python-dotenv未安装，无法加载.env文件")
    pass

from fastmcp import FastMCP, Context

# 直接导入当前目录的模块
current_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, current_dir)

from handler import ACKClusterManagementHandler
from runtime_provider import ACKClusterManagementRuntimeProvider
from server import create_mcp_server


@pytest.fixture
def env_config() -> Dict[str, Any]:
    """通过.env文件的环境变量创建配置.
    
    该fixture会从环境变量中读取阿里云认证信息和其他配置项。
    如果缺少关键配置，会输出警告信息。
    """
    config = {
        "allow_write": os.getenv("ALLOW_WRITE", "false").lower() == "true",
        "access_key_id": os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": os.getenv("ACCESS_KEY_SECRET", os.getenv("ACCESS_SECRET_KEY")),
        "region_id": os.getenv("REGION_ID", "cn-hangzhou"),
        "default_cluster_id": os.getenv("DEFAULT_CLUSTER_ID", ""),
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
        "development": os.getenv("DEVELOPMENT", "false").lower() == "true",
        "transport": os.getenv("TRANSPORT", "stdio"),
        "host": os.getenv("HOST", "localhost"),
        "port": int(os.getenv("PORT", "8000"))
    }
    
    # 检查关键配置项
    if not config["access_key_id"]:
        print("⚠️  ACCESS_KEY_ID 未设置，测试将使用模拟客户端")
    if not config["access_key_secret"]:
        print("⚠️  ACCESS_KEY_SECRET 未设置，测试将使用模拟客户端")
    
    print(f"ℹ️  使用配置: region_id={config['region_id']}, allow_write={config['allow_write']}, development={config['development']}")
    
    return config


@pytest.fixture
def mock_cs_client():
    """模拟阿里云CS客户端."""
    client = Mock()
    
    # 模拟describe_clusters_v1with_options_async方法
    async def mock_describe_clusters_v1with_options_async(request, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.clusters = [
            {
                "cluster_id": "test-cluster-123",
                "name": "test-cluster",
                "cluster_type": "ManagedKubernetes",
                "state": "running",
                "region_id": "cn-hangzhou"
            }
        ]
        response.body.page_info = {
            "total_count": 1,
            "page_number": 1,
            "page_size": 10
        }
        response.body.request_id = "test-request-123"
        return response
    
    # 模拟describe_cluster_detail_with_options_async方法
    async def mock_describe_cluster_detail_with_options_async(cluster_id, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.cluster_id = cluster_id
        response.body.name = "test-cluster"
        response.body.cluster_type = "ManagedKubernetes"
        response.body.cluster_spec = "ack.pro.small"
        response.body.profile = "Default"
        response.body.state = "running"
        response.body.size = 3
        response.body.region_id = "cn-hangzhou"
        response.body.zone_id = "cn-hangzhou-a"
        response.body.vpc_id = "vpc-test123"
        response.body.vswitch_ids = ["vsw-test123"]
        response.body.current_version = "1.28.3-aliyun.1"
        response.body.init_version = "1.28.3-aliyun.1"
        response.body.next_version = "1.28.4-aliyun.1"
        response.body.created = "2024-01-01T00:00:00Z"
        response.body.updated = "2024-01-01T00:00:00Z"
        response.body.deletion_protection = False
        response.body.resource_group_id = "rg-test123"
        response.body.security_group_id = "sg-test123"
        response.body.container_cidr = "172.20.0.0/16"
        response.body.service_cidr = "172.21.0.0/20"
        response.body.proxy_mode = "iptables"
        response.body.network_mode = "vpc"
        response.body.private_zone = False
        response.body.master_url = "https://test-cluster.cs.cn-hangzhou.aliyuncs.com:6443"
        response.body.tags = []
        response.body.maintenance_window = None
        response.body.operation_policy = None
        return response
    
    # 模拟modify_cluster_with_options_async方法
    async def mock_modify_cluster_with_options_async(cluster_id, request, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.request_id = "test-modify-request-123"
        return response
    
    # 模拟describe_task_info_with_options_async方法
    async def mock_describe_task_info_with_options_async(task_id, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.cluster_id = "test-cluster-123"
        response.body.task_type = "cluster_upgrade"
        response.body.state = "running"
        response.body.created = "2024-01-01T00:00:00Z"
        response.body.updated = "2024-01-01T00:00:00Z"
        response.body.current_stage = "upgrading_master"
        response.body.target = "1.28.4-aliyun.1"
        response.body.parameters = {}
        response.body.stages = []
        response.body.events = []
        response.body.task_result = None
        response.body.error = None
        return response
    
    # 模拟create_cluster_with_options_async方法
    async def mock_create_cluster_with_options_async(request, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.cluster_id = "new-cluster-123"
        response.body.request_id = "test-create-request-123"
        response.body.task_id = "test-create-task-123"
        return response
    
    # 模拟delete_cluster_with_options_async方法
    async def mock_delete_cluster_with_options_async(cluster_id, request, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.request_id = "test-delete-request-123"
        response.body.task_id = "test-delete-task-123"
        return response
    
    # 模拟upgrade_cluster_with_options_async方法
    async def mock_upgrade_cluster_with_options_async(cluster_id, request, headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.request_id = "test-upgrade-request-123"
        response.body.task_id = "test-upgrade-task-123"
        return response
    
    # 模拟describe_cluster_logs_with_options_async方法
    async def mock_describe_cluster_logs_with_options_async(cluster_id, headers, runtime):
        response = Mock()
        response.body = [
            {
                "log_id": "log-123",
                "cluster_id": cluster_id,
                "level": "info",
                "message": "Test log message",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        ]
        return response
    
    # 模拟describe_user_quota_with_options_async方法
    async def mock_describe_user_quota_with_options_async(headers, runtime):
        response = Mock()
        response.body = Mock()
        response.body.cluster_quota = 50
        response.body.node_quota = 1000
        response.body.cluster_nodepool_quota = 100
        response.body.amk_cluster_quota = 10
        response.body.ask_cluster_quota = 10
        response.body.quotas = {}
        response.body.edge_improved_nodepool_quota = 50
        return response
    
    # 模拟describe_kubernetes_version_metadata_with_options_async方法
    async def mock_describe_kubernetes_version_metadata_with_options_async(headers, runtime):
        response = Mock()
        response.body = [
            {
                "version": "1.28.3-aliyun.1",
                "platform": "AliyunLinux",
                "runtime": "containerd",
                "capabilities": ["basic"]
            }
        ]
        return response
    
    # 设置所有方法
    client.describe_clusters_v1with_options_async = mock_describe_clusters_v1with_options_async
    client.describe_cluster_detail_with_options_async = mock_describe_cluster_detail_with_options_async
    client.modify_cluster_with_options_async = mock_modify_cluster_with_options_async
    client.describe_task_info_with_options_async = mock_describe_task_info_with_options_async
    client.create_cluster_with_options_async = mock_create_cluster_with_options_async
    client.delete_cluster_with_options_async = mock_delete_cluster_with_options_async
    client.upgrade_cluster_with_options_async = mock_upgrade_cluster_with_options_async
    client.describe_cluster_logs_with_options_async = mock_describe_cluster_logs_with_options_async
    client.describe_user_quota_with_options_async = mock_describe_user_quota_with_options_async
    client.describe_kubernetes_version_metadata_with_options_async = mock_describe_kubernetes_version_metadata_with_options_async
    
    return client


@pytest.fixture
def mock_context(mock_cs_client):
    """模拟FastMCP上下文."""
    context = Mock(spec=Context)
    context.request_context = Mock()
    context.request_context.lifespan_context = Mock()
    
    def mock_get(key, default=None):
        if key == "providers":
            return {
                "cs_client": {
                    "client": mock_cs_client
                }
            }
        return default
    
    context.request_context.lifespan_context.get = mock_get
    return context


@pytest_asyncio.fixture
async def handler_with_server(env_config, mock_context):
    """创建带有模拟服务器的handler实例."""
    # 创建模拟服务器
    server = Mock(spec=FastMCP)
    tools = {}
    
    def mock_tool(name, description):
        def decorator(func):
            tools[name] = func
            return func
        return decorator
    
    server.tool = mock_tool
    
    # 创建handler
    handler = ACKClusterManagementHandler(
        server=server,
        allow_write=env_config.get("allow_write", False),
        settings=env_config
    )
    
    return handler, server, tools, mock_context


class TestACKClusterManagementTools:
    """ACK集群管理工具方法的单元测试."""
    
    @pytest.mark.asyncio
    async def test_describe_clusters(self, handler_with_server):
        """测试 describe_clusters 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        # 获取工具函数
        describe_clusters_func = tools["describe_clusters"]
        
        # 测试基本调用
        result = await describe_clusters_func(ctx=mock_context)
        
        assert "clusters" in result
        assert "page_info" in result
        assert "request_id" in result
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["cluster_id"] == "test-cluster-123"
        print("✅ describe_clusters 基本功能测试成功")
    
    @pytest.mark.asyncio
    async def test_describe_clusters_with_filters(self, handler_with_server):
        """测试带过滤条件的 describe_clusters."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_clusters_func = tools["describe_clusters"]
        
        # 测试带过滤条件的调用
        result = await describe_clusters_func(
            cluster_name="test-cluster",
            cluster_type="ManagedKubernetes",
            region_id="cn-hangzhou",
            page_size=20,
            ctx=mock_context
        )
        
        assert "clusters" in result
        assert "query_params" in result
        assert result["query_params"]["name"] == "test-cluster"
        assert result["query_params"]["cluster_type"] == "ManagedKubernetes"
        assert result["query_params"]["page_size"] == 20
        print("✅ describe_clusters 过滤条件测试成功")
    
    @pytest.mark.asyncio
    async def test_describe_cluster_detail(self, handler_with_server):
        """测试 describe_cluster_detail 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_cluster_detail_func = tools["describe_cluster_detail"]
        
        # 测试获取集群详情
        result = await describe_cluster_detail_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "cluster_info" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert result["cluster_info"]["name"] == "test-cluster"
        assert result["cluster_info"]["cluster_type"] == "ManagedKubernetes"
        assert result["cluster_info"]["state"] == "running"
        print("✅ describe_cluster_detail 测试成功")
    
    @pytest.mark.asyncio
    async def test_modify_cluster_write_disabled(self, handler_with_server):
        """测试写操作被禁用时的 modify_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        # 设置写操作禁用
        handler.allow_write = False
        
        modify_cluster_func = tools["modify_cluster"]
        
        result = await modify_cluster_func(
            cluster_id="test-cluster-123",
            cluster_name="new-name",
            ctx=mock_context
        )
        
        assert "error" in result
        assert result["error"] == "Write operations are disabled"
        print("✅ modify_cluster 写操作禁用测试成功")
    
    @pytest.mark.asyncio
    async def test_modify_cluster_write_enabled(self, env_config, handler_with_server):
        """测试写操作启用时的 modify_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        # 启用写操作
        handler.allow_write = True
        
        modify_cluster_func = tools["modify_cluster"]
        
        result = await modify_cluster_func(
            cluster_id="test-cluster-123",
            cluster_name="new-cluster-name",
            deletion_protection=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "request_id" in result
        assert "status" in result
        assert result["status"] == "modified"
        assert result["cluster_id"] == "test-cluster-123"
    
    @pytest.mark.asyncio
    async def test_describe_task_info(self, handler_with_server):
        """测试 describe_task_info 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_task_info_func = tools["describe_task_info"]
        
        result = await describe_task_info_func(
            task_id="test-task-123",
            ctx=mock_context
        )
        
        assert "task_id" in result
        assert "cluster_id" in result
        assert "task_type" in result
        assert "state" in result
        assert result["task_id"] == "test-task-123"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["task_type"] == "cluster_upgrade"
        assert result["state"] == "running"
    
    @pytest.mark.asyncio
    async def test_create_cluster_write_disabled(self, handler_with_server):
        """测试写操作被禁用时的 create_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = False
        
        create_cluster_func = tools["create_cluster"]
        
        result = await create_cluster_func(
            name="new-cluster",
            region_id="cn-hangzhou",
            cluster_type="ManagedKubernetes",
            ctx=mock_context
        )
        
        assert "error" in result
        assert result["error"] == "Write operations are disabled"
    
    @pytest.mark.asyncio
    async def test_create_cluster_write_enabled(self, handler_with_server):
        """测试写操作启用时的 create_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = True
        
        create_cluster_func = tools["create_cluster"]
        
        result = await create_cluster_func(
            name="new-cluster",
            region_id="cn-hangzhou",
            cluster_type="ManagedKubernetes",
            kubernetes_version="1.28.3-aliyun.1",
            cluster_spec="ack.pro.small",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "request_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "created"
        assert result["name"] == "new-cluster"
        assert result["region_id"] == "cn-hangzhou"
    
    @pytest.mark.asyncio
    async def test_delete_cluster_write_disabled(self, handler_with_server):
        """测试写操作被禁用时的 delete_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = False
        
        delete_cluster_func = tools["delete_cluster"]
        
        result = await delete_cluster_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert "error" in result
        assert result["error"] == "Write operations are disabled"
    
    @pytest.mark.asyncio
    async def test_delete_cluster_write_enabled(self, handler_with_server):
        """测试写操作启用时的 delete_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = True
        
        delete_cluster_func = tools["delete_cluster"]
        
        result = await delete_cluster_func(
            cluster_id="test-cluster-123",
            retain_all_resources=False,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "request_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "deleting"
        assert result["cluster_id"] == "test-cluster-123"
    
    @pytest.mark.asyncio
    async def test_upgrade_cluster_write_disabled(self, handler_with_server):
        """测试写操作被禁用时的 upgrade_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = False
        
        upgrade_cluster_func = tools["upgrade_cluster"]
        
        result = await upgrade_cluster_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert "error" in result
        assert result["error"] == "Write operations are disabled"
    
    @pytest.mark.asyncio
    async def test_upgrade_cluster_write_enabled(self, handler_with_server):
        """测试写操作启用时的 upgrade_cluster."""
        handler, server, tools, mock_context = handler_with_server
        
        handler.allow_write = True
        
        upgrade_cluster_func = tools["upgrade_cluster"]
        
        result = await upgrade_cluster_func(
            cluster_id="test-cluster-123",
            next_version="1.28.4-aliyun.1",
            master_only=True,
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "request_id" in result
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "upgrading"
        assert result["cluster_id"] == "test-cluster-123"
        assert result["next_version"] == "1.28.4-aliyun.1"
        assert result["master_only"] == True
    
    @pytest.mark.asyncio
    async def test_describe_cluster_logs(self, handler_with_server):
        """测试 describe_cluster_logs 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_cluster_logs_func = tools["describe_cluster_logs"]
        
        result = await describe_cluster_logs_func(
            cluster_id="test-cluster-123",
            ctx=mock_context
        )
        
        assert "cluster_id" in result
        assert "logs" in result
        assert "count" in result
        assert result["cluster_id"] == "test-cluster-123"
        assert len(result["logs"]) == 1
        assert result["count"] == 1
    
    @pytest.mark.asyncio
    async def test_describe_user_quota(self, handler_with_server):
        """测试 describe_user_quota 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_user_quota_func = tools["describe_user_quota"]
        
        result = await describe_user_quota_func(ctx=mock_context)
        
        assert "cluster_quota" in result
        assert "node_quota" in result
        assert "cluster_nodepool_quota" in result
        assert "amk_cluster_quota" in result
        assert "ask_cluster_quota" in result
        assert result["cluster_quota"] == 50
        assert result["node_quota"] == 1000
    
    @pytest.mark.asyncio
    async def test_describe_kubernetes_version_metadata(self, handler_with_server):
        """测试 describe_kubernetes_version_metadata 工具方法."""
        handler, server, tools, mock_context = handler_with_server
        
        describe_kubernetes_version_metadata_func = tools["describe_kubernetes_version_metadata"]
        
        # 测试不带过滤条件
        result = await describe_kubernetes_version_metadata_func(ctx=mock_context)
        
        assert "versions" in result
        assert "query_params" in result
        assert len(result["versions"]) == 1
        assert result["versions"][0]["version"] == "1.28.3-aliyun.1"
        
        # 测试带过滤条件
        result = await describe_kubernetes_version_metadata_func(
            region="cn-hangzhou",
            cluster_type="ManagedKubernetes",
            ctx=mock_context
        )
        
        assert "versions" in result
        assert "query_params" in result
        assert result["query_params"]["Region"] == "cn-hangzhou"
        assert result["query_params"]["ClusterType"] == "ManagedKubernetes"


class TestACKClusterManagementError:
    """ACK集群管理错误处理测试."""
    
    @pytest.mark.asyncio
    async def test_no_client_in_context(self, handler_with_server):
        """测试上下文中没有客户端的错误处理."""
        handler, server, tools, _ = handler_with_server
        
        # 创建没有客户端的mock context
        no_client_context = Mock(spec=Context)
        no_client_context.request_context = Mock()
        no_client_context.request_context.lifespan_context = Mock()
        no_client_context.request_context.lifespan_context.get = Mock(return_value={
            "providers": {}
        })
        
        describe_clusters_func = tools["describe_clusters"]
        
        result = await describe_clusters_func(ctx=no_client_context)
        
        assert "error" in result
        assert "CS client not available" in result["error"]
    
    @pytest.mark.asyncio
    async def test_context_access_failure(self, handler_with_server):
        """测试上下文访问失败的错误处理."""
        handler, server, tools, _ = handler_with_server
        
        # 创建会抛出异常的mock context
        failing_context = Mock(spec=Context)
        failing_context.request_context = Mock()
        failing_context.request_context.lifespan_context = Mock()
        failing_context.request_context.lifespan_context.get = Mock(
            side_effect=Exception("Context access failed")
        )
        
        describe_clusters_func = tools["describe_clusters"]
        
        result = await describe_clusters_func(ctx=failing_context)
        
        assert "error" in result
        assert "Failed to access lifespan context" in result["error"]


class TestIntegrationWithEnvironment:
    """与环境变量集成的测试."""
    
    def test_env_config_loading(self, env_config):
        """测试环境变量配置加载."""
        assert env_config is not None
        assert isinstance(env_config, dict)
        
        # 检查基本配置项
        assert "region_id" in env_config
        assert "allow_write" in env_config
        
        # 检查区域配置
        assert env_config["region_id"] in ["cn-hangzhou", "cn-beijing", "cn-shanghai", "us-west-1", "ap-southeast-1"]
    
    def test_credentials_configuration(self, env_config):
        """测试凭据配置."""
        # 如果设置了环境变量，验证凭据存在
        if os.getenv("ACCESS_KEY_ID"):
            assert env_config["access_key_id"] is not None
            assert len(env_config["access_key_id"]) > 0
        
        if os.getenv("ACCESS_KEY_SECRET") or os.getenv("ACCESS_SECRET_KEY"):
            assert env_config["access_key_secret"] is not None
            assert len(env_config["access_key_secret"]) > 0
    
    @pytest.mark.asyncio
    async def test_server_creation_with_env_config(self, env_config):
        """测试使用环境配置创建服务器."""
        try:
            server = create_mcp_server(env_config)
            assert server is not None
            assert hasattr(server, 'name')
        except Exception as e:
            # 如果缺少必要的环境变量，这是可以接受的
            assert "ACCESS_KEY" in str(e) or "region" in str(e)


if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v", "--tb=short"])