import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ack_controlplane_log_handler as module_under_test
from models import (
    QueryControlPlaneLogsOutput, 
    ControlPlaneLogEntry, 
    ErrorModel, 
    ControlPlaneLogErrorCodes,
    ControlPlaneLogConfig
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


class FakeSLSResponse:
    def __init__(self, logs=None):
        self.body = Mock()
        self.body.logs = logs or []


class FakeSLSClient:
    def __init__(self, response_logs=None):
        self._response_logs = response_logs or []

    def get_logs(self, request):
        return FakeSLSResponse(self._response_logs)


class FakeCSClient:
    def __init__(self, components=None, log_project="k8s-log-test"):
        self.components = components if components is not None else ["apiserver", "kcm", "scheduler", "ccm"]
        self.log_project = log_project

    def get_cluster_audit_project(self, cluster_id):
        # 这个方法在控制面日志中不需要，但为了兼容性保留
        class FakeResponse:
            class FakeBody:
                def __init__(self, audit_enabled, sls_project_name):
                    self.audit_enabled = audit_enabled
                    self.sls_project_name = sls_project_name
            def __init__(self, audit_enabled, sls_project_name):
                self.body = self.FakeBody(audit_enabled, sls_project_name)
        return FakeResponse(True, "k8s-log-test")


class FakeCSClientFactory:
    def __init__(self, components=None, log_project="k8s-log-test"):
        self.components = components if components is not None else ["apiserver", "kcm", "scheduler", "ccm"]
        self.log_project = log_project

    def __call__(self, region_id, config=None):
        return FakeCSClient(self.components, self.log_project)


class FakeSLSClientFactory:
    def __init__(self, response_logs=None):
        self.response_logs = response_logs or []

    def __call__(self, cluster_id, region_id):
        return FakeSLSClient(self.response_logs)


def make_handler_and_tool(settings=None, tool_name="query_controlplane_logs"):
    server = FakeServer()
    handler = module_under_test.ACKControlPlaneLogHandler(server, settings)
    # 根据指定的工具名称获取工具
    if tool_name in server.tools:
        tool = server.tools[tool_name]
    else:
        # 默认使用 query_controlplane_logs
        tool = server.tools.get("query_controlplane_logs")
    return handler, tool


@pytest.mark.asyncio
async def test_query_controlplane_logs_success():
    """测试成功查询控制面日志"""
    fake_logs = [
        {
            "__time__": 1640995200,  # 2022-01-01 00:00:00
            "component": "apiserver",
            "level": "info",
            "message": "API request processed",
            "source": "kube-apiserver",
            "user": "system:serviceaccount:kube-system:default"
        },
        {
            "__time__": 1640995201,
            "component": "apiserver", 
            "level": "warn",
            "message": "Rate limit exceeded",
            "source": "kube-apiserver",
            "user": "admin"
        }
    ]
    
    # 创建模拟的上下文
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm", "scheduler", "ccm"],
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory(fake_logs)
        }
    }
    ctx = FakeContext(lifespan_context)
    
    # 创建处理器和工具
    handler, tool = make_handler_and_tool()
    
    # 执行测试
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        filter_pattern="level: info",
        start_time="24h",
        limit=10
    )
    
    # 验证结果
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is None
    assert result.total == 2
    assert len(result.entries) == 2
    assert result.query is not None
    assert "component: apiserver" in result.query
    assert "level: info" in result.query
    
    # 验证日志条目
    assert result.entries[0].component == "apiserver"
    assert result.entries[0].level == "info"
    assert result.entries[0].message == "API request processed"
    assert result.entries[1].component == "apiserver"
    assert result.entries[1].level == "warn"
    assert result.entries[1].message == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_query_controlplane_logs_component_not_enabled():
    """测试查询未启用的组件"""
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm"],  # 不包含 scheduler
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory()
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="scheduler",  # 未启用的组件
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is not None
    assert result.error.error_code == ControlPlaneLogErrorCodes.INVALID_COMPONENT
    assert "scheduler" in result.error.error_message
    assert "apiserver" in result.error.error_message
    assert "kcm" in result.error.error_message


@pytest.mark.asyncio
async def test_query_controlplane_logs_no_components():
    """测试控制面日志功能未启用"""
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=[],  # 空组件列表，表示未启用
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory()
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is not None
    assert result.error.error_code == ControlPlaneLogErrorCodes.CONTROLPLANE_LOG_NOT_ENABLED
    assert "not enabled" in result.error.error_message


@pytest.mark.asyncio
async def test_query_controlplane_logs_missing_cluster_id():
    """测试缺少集群ID"""
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(),
            "sls_client_factory": FakeSLSClientFactory()
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="",  # 空的集群ID
        component_name="apiserver",
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is not None
    assert result.error.error_code == ControlPlaneLogErrorCodes.CLUSTER_NOT_FOUND
    assert "required" in result.error.error_message


@pytest.mark.asyncio
async def test_query_controlplane_logs_missing_component_name():
    """测试缺少组件名称"""
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(),
            "sls_client_factory": FakeSLSClientFactory()
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="",  # 空的组件名称
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is not None
    assert result.error.error_code == ControlPlaneLogErrorCodes.INVALID_COMPONENT
    assert "required" in result.error.error_message


@pytest.mark.asyncio
async def test_query_controlplane_logs_sls_client_error():
    """测试SLS客户端初始化失败"""
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(),
            "sls_client_factory": None  # 模拟SLS客户端工厂不可用
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is not None
    assert result.error.error_code == ControlPlaneLogErrorCodes.SLS_CLIENT_INIT_AK_ERROR


@pytest.mark.asyncio
async def test_query_controlplane_logs_different_components():
    """测试不同组件的日志查询"""
    fake_logs = [
        {
            "__time__": 1640995200,
            "component": "kcm",
            "level": "error",
            "message": "Controller manager error",
            "source": "kube-controller-manager"
        }
    ]
    
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm", "scheduler", "ccm"],
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory(fake_logs)
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="kcm",
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is None
    assert result.total == 1
    assert len(result.entries) == 1
    assert result.entries[0].component == "kcm"
    assert result.entries[0].level == "error"
    assert result.entries[0].message == "Controller manager error"


@pytest.mark.asyncio
async def test_query_controlplane_logs_with_filter_pattern():
    """测试带过滤条件的日志查询"""
    fake_logs = [
        {
            "__time__": 1640995200,
            "component": "scheduler",
            "level": "info",
            "message": "Pod scheduled successfully",
            "source": "kube-scheduler"
        }
    ]
    
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm", "scheduler", "ccm"],
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory(fake_logs)
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="scheduler",
        filter_pattern="level: info AND message: *scheduled*",
        limit=10
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is None
    assert result.total == 1
    assert len(result.entries) == 1
    assert "level: info AND message: *scheduled*" in result.query


def test_parse_time_iso_format():
    """测试ISO 8601时间格式解析"""
    # 测试ISO 8601格式 (UTC时间)
    timestamp = module_under_test._parse_time("2022-01-01T00:00:00Z")
    # 2022-01-01T00:00:00Z 对应的时间戳
    expected = 1640995200  # 这是正确的UTC时间戳
    assert timestamp == expected


def test_parse_time_relative_format():
    """测试相对时间格式解析"""
    # 测试相对时间格式
    now = datetime.now()
    
    # 测试1小时前
    timestamp_1h = module_under_test._parse_time("1h")
    expected_1h = int((now - timedelta(hours=1)).timestamp())
    assert abs(timestamp_1h - expected_1h) < 2  # 允许2秒误差
    
    # 测试24小时前
    timestamp_24h = module_under_test._parse_time("24h")
    expected_24h = int((now - timedelta(hours=24)).timestamp())
    assert abs(timestamp_24h - expected_24h) < 2  # 允许2秒误差


def test_parse_time_unix_timestamp():
    """测试Unix时间戳格式解析"""
    # 测试秒级时间戳
    timestamp = module_under_test._parse_time("1640995200")
    assert timestamp == 1640995200
    
    # 测试毫秒级时间戳
    timestamp_ms = module_under_test._parse_time("1640995200000")
    assert timestamp_ms == 1640995200


def test_build_controlplane_log_query():
    """测试控制面日志查询语句构建"""
    # 测试基础查询
    query = module_under_test._build_controlplane_log_query("apiserver")
    assert query == "component: apiserver"
    
    # 测试带过滤条件的查询
    query_with_filter = module_under_test._build_controlplane_log_query(
        "kcm", 
        "level: error"
    )
    assert query_with_filter == "component: kcm AND level: error"
    
    # 测试复杂过滤条件
    query_complex = module_under_test._build_controlplane_log_query(
        "scheduler",
        "level: info AND message: *scheduled*"
    )
    assert query_complex == "component: scheduler AND level: info AND message: *scheduled*"


def test_parse_controlplane_log_entry():
    """测试控制面日志条目解析"""
    log_data = {
        "__time__": 1640995200,
        "component": "apiserver",
        "level": "info",
        "message": "API request processed",
        "source": "kube-apiserver",
        "user": "admin"
    }
    
    entry = module_under_test._parse_controlplane_log_entry(log_data)
    
    assert isinstance(entry, ControlPlaneLogEntry)
    assert entry.component == "apiserver"
    assert entry.level == "info"
    assert entry.message == "API request processed"
    assert entry.source == "kube-apiserver"
    assert entry.raw_log is not None


def test_parse_controlplane_log_entry_with_json_fields():
    """测试包含JSON字段的控制面日志条目解析"""
    log_data = {
        "__time__": "1640995200",  # 字符串格式的时间戳
        "component": "kcm",
        "level": "warn",
        "message": "Controller warning",
        "source": "kube-controller-manager",
        "metadata": '{"namespace": "kube-system", "resource": "pod"}'
    }
    
    entry = module_under_test._parse_controlplane_log_entry(log_data)
    
    assert isinstance(entry, ControlPlaneLogEntry)
    assert entry.component == "kcm"
    assert entry.level == "warn"
    assert entry.message == "Controller warning"
    assert entry.source == "kube-controller-manager"


@pytest.mark.asyncio
async def test_query_controlplane_logs_time_formats():
    """测试不同时间格式的查询"""
    fake_logs = [
        {
            "__time__": 1640995200,
            "component": "apiserver",
            "level": "info",
            "message": "Test log entry"
        }
    ]
    
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm", "scheduler", "ccm"],
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory(fake_logs)
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    # 测试ISO 8601格式
    result_iso = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        start_time="2022-01-01T00:00:00Z",
        end_time="2022-01-02T00:00:00Z",
        limit=10
    )
    
    assert isinstance(result_iso, QueryControlPlaneLogsOutput)
    assert result_iso.error is None
    
    # 测试相对时间格式
    result_relative = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        start_time="1h",
        end_time="30m",
        limit=10
    )
    
    assert isinstance(result_relative, QueryControlPlaneLogsOutput)
    assert result_relative.error is None


@pytest.mark.asyncio
async def test_query_controlplane_logs_limit_validation():
    """测试结果限制验证"""
    fake_logs = [
        {"__time__": 1640995200, "component": "apiserver", "level": "info", "message": f"Log {i}"}
        for i in range(5)
    ]
    
    lifespan_context = {
        "config": {"region_id": "cn-hangzhou"},
        "providers": {
            "cs_client_factory": FakeCSClientFactory(
                components=["apiserver", "kcm", "scheduler", "ccm"],
                log_project="k8s-log-test-cluster"
            ),
            "sls_client_factory": FakeSLSClientFactory(fake_logs)
        }
    }
    ctx = FakeContext(lifespan_context)
    
    handler, tool = make_handler_and_tool()
    
    # 测试限制为3
    result = await tool(
        ctx=ctx,
        cluster_id="test-cluster-123",
        component_name="apiserver",
        limit=3
    )
    
    assert isinstance(result, QueryControlPlaneLogsOutput)
    assert result.error is None
    assert result.total == 5  # 实际返回的日志数量
    assert len(result.entries) == 5  # 模拟数据返回所有日志


if __name__ == "__main__":
    pytest.main([__file__])
