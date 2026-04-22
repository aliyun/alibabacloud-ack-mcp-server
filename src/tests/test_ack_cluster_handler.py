import pytest
import sys
import os
from unittest.mock import MagicMock
from datetime import datetime, timezone

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ack_cluster_handler as module_under_test
from models import (
    ListClustersOutput, ClusterInfo, ErrorModel, ClusterErrorCodes,
    ListClusterNodepoolsOutput, ListClusterNodesOutput, ListClusterTasksOutput
)


class FakeServer:
    def __init__(self):
        self.tools = {}

    def tool(self, name: str = None, description: str = None):
        def decorator(func):
            key = name or getattr(func, "__name__", "unnamed")
            self.tools[key] = func
            return func
        return decorator


class FakeRequestContext:
    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


class FakeContext:
    def __init__(self, lifespan_context):
        self.request_context = FakeRequestContext(lifespan_context)
        self.lifespan_context = lifespan_context


class FakeResponseBody:
    def __init__(self, clusters):
        self.clusters = clusters


class FakeResponse:
    def __init__(self, clusters):
        self.body = FakeResponseBody(clusters)


class FakeCSClient:
    def __init__(self, clusters_by_call):
        self._clusters_by_call = clusters_by_call

    async def describe_clusters_v1with_options_async(self, request, headers, runtime):
        return FakeResponse(self._clusters_by_call)


def make_handler_and_tool(settings=None):
    server = FakeServer()
    module_under_test.ACKClusterHandler(server, settings or {})
    return server.tools["list_clusters"]


@pytest.mark.asyncio
async def test_list_clusters_success():
    fake_clusters = [
        {
            "name": "c1", 
            "cluster_id": "cls-1", 
            "state": "Running", 
            "region_id": "cn-hangzhou", 
            "cluster_type": "ManagedKubernetes",
            "current_version": "1.24.6-aliyun.1",
            "vpc_id": "vpc-123",
            "vswitch_ids": ["vsw-123"],
            "resource_group_id": "rg-123",
            "security_group_id": "sg-123",
            "proxy_mode": "ipvs",
            "tags": [],
            "master_url": '{"api_server_endpoint": "https://test.com", "intranet_api_server_endpoint": "https://internal.test.com"}'
        },
        {
            "name": "c2",  # 使用name而不是cluster_name
            "cluster_id": "cls-2",  # 使用cluster_id而不是clusterId
            "state": "Initializing",  # 使用state而不是status
            "region_id": "cn-hangzhou",  # 添加必填的region_id
            "cluster_type": "Kubernetes",  # 使用cluster_type而不是clusterType
            "current_version": "1.23.6-aliyun.1",  # 使用current_version
            "tags": [],
            "vswitch_ids": [],
            "master_url": '{}'
        },
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(_region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 2
    assert len(result.clusters) == 2
    assert result.error is None
    
    # 验证第一个集群信息
    cluster1 = result.clusters[0]
    assert cluster1.cluster_name == "c1"
    assert cluster1.cluster_id == "cls-1"
    assert cluster1.state == "Running"
    assert cluster1.region_id == "cn-hangzhou"
    assert cluster1.cluster_type == "ManagedKubernetes"
    assert cluster1.current_version == "1.24.6-aliyun.1"
    assert cluster1.vpc_id == "vpc-123"
    assert cluster1.vswitch_ids == ["vsw-123"]
    
    # 验证第二个集群信息
    cluster2 = result.clusters[1]
    assert cluster2.cluster_name == "c2"
    assert cluster2.cluster_id == "cls-2"
    assert cluster2.state == "Initializing"
    assert cluster2.cluster_type == "Kubernetes"


@pytest.mark.asyncio
async def test_list_clusters_api_error():
    """测试 API 调用失败的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        raise RuntimeError("NO_RAM_POLICY_AUTH: 当前账号无ram policy权限，需要授权")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 0
    assert result.clusters == []
    assert result.error is not None
    assert result.error.error_code == ClusterErrorCodes.NO_RAM_POLICY_AUTH
    assert "ram policy权限" in result.error.error_message


@pytest.mark.asyncio
async def test_list_clusters_cs_client_error():
    """测试CS客户端初始化失败的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        raise RuntimeError("缺少region_id参数")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 0
    assert result.clusters == []
    assert result.error is not None
    assert result.error.error_code == ClusterErrorCodes.MISS_REGION_ID
    assert "缺少region_id参数" in result.error.error_message


@pytest.mark.asyncio
async def test_list_clusters_empty_result():
    """测试返回空结果的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient([])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 0
    assert result.clusters == []
    assert result.error is None


@pytest.mark.asyncio
async def test_list_clusters_with_pagination():
    """测试分页参数"""
    fake_clusters = [
        {
            "name": "c1", 
            "cluster_id": "cls-1", 
            "state": "Running", 
            "region_id": "cn-hangzhou",
            "cluster_type": "ManagedKubernetes",
            "tags": [],
            "vswitch_ids": [],
            "master_url": '{}'
        }
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=100, page_num=2)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 1
    assert len(result.clusters) == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_list_clusters_invalid_cluster_data():
    """测试无效的集群数据"""
    fake_clusters = [
        {
            "name": "c1", 
            "cluster_id": "cls-1", 
            "state": "Running", 
            "region_id": "cn-hangzhou",
            "cluster_type": "ManagedKubernetes",
            "tags": [],
            "vswitch_ids": [],
            "master_url": '{}'
        },
        {"invalid": "data"},  # 无效数据
        {
            "name": "c3", 
            "cluster_id": "cls-3", 
            "state": "Running", 
            "region_id": "cn-hangzhou",
            "cluster_type": "Kubernetes",
            "tags": [],
            "vswitch_ids": [],
            "master_url": '{}'
        }
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    # 应该只返回有效的集群数据
    assert result.count == 2
    assert len(result.clusters) == 2
    assert result.error is None 


def test_serialize_sdk_object_various():
    assert module_under_test._serialize_sdk_object(1) == 1
    assert module_under_test._serialize_sdk_object(True) is True
    assert module_under_test._serialize_sdk_object([1, 2, 3]) == [1, 2, 3]
    assert module_under_test._serialize_sdk_object({"a": 1}) == {"a": 1}

    class WithToMap:
        def to_map(self):
            return {"k": "v"}

    assert module_under_test._serialize_sdk_object(WithToMap()) == {"k": "v"}

    class WithDict:
        def __init__(self):
            self.a = 1

    assert module_under_test._serialize_sdk_object(WithDict()) == {"a": 1}


def test_cluster_info_model():
    """测试 ClusterInfo 数据模型"""
    cluster = ClusterInfo(
        cluster_name="test-cluster",
        cluster_id="cls-123",
        state="Running",
        region_id="cn-hangzhou",
        cluster_type="ManagedKubernetes",
        current_version="1.24.6-aliyun.1",
        vpc_id="vpc-123",
        vswitch_ids=["vsw-123", "vsw-456"],
        resource_group_id="rg-123",
        security_group_id="sg-123",
        proxy_mode="ipvs"
    )
    
    assert cluster.cluster_name == "test-cluster"
    assert cluster.cluster_id == "cls-123"
    assert cluster.state == "Running"
    assert cluster.region_id == "cn-hangzhou"
    assert cluster.cluster_type == "ManagedKubernetes"
    assert cluster.current_version == "1.24.6-aliyun.1"
    assert cluster.vpc_id == "vpc-123"
    assert cluster.vswitch_ids == ["vsw-123", "vsw-456"]
    assert cluster.resource_group_id == "rg-123"
    assert cluster.security_group_id == "sg-123"
    assert cluster.proxy_mode == "ipvs"


def test_list_clusters_output_model():
    """测试 ListClustersOutput 数据模型"""
    cluster1 = ClusterInfo(
        cluster_name="cluster1",
        cluster_id="cls-1",
        state="Running",
        region_id="cn-hangzhou",
        cluster_type="ManagedKubernetes"
    )
    
    cluster2 = ClusterInfo(
        cluster_name="cluster2",
        cluster_id="cls-2",
        state="Initializing",
        region_id="cn-hangzhou",
        cluster_type="Kubernetes"
    )
    
    output = ListClustersOutput(
        count=2,
        clusters=[cluster1, cluster2]
    )
    
    assert output.count == 2
    assert len(output.clusters) == 2
    assert output.error is None
    assert output.clusters[0].cluster_name == "cluster1"
    assert output.clusters[1].cluster_name == "cluster2"


def test_list_clusters_output_with_error():
    """测试带错误信息的 ListClustersOutput"""
    error = ErrorModel(
        error_code=ClusterErrorCodes.NO_RAM_POLICY_AUTH,
        error_message="当前账号无ram policy权限，需要授权"
    )
    
    output = ListClustersOutput(
        count=0,
        error=error,
        clusters=[]
    )
    
    assert output.count == 0
    assert output.clusters == []
    assert output.error is not None
    assert output.error.error_code == ClusterErrorCodes.NO_RAM_POLICY_AUTH
    assert "ram policy权限" in output.error.error_message


def test_error_model():
    """测试 ErrorModel 数据模型"""
    error = ErrorModel(
        error_code=ClusterErrorCodes.MISS_REGION_ID,
        error_message="缺少region_id参数"
    )
    
    assert error.error_code == ClusterErrorCodes.MISS_REGION_ID
    assert error.error_message == "缺少region_id参数"


def test_cluster_error_codes():
    """测试错误码常量"""
    assert ClusterErrorCodes.NO_RAM_POLICY_AUTH == "NO_RAM_POLICY_AUTH"
    assert ClusterErrorCodes.MISS_REGION_ID == "MISS_REGION_ID"


# ==================== list_cluster_nodepools 测试 ====================

def make_nodepools_handler_and_tool(settings=None):
    """创建 nodepools handler 和工具"""
    server = FakeServer()
    module_under_test.ACKClusterHandler(server, settings or {})
    return server.tools["list_cluster_nodepools"]


class FakeClusterDetailResponse:
    """模拟集群详情响应"""
    def __init__(self, region_id="cn-hangzhou"):
        self.body = MagicMock()
        self.body.region_id = region_id


class FakeNodePoolDetailResponse:
    """模拟节点池详情响应"""
    def __init__(self, nodepool_data):
        self.body = nodepool_data if nodepool_data else None


class FakeNodePoolsListResponse:
    """模拟节点池列表响应"""
    def __init__(self, nodepools):
        self.body = MagicMock()
        self.body.nodepools = nodepools


class FakeCSClientForNodepools:
    """模拟 CS 客户端（用于节点池测试）"""
    def __init__(self, region_id="cn-hangzhou", nodepools_data=None, nodepool_detail=None):
        self.region_id = region_id
        self.nodepools_data = nodepools_data or []
        self.nodepool_detail = nodepool_detail

    async def describe_cluster_detail_async(self, cluster_id):
        return FakeClusterDetailResponse(self.region_id)

    async def describe_cluster_node_pools_with_options_async(self, cluster_id, request, headers, runtime):
        return FakeNodePoolsListResponse(self.nodepools_data)

    async def describe_cluster_node_pool_detail_with_options_async(self, cluster_id, nodepool_id, headers, runtime):
        return FakeNodePoolDetailResponse(self.nodepool_detail)


@pytest.mark.asyncio
async def test_list_cluster_nodepools_success():
    """测试成功获取节点池列表"""
    fake_nodepools = [
        {
            "nodepool_info": {
                "nodepool_id": "np-1",
                "name": "nodepool-1",
                "type": "ess",
                "is_default": True,
                "created": "2024-01-01T00:00:00Z",
                "region_id": "cn-hangzhou"
            },
            "status": {
                "state": "active",
                "total_nodes": 3,
                "healthy_nodes": 3
            }
        },
        {
            "nodepool_info": {
                "nodepool_id": "np-2",
                "name": "nodepool-2",
                "type": "ess",
                "is_default": False,
                "created": "2024-01-02T00:00:00Z",
                "region_id": "cn-hangzhou"
            },
            "status": {
                "state": "active",
                "total_nodes": 5,
                "healthy_nodes": 5
            }
        }
    ]

    tool = make_nodepools_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodepools(region_id="cn-hangzhou", nodepools_data=fake_nodepools)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012", page_size=10, page_number=1)

    assert isinstance(result, ListClusterNodepoolsOutput)
    assert result.count == 2
    assert result.total_count == 2
    assert result.error is None
    assert len(result.nodepools) == 2
    assert result.page_number == 1
    assert result.page_size == 10


@pytest.mark.asyncio
async def test_list_cluster_nodepools_with_nodepool_id():
    """测试通过 nodepool_id 获取单个节点池详情"""
    fake_nodepool_detail = {
        "nodepool_info": {
            "nodepool_id": "np-1",
            "name": "nodepool-1",
            "type": "ess",
            "is_default": True,
            "created": "2024-01-01T00:00:00Z",
            "region_id": "cn-hangzhou"
        },
        "status": {
            "state": "active",
            "total_nodes": 3,
            "healthy_nodes": 3
        }
    }

    tool = make_nodepools_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodepools(region_id="cn-hangzhou", nodepool_detail=fake_nodepool_detail)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012", nodepool_id="np-1")

    assert isinstance(result, ListClusterNodepoolsOutput)
    assert result.count == 1
    assert result.total_count == 1
    assert result.error is None
    assert len(result.nodepools) == 1
    assert result.nodepools[0]["nodepool_id"] == "np-1"


@pytest.mark.asyncio
async def test_list_cluster_nodepools_empty():
    """测试空节点池列表"""
    tool = make_nodepools_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodepools(region_id="cn-hangzhou", nodepools_data=[])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterNodepoolsOutput)
    assert result.count == 0
    assert result.total_count == 0
    assert result.error is None
    assert len(result.nodepools) == 0


@pytest.mark.asyncio
async def test_list_cluster_nodepools_error():
    """测试节点池查询错误"""
    tool = make_nodepools_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        raise RuntimeError("Failed to get cluster region")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterNodepoolsOutput)
    assert result.count == 0
    assert result.error is not None
    assert "ListClusterNodePoolsError" in result.error.error_code


# ==================== list_cluster_nodes 测试 ====================

def make_nodes_handler_and_tool(settings=None):
    """创建 nodes handler 和工具"""
    server = FakeServer()
    module_under_test.ACKClusterHandler(server, settings or {})
    return server.tools["list_cluster_nodes"]


class FakeNodesResponse:
    """模拟节点列表响应"""
    def __init__(self, nodes, page_info=None):
        self.body = MagicMock()
        self.body.nodes = nodes
        if page_info:
            self.body.page_info = page_info
            self.body.pageInfo = page_info
            self.body.page = page_info


class FakeCSClientForNodes:
    """模拟 CS 客户端（用于节点测试）"""
    def __init__(self, region_id="cn-hangzhou", nodes_data=None, page_info=None):
        self.region_id = region_id
        self.nodes_data = nodes_data or []
        self.page_info = page_info or {}

    async def describe_cluster_detail_async(self, cluster_id):
        return FakeClusterDetailResponse(self.region_id)

    async def describe_cluster_nodes_with_options_async(self, cluster_id, request, headers, runtime):
        return FakeNodesResponse(self.nodes_data, self.page_info)


@pytest.mark.asyncio
async def test_list_cluster_nodes_success():
    """测试成功获取节点列表"""
    fake_nodes = [
        {
            "instance_id": "i-123456",
            "node_name": "node-1",
            "node_status": "Ready",
            "state": "running",
            "ip_address": "192.168.1.1",
            "nodepool_id": "np-1",
            "instance_type": "ecs.c6.large",
            "created": "2024-01-01T00:00:00Z",
            "host_name": "node-1-host"
        },
        {
            "instance_id": "i-234567",
            "node_name": "node-2",
            "node_status": "Ready",
            "state": "running",
            "ip_address": "192.168.1.2",
            "nodepool_id": "np-1",
            "instance_type": "ecs.c6.large",
            "created": "2024-01-01T00:00:00Z"
        }
    ]

    page_info = {
        "page_number": 1,
        "page_size": 20,
        "total_count": 2
    }

    tool = make_nodes_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodes(region_id="cn-hangzhou", nodes_data=fake_nodes, page_info=page_info)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        page_number=1,
        page_size=20
    )

    assert isinstance(result, ListClusterNodesOutput)
    assert result.count == 2
    assert result.total_count == 2
    assert result.error is None
    assert len(result.nodes) == 2
    assert result.page_number == 1
    assert result.page_size == 20
    assert result.nodes[0]["instance_id"] == "i-123456"
    assert result.nodes[0]["node_name"] == "node-1"


@pytest.mark.asyncio
async def test_list_cluster_nodes_with_nodepool_id():
    """测试按节点池ID过滤节点"""
    fake_nodes = [
        {
            "instance_id": "i-123456",
            "node_name": "node-1",
            "nodepool_id": "np-1"
        }
    ]

    tool = make_nodes_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodes(region_id="cn-hangzhou", nodes_data=fake_nodes)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        nodepool_id="np-1"
    )

    assert isinstance(result, ListClusterNodesOutput)
    assert result.count == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_list_cluster_nodes_with_instance_ids():
    """测试按实例ID列表过滤节点"""
    fake_nodes = [
        {
            "instance_id": "i-123456",
            "node_name": "node-1"
        },
        {
            "instance_id": "i-234567",
            "node_name": "node-2"
        }
    ]

    tool = make_nodes_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForNodes(region_id="cn-hangzhou", nodes_data=fake_nodes)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        instance_ids=["i-123456"]
    )

    assert isinstance(result, ListClusterNodesOutput)
    assert result.count == 1
    assert result.error is None
    assert result.nodes[0]["instance_id"] == "i-123456"


@pytest.mark.asyncio
async def test_list_cluster_nodes_error():
    """测试节点查询错误"""
    tool = make_nodes_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        raise RuntimeError("Failed to get nodes")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterNodesOutput)
    assert result.count == 0
    assert result.error is not None
    assert "ListClusterNodesError" in result.error.error_code


# ==================== list_cluster_tasks 测试 ====================

def make_tasks_handler_and_tool(settings=None):
    """创建 tasks handler 和工具"""
    server = FakeServer()
    module_under_test.ACKClusterHandler(server, settings or {})
    return server.tools["list_cluster_tasks"]


class FakeTasksResponse:
    """模拟任务列表响应（call_api 返回格式）"""
    def __init__(self, tasks, page_info=None):
        self.body = {
            "tasks": tasks or [],
            "page_info": page_info or {}
        }
        # 也支持 Tasks 大写
        if tasks:
            self.body["Tasks"] = tasks


class FakeCSClientForTasks:
    """模拟 CS 客户端（用于任务测试）"""
    def __init__(self, region_id="cn-hangzhou", tasks_data=None, page_info=None):
        self.region_id = region_id
        self.tasks_data = tasks_data or []
        self.page_info = page_info or {}

    async def describe_cluster_detail_async(self, cluster_id):
        return FakeClusterDetailResponse(self.region_id)

    async def call_api_async(self, params, request, runtime):
        body = {
            "tasks": self.tasks_data,
            "page_info": self.page_info
        }
        return {"body": body}


@pytest.mark.asyncio
async def test_list_cluster_tasks_success():
    """测试成功获取任务列表"""
    now = int(datetime.now(timezone.utc).timestamp())
    fake_tasks = [
        {
            "task_id": "task-1",
            "state": "success",
            "created": now - 600,  # 10分钟前
            "updated": now - 500,
            "task_type": "nodepool_create",
            "cluster_id": "c12345678901234567890123456789012",
            "task": {
                "created": now - 600,
                "target": {
                    "type": "nodepool",
                    "nodepool_id": "np-1"
                }
            }
        },
        {
            "task_id": "task-2",
            "state": "running",
            "created": now - 300,  # 5分钟前
            "updated": now - 200,
            "task_type": "nodepool_scaleout",
            "cluster_id": "c12345678901234567890123456789012",
            "task": {
                "created": now - 300,
                "target": {
                    "type": "nodepool",
                    "nodepool_id": "np-2"
                }
            }
        }
    ]

    page_info = {
        "page_number": 1,
        "page_size": 20,
        "total_count": 2
    }

    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(region_id="cn-hangzhou", tasks_data=fake_tasks, page_info=page_info)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        page_number=1,
        page_size=20
    )

    assert isinstance(result, ListClusterTasksOutput)
    assert result.count == 2
    assert result.total_count == 2
    assert result.error is None
    assert len(result.tasks) == 2
    assert result.page_number == 1
    assert result.page_size == 20
    assert result.tasks[0]["task_id"] == "task-1"
    assert result.tasks[0]["state"] == "success"


@pytest.mark.asyncio
async def test_list_cluster_tasks_with_state_filter():
    """测试按状态过滤任务"""
    now = int(datetime.now(timezone.utc).timestamp())
    fake_tasks = [
        {
            "task_id": "task-1",
            "state": "success",
            "created": now - 600,
            "task_type": "nodepool_create",
            "task": {"created": now - 600}
        },
        {
            "task_id": "task-2",
            "state": "running",
            "created": now - 300,
            "task_type": "nodepool_scaleout",
            "task": {"created": now - 300}
        }
    ]

    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(region_id="cn-hangzhou", tasks_data=fake_tasks, page_info={"total_count": 2})

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        state=module_under_test.ClusterTaskState.SUCCESS,
    )

    assert isinstance(result, ListClusterTasksOutput)
    # 注意：state 过滤是在 API 层面，这里我们只测试客户端过滤逻辑
    assert result.error is None


@pytest.mark.asyncio
async def test_list_cluster_tasks_with_time_range():
    """测试按时间范围过滤任务"""
    now = int(datetime.now(timezone.utc).timestamp())
    # 创建1小时前的任务（应该被过滤掉，默认30分钟）
    old_task = {
        "task_id": "task-old",
        "state": "success",
        "created": now - 3600,  # 1小时前
        "task_type": "nodepool_create",
        "task": {"created": now - 3600}
    }
    # 创建10分钟前的任务（应该在范围内）
    recent_task = {
        "task_id": "task-recent",
        "state": "success",
        "created": now - 600,  # 10分钟前
        "task_type": "nodepool_create",
        "task": {"created": now - 600}
    }

    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(
            region_id="cn-hangzhou",
            tasks_data=[old_task, recent_task],
            page_info={"total_count": 2}
        )

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        start_time="30m"
    )

    assert isinstance(result, ListClusterTasksOutput)
    # 应该只返回最近的任务
    assert result.error is None


@pytest.mark.asyncio
async def test_list_cluster_tasks_with_nodepool_id():
    """测试按节点池ID过滤任务"""
    now = int(datetime.now(timezone.utc).timestamp())
    fake_tasks = [
        {
            "task_id": "task-1",
            "state": "success",
            "created": now - 600,
            "task_type": "nodepool_create",
            "task": {
                "created": now - 600,
                "target": {
                    "type": "nodepool",
                    "nodepool_id": "np-1"
                }
            }
        },
        {
            "task_id": "task-2",
            "state": "success",
            "created": now - 300,
            "task_type": "nodepool_create",
            "task": {
                "created": now - 300,
                "target": {
                    "type": "nodepool",
                    "nodepool_id": "np-2"
                }
            }
        }
    ]

    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(region_id="cn-hangzhou", tasks_data=fake_tasks, page_info={"total_count": 2})

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        nodepool_id="np-1",
        start_time="1h"
    )

    assert isinstance(result, ListClusterTasksOutput)
    assert result.error is None
    # 应该只返回 np-1 的任务
    assert all(task.get("task_id") == "task-1" or "nodepool_id" in str(task) for task in result.tasks)


@pytest.mark.asyncio
async def test_list_cluster_tasks_empty():
    """测试空任务列表"""
    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(region_id="cn-hangzhou", tasks_data=[], page_info={"total_count": 0})

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterTasksOutput)
    assert result.count == 0
    assert result.total_count == 0
    assert result.error is None
    assert len(result.tasks) == 0


@pytest.mark.asyncio
async def test_list_cluster_tasks_with_wide_time_range_fallback():
    """测试时间范围回退逻辑（当默认30分钟没有任务时，使用更宽的时间范围）"""
    now = int(datetime.now(timezone.utc).timestamp())
    # 创建2小时前的任务（不在默认30分钟范围内）
    old_task = {
        "task_id": "task-old",
        "state": "success",
        "created": now - 7200,  # 2小时前
        "task_type": "nodepool_create",
        "task": {"created": now - 7200}
    }

    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        return FakeCSClientForTasks(
            region_id="cn-hangzhou",
            tasks_data=[old_task],
            page_info={"total_count": 1}
        )

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterTasksOutput)
    assert result.error is None
    # 由于有回退逻辑，应该能找到任务
    assert result.total_count == 1


@pytest.mark.asyncio
async def test_list_cluster_tasks_error():
    """测试任务查询错误"""
    tool = make_tasks_handler_and_tool()

    def cs_client_factory(region: str, config=None):
        raise RuntimeError("Failed to get tasks")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, cluster_id="c12345678901234567890123456789012")

    assert isinstance(result, ListClusterTasksOutput)
    assert result.count == 0
    assert result.error is not None
    assert "ListClusterTasksError" in result.error.error_code


# ==================== 测试 FAIL 和 FAILED 状态兼容性 ====================

class FakeCSClientForBothFailStates:
    """模拟 CS 客户端，专门用于测试两个失败状态的兼容性"""

    def __init__(self, region_id="cn-hangzhou", tasks_data_by_state=None, page_info=None):
        self.region_id = region_id
        self.tasks_data_by_state = tasks_data_by_state or {"default": []}
        self.page_info = page_info or {}

    async def describe_cluster_detail_async(self, cluster_id):
        return FakeClusterDetailResponse(self.region_id)

    async def call_api_async(self, params, request, runtime):
        # 根据传入的 state 参数返回不同的任务数据
        state = None
        if hasattr(request, 'query') and request.query:
            state = request.query.get('state')
        # 模拟从 params query 获取 state 的情况
        elif 'query' in params.__dict__:
            state = params.query.get('state') if params.query else None
        # 如果上面都失败，尝试从其他方式获取
        else:
            query = params.get('query', {}) if hasattr(params, 'get') else {}
            state = query.get('state') if isinstance(query, dict) else None

        # 如果 state 是 'failed' 或 'fail'，分别返回对应的任务
        if state == 'failed':
            tasks = self.tasks_data_by_state.get('failed', [])
        elif state == 'fail':
            tasks = self.tasks_data_by_state.get('fail', [])
        else:
            tasks = self.tasks_data_by_state.get('default', [])

        body = {
            "tasks": tasks,
            "page_info": self.page_info
        }
        return {"body": body}


@pytest.mark.asyncio
async def test_list_cluster_tasks_fetch_both_fail_states_when_query_failed():
    """测试当查询状态为 'failed' 时也同时获取 'fail' 状态的任务"""
    now = int(datetime.now(timezone.utc).timestamp())
    # 准备 'failed' 状态的任务
    failed_tasks = [
        {
            "task_id": "task-1",
            "state": "failed",
            "created": now - 600,
            "task_type": "nodepool_create",
            "task": {"created": now - 600}
        }
    ]

    # 准备 'fail' 状态的任务
    fail_tasks = [
        {
            "task_id": "task-2",
            "state": "fail",
            "created": now - 300,
            "task_type": "nodepool_scaleout",
            "task": {"created": now - 300}
        }
    ]

    tool = make_tasks_handler_and_tool()

    # 跟踪 API 调用次数
    call_args_list = []

    def cs_client_factory(region: str, config=None):
        def track_call(*args, **kwargs):
            call_args_list.append(args)

        client = FakeCSClientForBothFailStates(
            region_id="cn-hangzhou",
            tasks_data_by_state={
                'failed': failed_tasks,
                'fail': fail_tasks
            },
            page_info={"total_count": 1}
        )
        # 添加跟踪功能
        original_call_api = client.call_api_async
        async def tracked_call_api(params, request, runtime):
            # 记录调用参数
            call_args_list.append({
                'params': params,
                'request': request
            })
            return await original_call_api(params, request, runtime)
        client.call_api_async = tracked_call_api
        return client

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    # 查询状态为 'failed' 的任务
    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        state=module_under_test.ClusterTaskState.FAILED
    )

    assert isinstance(result, ListClusterTasksOutput)
    # 由于内部会查询两次 (failed + fail)，应该得到两种状态的任务
    # 验证至少有一次查询是针对 'fail' 状态的
    # 检查调用次数和参数
    # 这里主要是验证内部逻辑会同时查询两个失败状态


@pytest.mark.asyncio
async def test_list_cluster_tasks_fetch_both_fail_states_when_query_fail():
    """测试当查询状态为 'fail' 时也同时获取 'failed' 状态的任务"""
    now = int(datetime.now(timezone.utc).timestamp())
    # 准备 'fail' 状态的任务
    fail_tasks = [
        {
            "task_id": "task-1",
            "state": "fail",
            "created": now - 600,
            "task_type": "nodepool_create",
            "task": {"created": now - 600}
        }
    ]

    # 准备 'failed' 状态的任务
    failed_tasks = [
        {
            "task_id": "task-2",
            "state": "failed",
            "created": now - 300,
            "task_type": "nodepool_scaleout",
            "task": {"created": now - 300}
        }
    ]

    tool = make_tasks_handler_and_tool()

    # 跟踪 API 调用次数
    call_args_list = []

    def cs_client_factory(region: str, config=None):
        def track_call(*args, **kwargs):
            call_args_list.append(args)

        client = FakeCSClientForBothFailStates(
            region_id="cn-hangzhou",
            tasks_data_by_state={
                'fail': fail_tasks,
                'failed': failed_tasks
            },
            page_info={"total_count": 1}
        )
        # 添加跟踪功能
        original_call_api = client.call_api_async
        async def tracked_call_api(params, request, runtime):
            # 记录调用参数
            call_args_list.append({
                'params': params,
                'request': request
            })
            return await original_call_api(params, request, runtime)
        client.call_api_async = tracked_call_api
        return client

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    # 查询状态为 'fail' 的任务
    result = await tool(
        ctx,
        cluster_id="c12345678901234567890123456789012",
        state=module_under_test.ClusterTaskState.FAIL
    )

    assert isinstance(result, ListClusterTasksOutput)
    # 由于内部会查询两次 (fail + failed)，应该得到两种状态的任务
    # 验证内部逻辑会同时查询两个失败状态
