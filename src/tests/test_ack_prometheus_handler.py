import json
import pytest

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
async def test_query_prometheus_metric_guidance():
    _, tools = make_handler_and_tools()
    tool = tools["query_prometheus_metric_guidance"]

    ctx = FakeContext()
    out = await tool(ctx, resource_label="node", metric_category="cpu")
    assert out.error is None
    assert isinstance(out.metrics, list)
    assert any(m.name for m in out.metrics)


