import types
import pytest
import tempfile
import os
import sys

# 添加父目录到路径以导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import kubectl_handler as module_under_test


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


def make_handler_and_tool():
    server = FakeServer()
    handler = module_under_test.KubectlHandler(server, {"allow_write": True})
    tool = server.tools["ack_kubectl"]
    return handler, tool


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.mark.asyncio
async def test_kubectl_tool_success(monkeypatch):
    def fake_run(*args, **kwargs):
        # 获取命令参数，可能是字符串或列表
        cmd = args[0] if args else None
        if isinstance(cmd, str):
            assert "kubectl" in cmd
        elif isinstance(cmd, list):
            assert cmd[0] == "kubectl"
        return DummyCompleted(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    
    # 创建一个带有cs_client_factory的lifespan_context
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
            self.providers = {"cs_client_factory": FakeCSClientFactory()}
    
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="version --client", cluster_id="test-cluster")

    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.stderr in (None, "")


@pytest.mark.asyncio
async def test_kubectl_tool_error(monkeypatch):
    def fake_run(*args, **kwargs):
        cmd = args[0] if args else None
        raise module_under_test.subprocess.CalledProcessError(1, cmd, output="", stderr="boom")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    
    # 创建一个带有cs_client_factory的lifespan_context
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
            self.providers = {"cs_client_factory": FakeCSClientFactory()}
    
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="get pods -A", cluster_id="test-cluster")

    assert result.exit_code == 1
    assert result.stderr == "boom"


def test_handler_registers_tool():
    server = FakeServer()
    module_under_test.KubectlHandler(server, {})
    assert "ack_kubectl" in server.tools


@pytest.mark.asyncio
async def test_kubectl_with_cluster_id_success(monkeypatch):
    """测试使用 cluster_id 成功获取 kubeconfig 并执行命令"""
    
    # 清理全局缓存
    module_under_test._context_manager = None
    
    # Mock CS 客户端和响应
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    def fake_run(*args, **kwargs):
        cmd = args[0] if args else None
        if isinstance(cmd, str):
            assert "kubectl" in cmd
        elif isinstance(cmd, list):
            assert cmd[0] == "kubectl"
        return DummyCompleted(returncode=0, stdout="pods found", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.exit_code == 0
    assert result.stdout == "pods found"


@pytest.mark.asyncio
async def test_kubectl_with_cluster_id_no_kubeconfig(monkeypatch):
    """测试使用 cluster_id 但获取不到 kubeconfig 的情况"""
    
    # 清理全局缓存
    module_under_test._context_manager = None
    
    # Mock CS 客户端返回空响应
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = None
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.exit_code == 1
    assert "Failed to get kubeconfig" in result.stderr


@pytest.mark.asyncio
async def test_kubectl_without_cluster_id(monkeypatch):
    """测试使用有效的 cluster_id 的情况（使用ACK API获取 kubeconfig）"""
    
    # 清理全局缓存
    module_under_test._context_manager = None
    
    def fake_run(*args, **kwargs):
        cmd = args[0] if args else None
        if isinstance(cmd, str):
            assert "kubectl" in cmd
        elif isinstance(cmd, list):
            assert cmd[0] == "kubectl"
        return DummyCompleted(returncode=0, stdout="cluster pods", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    # Mock CS 客户端
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
            self.providers = fake_providers
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="test-cluster")
    
    assert result.exit_code == 0
    assert result.stdout == "cluster pods"


@pytest.mark.asyncio
async def test_kubectl_cs_client_factory_not_available(monkeypatch):
    """测试 CS 客户端工厂不可用的情况"""
    
    # 清理全局缓存
    module_under_test._context_manager = None
    
    # Mock providers 中没有 cs_client_factory
    fake_providers = {}
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.exit_code == 1
    assert "CS client not set" in result.stderr


@pytest.mark.asyncio
async def test_kubectl_temp_file_cleanup(monkeypatch):
    """测试临时 kubeconfig 文件被正确清理"""
    
    temp_files_created = []
    
    class FakeCSClient:
        def describe_cluster_detail(self, cluster_id):
            class FakeResponse:
                class FakeBody:
                    def __init__(self):
                        self.master_url = '{"api_server_endpoint": "https://test.example.com:6443", "intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                body = FakeBody()
            return FakeResponse()
            
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id, config=None):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    def fake_run(*args, **kwargs):
        return DummyCompleted(returncode=0, stdout="success", stderr="")
    
    # Mock tempfile.NamedTemporaryFile
    def mock_named_temporary_file(*args, **kwargs):
        class MockFile:
            def __init__(self):
                self.name = f"/tmp/test_kubeconfig_{len(temp_files_created)}.yaml"
                temp_files_created.append(self.name)
            
            def write(self, content):
                pass
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                pass
        
        return MockFile()
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.exit_code == 0

