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
    tool = server.tools["kubectl"]
    return handler, tool


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.mark.asyncio
async def test_kubectl_tool_success(monkeypatch):
    def fake_run(cmd, capture_output=True, text=True, check=True, env=None):
        assert cmd[:1] == ["kubectl"]
        return DummyCompleted(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    
    # 创建一个简单的 lifespan_context 用于测试
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
    
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="version --client", cluster_id=None)

    assert result.status == "success"
    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.stderr in (None, "")


@pytest.mark.asyncio
async def test_kubectl_tool_error(monkeypatch):
    class DummyCalled(Exception):
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    def fake_run(cmd, capture_output=True, text=True, check=True, env=None):
        raise module_under_test.subprocess.CalledProcessError(1, cmd, output="", stderr="boom")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    
    # 创建一个简单的 lifespan_context 用于测试
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
    
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="get pods -A", cluster_id=None)

    assert result.status == "error"
    assert result.exit_code == 1
    assert result.stderr == "boom"


def test_handler_registers_tool():
    server = FakeServer()
    module_under_test.KubectlHandler(server, {})
    assert "kubectl" in server.tools


@pytest.mark.asyncio
async def test_kubectl_with_cluster_id_success(monkeypatch):
    """测试使用 cluster_id 成功获取 kubeconfig 并执行命令"""
    
    # Mock CS 客户端和响应
    class FakeCSClient:
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    def fake_run(cmd, capture_output=True, text=True, check=True, env=None):
        assert cmd[:1] == ["kubectl"]
        # 验证环境变量中设置了 KUBECONFIG
        if env and "KUBECONFIG" in env:
            assert env["KUBECONFIG"].endswith('.yaml')
        return DummyCompleted(returncode=0, stdout="pods found", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.status == "success"
    assert result.exit_code == 0
    assert result.stdout == "pods found"
    assert result.kubeconfig_source == "ack_api"


@pytest.mark.asyncio
async def test_kubectl_with_cluster_id_no_kubeconfig(monkeypatch):
    """测试使用 cluster_id 但获取不到 kubeconfig 的情况"""
    
    # Mock CS 客户端返回空响应
    class FakeCSClient:
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = None
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id):
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
    
    assert result.status == "error"
    assert result.exit_code == 1
    assert "Failed to fetch kubeconfig" in result.error
    assert result.kubeconfig_source == "ack_api"


@pytest.mark.asyncio
async def test_kubectl_without_cluster_id(monkeypatch):
    """测试不使用 cluster_id 的情况（使用本地 kubeconfig）"""
    
    def fake_run(cmd, capture_output=True, text=True, check=True, env=None):
        assert cmd[:1] == ["kubectl"]
        # 验证没有设置 KUBECONFIG 环境变量
        if env:
            assert "KUBECONFIG" not in env
        return DummyCompleted(returncode=0, stdout="local pods", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    _, tool = make_handler_and_tool()
    
    # 创建一个简单的 lifespan_context 用于测试
    class SimpleLifespanContext:
        def __init__(self):
            self.config = {"region_id": "cn-hangzhou"}
    
    ctx = FakeContext(SimpleLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id=None)
    
    assert result.status == "success"
    assert result.exit_code == 0
    assert result.stdout == "local pods"
    assert result.kubeconfig_source == "local"


@pytest.mark.asyncio
async def test_kubectl_cs_client_factory_not_available(monkeypatch):
    """测试 CS 客户端工厂不可用的情况"""
    
    # Mock providers 中没有 cs_client_factory
    fake_providers = {}
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.status == "error"
    assert result.exit_code == 1
    assert "Failed to fetch kubeconfig" in result.error


@pytest.mark.asyncio
async def test_kubectl_temp_file_cleanup(monkeypatch):
    """测试临时 kubeconfig 文件被正确清理"""
    
    temp_files_created = []
    
    class FakeCSClient:
        def describe_cluster_user_kubeconfig(self, cluster_id, request):
            class FakeResponse:
                class FakeBody:
                    config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"
                body = FakeBody()
            return FakeResponse()
    
    class FakeCSClientFactory:
        def __call__(self, region_id):
            return FakeCSClient()
    
    # Mock providers
    fake_providers = {
        "cs_client_factory": FakeCSClientFactory()
    }
    
    class FakeLifespanContext:
        def __init__(self):
            self.providers = fake_providers
            self.config = {"region_id": "cn-hangzhou"}
    
    def fake_run(cmd, capture_output=True, text=True, check=True, env=None):
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
    monkeypatch.setattr(module_under_test.tempfile, "NamedTemporaryFile", mock_named_temporary_file)
    
    # Mock os.unlink to track file deletion
    deleted_files = []
    
    def mock_unlink(path):
        deleted_files.append(path)
        # 不调用原始的 unlink，因为我们只是要跟踪调用
    
    def mock_exists(path):
        return True  # 总是返回 True，让清理逻辑执行
    
    monkeypatch.setattr(os, "unlink", mock_unlink)
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext(FakeLifespanContext())
    result = await tool(ctx, command="get pods", cluster_id="c123456")
    
    assert result.status == "success"
    # 验证临时文件被创建和删除
    assert len(temp_files_created) == 1
    assert temp_files_created[0] in deleted_files

