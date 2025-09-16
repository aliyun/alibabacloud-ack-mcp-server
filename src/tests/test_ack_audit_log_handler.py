import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ack_audit_log_handler as module_under_test
from models import (
    QueryAuditLogsOutput, 
    AuditLogEntry, 
    ErrorModel, 
    AuditLogErrorCodes
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


def make_handler_and_tool(settings=None):
    server = FakeServer()
    module_under_test.ACKAuditLogHandler(server, settings or {})
    return server.tools["query_audit_logs"]


@pytest.mark.asyncio
async def test_query_audit_logs_success():
    """测试成功查询审计日志"""
    fake_logs = [
        {
            "__time__": 1640995200,  # 2022-01-01 00:00:00
            "verb": "get",
            "objectRef": {
                "resource": "pods",
                "name": "nginx-pod",
                "namespace": "default"
            },
            "user": {
                "username": "system:admin"
            },
            "sourceIPs": ["192.168.1.1"],
            "userAgent": "kubectl/v1.21.0",
            "responseStatus": {
                "code": 200,
                "status": "Success"
            },
            "requestURI": "/api/v1/namespaces/default/pods/nginx-pod",
            "requestObject": {"kind": "Pod"},
            "responseObject": {"status": "Running"}
        }
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def sls_client_factory(cluster_id: str, region_id: str):
        return FakeSLSClient(fake_logs)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk", "region_id": "cn-hangzhou"},
        "providers": {"sls_client_factory": sls_client_factory}
    })

    result = await tool(
        ctx, 
        cluster_id="c123456", 
        namespace="default", 
        verbs="get", 
        limit=10
    )

    assert isinstance(result, QueryAuditLogsOutput)
    assert result.total == 1
    assert len(result.entries) == 1
    assert result.error is None
    assert result.query is not None
    
    # 验证日志条目
    entry = result.entries[0]
    assert entry.verb == "get"
    assert entry.resource_type == "pods"
    assert entry.resource_name == "nginx-pod"
    assert entry.namespace == "default"
    assert entry.user == "system:admin"
    assert entry.source_ips == ["192.168.1.1"]
    assert entry.response_code == 200


@pytest.mark.asyncio
async def test_query_audit_logs_no_sls_client():
    """测试 SLS 客户端不可用的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"sls_client_factory": None}
    })

    result = await tool(ctx, cluster_id="c123456", namespace="default")

    assert isinstance(result, QueryAuditLogsOutput)
    assert result.total == 0
    assert result.entries == []
    assert result.error is not None
    assert result.error.error_code == AuditLogErrorCodes.SLS_CLIENT_INIT_AK_ERROR


@pytest.mark.asyncio
async def test_query_audit_logs_missing_cluster_id():
    """测试缺少 cluster_id 参数的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def sls_client_factory(cluster_id: str, region_id: str):
        return FakeSLSClient([])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"sls_client_factory": sls_client_factory}
    })

    result = await tool(ctx, cluster_id="", namespace="default")

    assert isinstance(result, QueryAuditLogsOutput)
    assert result.total == 0
    assert result.entries == []
    assert result.error is not None
    assert result.error.error_code == AuditLogErrorCodes.LOGSTORE_NOT_FOUND


@pytest.mark.asyncio
async def test_query_audit_logs_empty_result():
    """测试返回空结果的情况"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def sls_client_factory(cluster_id: str, region_id: str):
        return FakeSLSClient([])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk", "region_id": "cn-hangzhou"},
        "providers": {"sls_client_factory": sls_client_factory}
    })

    result = await tool(ctx, cluster_id="c123456", namespace="default")

    assert isinstance(result, QueryAuditLogsOutput)
    assert result.total == 0
    assert result.entries == []
    assert result.error is None


@pytest.mark.asyncio
async def test_query_audit_logs_with_filters():
    """测试带过滤条件的查询"""
    fake_logs = [
        {
            "__time__": 1640995200,
            "verb": "create",
            "objectRef": {
                "resource": "deployments",
                "name": "nginx-deployment",
                "namespace": "app"
            },
            "user": {"username": "kube-admin"},
            "sourceIPs": ["10.0.0.1"],
            "userAgent": "kubectl/v1.21.0",
            "responseStatus": {"code": 201, "status": "Created"},
            "requestURI": "/apis/apps/v1/namespaces/app/deployments",
            "requestObject": {"kind": "Deployment"},
            "responseObject": {"status": "Created"}
        }
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def sls_client_factory(cluster_id: str, region_id: str):
        return FakeSLSClient(fake_logs)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk", "region_id": "cn-hangzhou"},
        "providers": {"sls_client_factory": sls_client_factory}
    })

    result = await tool(
        ctx,
        cluster_id="c123456",
        namespace="app",
        verbs="create",
        resource_types="deployments",
        resource_name="nginx-deployment",
        user="kube-admin",
        start_time="1h",
        end_time="30m",
        limit=50
    )

    assert isinstance(result, QueryAuditLogsOutput)
    assert result.total == 1
    assert len(result.entries) == 1
    assert result.error is None
    
    entry = result.entries[0]
    assert entry.verb == "create"
    assert entry.resource_type == "deployments"
    assert entry.resource_name == "nginx-deployment"
    assert entry.namespace == "app"
    assert entry.user == "kube-admin"


@pytest.mark.asyncio
async def test_query_audit_logs_limit_validation():
    """测试结果限制验证"""
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def sls_client_factory(cluster_id: str, region_id: str):
        return FakeSLSClient([])

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk", "region_id": "cn-hangzhou"},
        "providers": {"sls_client_factory": sls_client_factory}
    })

    # 测试超过最大限制的情况
    result = await tool(ctx, cluster_id="c123456", limit=200)

    assert isinstance(result, QueryAuditLogsOutput)
    # 限制应该被限制在100以内
    assert result.total == 0


def test_parse_time_relative():
    """测试相对时间解析"""
    # 测试分钟
    timestamp = module_under_test._parse_time("30m")
    assert isinstance(timestamp, int)
    assert timestamp > 0
    
    # 测试小时
    timestamp = module_under_test._parse_time("1h")
    assert isinstance(timestamp, int)
    assert timestamp > 0
    
    # 测试天
    timestamp = module_under_test._parse_time("7d")
    assert isinstance(timestamp, int)
    assert timestamp > 0


def test_parse_time_iso():
    """测试 ISO 时间格式解析"""
    timestamp = module_under_test._parse_time("2024-01-01T10:00:00")
    assert isinstance(timestamp, int)
    assert timestamp > 0


def test_parse_time_invalid():
    """测试无效时间格式"""
    with pytest.raises(ValueError):
        module_under_test._parse_time("invalid-time")


def test_build_sls_query():
    """测试 SLS 查询语句构建"""
    from models import QueryAuditLogsInput
    
    params = QueryAuditLogsInput(
        cluster_id="c123456",
        namespace="default",
        verbs="get,list",
        resource_types="pods,services",
        resource_name="nginx-*",
        user="system:*"
    )
    
    query = module_under_test._build_sls_query(params)
    
    assert "objectRef.namespace: \"default\"" in query
    assert "verb: \"get\"" in query or "verb: \"list\"" in query
    assert "objectRef.resource: \"pods\"" in query or "objectRef.resource: \"services\"" in query
    assert "objectRef.name: nginx-*" in query
    assert "user.username: system:*" in query


def test_parse_audit_log_entry():
    """测试审计日志条目解析"""
    log_data = {
        "__time__": 1640995200,
        "verb": "get",
        "objectRef": {
            "resource": "pods",
            "name": "nginx-pod",
            "namespace": "default"
        },
        "user": {
            "username": "system:admin"
        },
        "sourceIPs": ["192.168.1.1", "10.0.0.1"],
        "userAgent": "kubectl/v1.21.0",
        "responseStatus": {
            "code": 200,
            "status": "Success"
        },
        "requestURI": "/api/v1/namespaces/default/pods/nginx-pod",
        "requestObject": {"kind": "Pod"},
        "responseObject": {"status": "Running"}
    }
    
    entry = module_under_test._parse_audit_log_entry(log_data)
    
    assert isinstance(entry, AuditLogEntry)
    assert entry.verb == "get"
    assert entry.resource_type == "pods"
    assert entry.resource_name == "nginx-pod"
    assert entry.namespace == "default"
    assert entry.user == "system:admin"
    assert entry.source_ips == ["192.168.1.1", "10.0.0.1"]
    assert entry.user_agent == "kubectl/v1.21.0"
    assert entry.response_code == 200
    assert entry.response_status == "Success"
    assert entry.request_uri == "/api/v1/namespaces/default/pods/nginx-pod"
    assert entry.request_object == {"kind": "Pod"}
    assert entry.response_object == {"status": "Running"}


def test_audit_log_entry_model():
    """测试 AuditLogEntry 数据模型"""
    entry = AuditLogEntry(
        timestamp="2024-01-01T10:00:00",
        verb="get",
        resource_type="pods",
        resource_name="nginx-pod",
        namespace="default",
        user="system:admin",
        source_ips=["192.168.1.1"],
        user_agent="kubectl/v1.21.0",
        response_code=200,
        response_status="Success",
        request_uri="/api/v1/namespaces/default/pods/nginx-pod",
        request_object={"kind": "Pod"},
        response_object={"status": "Running"},
        raw_log='{"verb": "get"}'
    )
    
    assert entry.timestamp == "2024-01-01T10:00:00"
    assert entry.verb == "get"
    assert entry.resource_type == "pods"
    assert entry.resource_name == "nginx-pod"
    assert entry.namespace == "default"
    assert entry.user == "system:admin"
    assert entry.source_ips == ["192.168.1.1"]
    assert entry.user_agent == "kubectl/v1.21.0"
    assert entry.response_code == 200
    assert entry.response_status == "Success"
    assert entry.request_uri == "/api/v1/namespaces/default/pods/nginx-pod"
    assert entry.request_object == {"kind": "Pod"}
    assert entry.response_object == {"status": "Running"}
    assert entry.raw_log == '{"verb": "get"}'


def test_query_audit_logs_output_model():
    """测试 QueryAuditLogsOutput 数据模型"""
    entry = AuditLogEntry(
        verb="get",
        resource_type="pods",
        resource_name="nginx-pod",
        namespace="default"
    )
    
    output = QueryAuditLogsOutput(
        query="verb: \"get\"",
        entries=[entry],
        total=1
    )
    
    assert output.query == "verb: \"get\""
    assert len(output.entries) == 1
    assert output.total == 1
    assert output.error is None


def test_query_audit_logs_output_with_error():
    """测试带错误信息的 QueryAuditLogsOutput"""
    error = ErrorModel(
        error_code=AuditLogErrorCodes.SLS_CLIENT_INIT_AK_ERROR,
        error_message="密钥在环境变量中不存在，client初始化失败"
    )
    
    output = QueryAuditLogsOutput(
        query=None,
        entries=[],
        total=0,
        error=error
    )
    
    assert output.query is None
    assert output.entries == []
    assert output.total == 0
    assert output.error is not None
    assert output.error.error_code == AuditLogErrorCodes.SLS_CLIENT_INIT_AK_ERROR
    assert "密钥在环境变量中不存在" in output.error.error_message


def test_audit_log_error_codes():
    """测试错误码常量"""
    assert AuditLogErrorCodes.SLS_CLIENT_INIT_AK_ERROR == "SLS_CLIENT_INIT_AK_ERROR"
    assert AuditLogErrorCodes.LOGSTORE_NOT_FOUND == "LOGSTORE_NOT_FOUND"
