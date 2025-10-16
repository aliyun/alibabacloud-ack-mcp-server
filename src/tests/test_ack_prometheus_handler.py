import os
import sys
import pytest

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ack_prometheus_handler as module_under_test


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
    def __init__(self, lifespan_context=None):
        self.lifespan_context = lifespan_context or {}


class FakeContext:
    def __init__(self, lifespan_context=None):
        self.request_context = FakeRequestContext(lifespan_context)


def make_handler_and_tools():
    server = FakeServer()
    handler = module_under_test.PrometheusHandler(server, {})
    return handler, server.tools


class DummyResp:
    def __init__(self, data: dict, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_query_prometheus_instant(monkeypatch):
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus"]

    # mock endpoint 解析：通过 providers.prometheus_endpoints
    ctx = FakeContext({
        "config": {"region_id": "cn-hangzhou"},
        "providers": {"prometheus_endpoints": {"c-1": "http://prom.example.com"}},
    })

    # mock httpx.AsyncClient.get
    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            assert url.endswith("/api/v1/query")
            return DummyResp({
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {"metric": {"pod": "p1"}, "value": [1680307200, "0.1"]}
                    ]
                }
            })

    monkeypatch.setattr(module_under_test.httpx, "AsyncClient", lambda timeout=60.0: DummyClient())

    res = await tool(ctx, cluster_id="c-1", promql="up", start_time=None, end_time=None, step=None)

    assert res.resultType == "vector"
    assert isinstance(res.result, list)
    assert len(res.result) == 1
    assert res.result[0].metric["pod"] == "p1"


@pytest.mark.asyncio
async def test_query_prometheus_range(monkeypatch):
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus"]

    ctx = FakeContext({
        "config": {"region_id": "cn-hangzhou"},
        "providers": {"prometheus_endpoints": {"c-2": "http://prom.example.com"}},
    })

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None):
            assert url.endswith("/api/v1/query_range")
            assert params.get("step") == "30s"
            return DummyResp({
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {"metric": {"pod": "p1"}, "values": [[1680307200, "0.01"], [1680307260, "0.02"]]}
                    ]
                }
            })

    monkeypatch.setattr(module_under_test.httpx, "AsyncClient", lambda timeout=60.0: DummyClient())

    res = await tool(ctx, cluster_id="c-2", promql="up", start_time="2025-09-16T06:15:23.239Z", end_time="2025-09-16T06:16:23.239Z", step="30s")

    assert res.resultType == "matrix"
    assert len(res.result[0].values) == 2


@pytest.mark.asyncio
async def test_query_prometheus_metric_guidance_success():
    """测试成功查询 Prometheus 指标指引"""
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    # 模拟 runtime context 中的 Prometheus 指标指引数据
    mock_guidance = {
        "initialized": True,
        "metrics_dictionary": {
            "test_metrics": {
                "metrics": [
                    {
                        "name": "container_cpu_usage_seconds_total",
                        "category": "cpu",
                        "labels": ["pod", "container"],
                        "description": "容器CPU使用时间总计",
                        "type": "counter"
                    },
                    {
                        "name": "container_memory_working_set_bytes",
                        "category": "memory",
                        "labels": ["pod", "container"],
                        "description": "容器内存工作集字节",
                        "type": "gauge"
                    }
                ]
            }
        },
        "promql_best_practice": {
            "test_practice": {
                "rules": [
                    {
                        "rule_name": "CPU resource usage high",
                        "category": "cpu",
                        "labels": ["pod"],
                        "description": "CPU usage is higher than 85%",
                        "expression": "cpu_usage > 85",
                        "severity": "Critical",
                        "recommendation_sop": "Check CPU limits"
                    }
                ]
            }
        }
    }

    ctx = FakeContext({
        "providers": {
            "prometheus_guidance": mock_guidance
        }
    })

    result = await tool(ctx, resource_label="pod", metric_category="cpu")
    
    # 验证返回结果结构
    assert hasattr(result, "metrics")
    assert hasattr(result, "promql_samples")
    assert result.error is None
    
    # 验证指标定义
    assert len(result.metrics) == 1
    assert result.metrics[0].name == "container_cpu_usage_seconds_total"
    assert result.metrics[0].category == "cpu"
    
    # 验证 PromQL 最佳实践
    assert len(result.promql_samples) == 1
    assert result.promql_samples[0].rule_name == "CPU resource usage high"
    assert result.promql_samples[0].category == "cpu"


@pytest.mark.asyncio
async def test_query_prometheus_metric_guidance_not_initialized():
    """测试 Prometheus 指标指引未初始化时的处理"""
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    ctx = FakeContext({
        "providers": {
            "prometheus_guidance": {
                "initialized": False,
                "error": "Guidance not initialized"
            }
        }
    })

    result = await tool(ctx, resource_label="pod", metric_category="cpu")
    
    assert "error" in result
    assert result["error"]["error_code"] == "GuidanceNotInitialized"


@pytest.mark.asyncio
async def test_query_prometheus_metric_guidance_missing_providers():
    """测试缺少 providers 时的处理"""
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    ctx = FakeContext({
        "providers": {}
    })

    result = await tool(ctx, resource_label="pod", metric_category="cpu")
    
    assert "error" in result
    assert result["error"]["error_code"] == "GuidanceNotInitialized"


@pytest.mark.asyncio
async def test_query_prometheus_metric_guidance_no_match():
    """测试没有匹配结果时的查询"""
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    mock_guidance = {
        "initialized": True,
        "metrics_dictionary": {
            "test_metrics": {
                "metrics": [
                    {
                        "name": "node_cpu_usage",
                        "category": "cpu",
                        "labels": ["node"],  # 不包含 "pod"
                        "description": "Node CPU usage",
                        "type": "gauge"
                    }
                ]
            }
        },
        "promql_best_practice": {
            "test_practice": {
                "rules": [
                    {
                        "rule_name": "Node CPU high",
                        "category": "cpu",
                        "labels": ["node"],  # 不包含 "pod"
                        "description": "Node CPU usage is high",
                        "expression": "node_cpu > 80",
                        "severity": "Critical"
                    }
                ]
            }
        }
    }

    ctx = FakeContext({
        "providers": {
            "prometheus_guidance": mock_guidance
        }
    })

    result = await tool(ctx, resource_label="pod", metric_category="cpu")
    
    assert result.error is None
    assert len(result.metrics) == 0
    assert len(result.promql_samples) == 0


@pytest.mark.asyncio
async def test_query_prometheus_metric_guidance_case_insensitive():
    """测试大小写不敏感的查询"""
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    mock_guidance = {
        "initialized": True,
        "metrics_dictionary": {
            "test_metrics": {
                "metrics": [
                    {
                        "name": "container_cpu_usage",
                        "category": "CPU",  # 大写
                        "labels": ["pod"],
                        "description": "Container CPU usage",
                        "type": "gauge"
                    }
                ]
            }
        },
        "promql_best_practice": {
            "test_practice": {
                "rules": [
                    {
                        "rule_name": "CPU High",
                        "category": "CPU",  # 大写
                        "labels": ["pod"],
                        "description": "CPU usage is high",
                        "expression": "cpu > 80",
                        "severity": "Critical"
                    }
                ]
            }
        }
    }

    ctx = FakeContext({
        "providers": {
            "prometheus_guidance": mock_guidance
        }
    })

    result = await tool(ctx, resource_label="pod", metric_category="cpu")  # 小写查询
    
    assert result.error is None
    assert len(result.metrics) == 1
    assert result.metrics[0].name == "container_cpu_usage"
    assert len(result.promql_samples) == 1
    assert result.promql_samples[0].rule_name == "CPU High"


