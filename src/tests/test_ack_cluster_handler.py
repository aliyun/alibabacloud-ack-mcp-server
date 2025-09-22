import pytest
import sys
import os

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ack_cluster_handler as module_under_test
from models import ListClustersOutput, ClusterInfo, ErrorModel, ClusterErrorCodes


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
            "network_mode": "VPC",
            "proxy_mode": "ipvs"
        },
        {
            "cluster_name": "c2", 
            "clusterId": "cls-2", 
            "status": "Initializing", 
            "clusterType": "Kubernetes",
            "currentVersion": "1.23.6-aliyun.1"
        },
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(_region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, region_id="cn-hangzhou", page_size=10, page_num=1)

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
    
    # 验证第二个集群信息（兼容不同字段名）
    cluster2 = result.clusters[1]
    assert cluster2.cluster_name == "c2"
    assert cluster2.cluster_id == "cls-2"
    assert cluster2.state == "Initializing"
    assert cluster2.cluster_type == "Kubernetes"


@pytest.mark.asyncio
async def test_list_clusters_api_error():
    """测试 API 调用失败的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str):
        raise RuntimeError("NO_RAM_POLICY_AUTH: 当前账号无ram policy权限，需要授权")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, region_id="cn-hangzhou", page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 0
    assert result.clusters == []
    assert result.error is not None
    assert result.error.error_code == ClusterErrorCodes.NO_RAM_POLICY_AUTH
    assert "ram policy权限" in result.error.error_message


@pytest.mark.asyncio
async def test_list_clusters_missing_region_id():
    """测试缺少 region_id 参数的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient([])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, region_id="", page_size=10, page_num=1)

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

    result = await tool(ctx, region_id="cn-hangzhou", page_size=10, page_num=1)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 0
    assert result.clusters == []
    assert result.error is None


@pytest.mark.asyncio
async def test_list_clusters_with_pagination():
    """测试分页参数"""
    fake_clusters = [
        {"name": "c1", "cluster_id": "cls-1", "state": "Running", "cluster_type": "ManagedKubernetes"}
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, region_id="cn-hangzhou", page_size=100, page_num=2)

    assert isinstance(result, ListClustersOutput)
    assert result.count == 1
    assert len(result.clusters) == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_list_clusters_invalid_cluster_data():
    """测试无效的集群数据"""
    fake_clusters = [
        {"name": "c1", "cluster_id": "cls-1", "state": "Running", "cluster_type": "ManagedKubernetes"},
        {"invalid": "data"},  # 无效数据
        {"name": "c3", "cluster_id": "cls-3", "state": "Running", "cluster_type": "Kubernetes"}
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str, config=None):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, region_id="cn-hangzhou", page_size=10, page_num=1)

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
        network_mode="VPC",
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
    assert cluster.network_mode == "VPC"
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


