import pytest

import ack_cluster_handler as module_under_test


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
    return server.tools["describe_clusters_brief"]


@pytest.mark.asyncio
async def test_describe_clusters_brief_success():
    fake_clusters = [
        {"name": "c1", "cluster_id": "cls-1", "state": "running", "region_id": "cn-hangzhou", "node_count": 5, "cluster_type": "ManagedKubernetes"},
        {"cluster_name": "c2", "clusterId": "cls-2", "status": "initializing", "size": 3, "clusterType": "Ask"},
    ]

    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(_region: str):
        return FakeCSClient(fake_clusters)

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, resource_type="cluster", regions=["cn-hangzhou"], page_size=10)

    assert isinstance(result, dict)
    assert "clusters" in result
    assert result["count"] == 2
    brief0 = result["clusters"][0]
    assert brief0["name"] == "c1"
    assert brief0["cluster_id"] == "cls-1"
    assert brief0["region_id"] == "cn-hangzhou"


@pytest.mark.asyncio
async def test_describe_clusters_brief_partial_error():
    tool = make_handler_and_tool({"access_key_id": "ak", "access_key_secret": "sk"})

    def cs_client_factory(region: str):
        if region == "cn-hangzhou":
            return FakeCSClient([{"name": "ok", "cluster_id": "id-1", "state": "running"}])
        raise RuntimeError("region error")

    ctx = FakeContext({
        "config": {"access_key_id": "ak", "access_key_secret": "sk"},
        "providers": {"cs_client_factory": cs_client_factory}
    })

    result = await tool(ctx, resource_type="cluster", regions=["cn-hangzhou", "cn-shanghai"], page_size=10)

    assert result["count"] == 1
    assert result["errors"] is not None
    assert any(e.get("region") == "cn-shanghai" for e in result["errors"]) 


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


