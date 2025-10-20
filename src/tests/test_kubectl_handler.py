import pytest
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
    
    ctx = FakeContext()
    result = await tool(ctx, command="version --client")

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
    
    ctx = FakeContext()
    result = await tool(ctx, command="get pods -A")

    assert result.exit_code == 1
    assert result.stderr == "boom"


def test_handler_registers_tool():
    server = FakeServer()
    module_under_test.KubectlHandler(server, {})
    assert "ack_kubectl" in server.tools


@pytest.mark.asyncio
async def test_kubectl_with_local_kubeconfig(monkeypatch):
    """测试使用本地kubeconfig文件执行命令"""
    
    def fake_run(*args, **kwargs):
        cmd = args[0] if args else None
        if isinstance(cmd, str):
            assert "kubectl" in cmd
        elif isinstance(cmd, list):
            assert cmd[0] == "kubectl"
        return DummyCompleted(returncode=0, stdout="pods found", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    _, tool = make_handler_and_tool()
    ctx = FakeContext()
    result = await tool(ctx, command="get pods")
    
    assert result.exit_code == 0
    assert result.stdout == "pods found"


@pytest.mark.asyncio
async def test_kubectl_kubeconfig_path_resolution(monkeypatch):
    """测试kubeconfig路径解析逻辑"""
    
    def fake_run(*args, **kwargs):
        return DummyCompleted(returncode=0, stdout="success", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    handler, tool = make_handler_and_tool()
    
    # 测试默认路径
    default_path = handler._get_kubeconfig_path()
    assert default_path == os.path.expanduser("~/.kube/config")
    
    # 测试环境变量路径
    test_kubeconfig_path = "/tmp/test-kubeconfig"
    monkeypatch.setenv("KUBECONFIG", test_kubeconfig_path)
    monkeypatch.setattr(os.path, "exists", lambda path: path == test_kubeconfig_path)
    
    resolved_path = handler._get_kubeconfig_path()
    assert resolved_path == test_kubeconfig_path


def test_is_write_command_readonly_commands():
    """测试只读命令应该返回 False"""
    handler = module_under_test.KubectlHandler(None, {})
    
    # 测试所有只读命令
    readonly_commands = [
        "api-resources",
        "api-versions", 
        "cluster-info",
        "describe pods my-pod",
        "diff -f deployment.yaml",
        "events",
        "explain pods",
        "get pods -A",
        "kustomize build",
        "logs my-pod",
        "options",
        "top nodes",
        "version --client"
    ]
    
    for command in readonly_commands:
        is_write, error = handler.is_write_command(command)
        assert is_write is False, f"Command '{command}' should be read-only"
        assert error is None, f"Command '{command}' should not have error"


def test_is_write_command_write_commands():
    """测试写命令应该返回 True"""
    handler = module_under_test.KubectlHandler(None, {})
    
    # 测试常见的写命令
    write_commands = [
        "apply -f deployment.yaml",
        "create deployment nginx --image=nginx",
        "delete pod my-pod",
        "patch deployment nginx -p '{\"spec\":{\"replicas\":3}}'",
        "scale deployment nginx --replicas=5",
        "edit deployment nginx",
        "replace -f deployment.yaml",
        "rollout restart deployment/nginx",
        "annotate pod my-pod description='test'",
        "label pod my-pod env=prod",
        "cordon node-1",
        "uncordon node-1",
        "drain node-1",
        "taint nodes node-1 key=value:NoSchedule",
        "exec my-pod -- ls /tmp",
        "cp my-pod:/tmp/file ./file",
        "port-forward service/my-service 8080:80",
        "proxy --port=8080",
        "attach my-pod",
        "auth can-i create pods",
        "certificate approve csr-xyz",
        "config set-context dev --namespace=development",
        "completion bash",
        "plugin list",
        "wait --for=condition=Ready pod/my-pod"
    ]
    
    for command in write_commands:
        is_write, error = handler.is_write_command(command)
        assert is_write is True, f"Command '{command}' should be write command"
        assert error is not None, f"Command '{command}' should have error message"
        assert "not allowed in read-only mode" in error, f"Error message should mention read-only mode for '{command}'"


def test_is_write_command_empty_command():
    """测试空命令应该返回 True（写命令）"""
    handler = module_under_test.KubectlHandler(None, {})
    
    is_write, error = handler.is_write_command("")
    assert is_write is True
    assert error == "Empty command not allowed"
    
    is_write, error = handler.is_write_command("   ")
    assert is_write is True
    assert error == "Empty command not allowed"


def test_is_write_command_readonly_with_parameters():
    """测试只读命令带复杂参数的情况"""
    handler = module_under_test.KubectlHandler(None, {})
    
    complex_readonly_commands = [
        "get pods -o wide --all-namespaces --field-selector=status.phase=Running",
        "describe deployment nginx --namespace=default",
        "logs my-pod --container=nginx --tail=100 --follow=false",
        "top pods --sort-by=memory --namespace=kube-system",
        "events --field-selector involvedObject.name=my-pod",
        "explain pod.spec.containers.resources.limits",
        "api-resources --verbs=list --namespaced=true",
        "api-versions --output=json",
        "cluster-info dump --output-directory=/tmp",
        "diff -f deployment.yaml --server-side",
        "version --output=yaml --client",
        "kustomize build ./overlays/production"
    ]
    
    for command in complex_readonly_commands:
        is_write, error = handler.is_write_command(command)
        assert is_write is False, f"Command '{command}' should be read-only"
        assert error is None, f"Command '{command}' should not have error"


@pytest.mark.asyncio
async def test_write_command_blocked_in_readonly_mode(monkeypatch):
    """测试在只读模式下写命令被阻止"""
    
    # 创建只读模式的handler
    server = FakeServer()
    handler = module_under_test.KubectlHandler(server, {"allow_write": False})
    tool = server.tools["ack_kubectl"]
    
    ctx = FakeContext()
    
    # 测试写命令被阻止
    result = await tool(ctx, command="apply -f deployment.yaml")
    assert result.exit_code == 1
    assert "not allowed in read-only mode" in result.stderr
    
    # 测试只读命令正常执行
    def fake_run(*args, **kwargs):
        return DummyCompleted(returncode=0, stdout="pods found", stderr="")
    
    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)
    
    result = await tool(ctx, command="get pods")
    assert result.exit_code == 0
    assert result.stdout == "pods found"

