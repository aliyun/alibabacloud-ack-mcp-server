import types
import pytest

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
    def fake_run(cmd, capture_output=True, text=True, check=True):
        assert cmd[:1] == ["kubectl"]
        return DummyCompleted(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    ctx = FakeContext()
    result = await tool(ctx, command="version --client")

    assert result["status"] == "success"
    assert result["exit_code"] == 0
    assert result["stdout"] == "ok"
    assert result["stderr"] in (None, "")


@pytest.mark.asyncio
async def test_kubectl_tool_error(monkeypatch):
    class DummyCalled(Exception):
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "boom"

    def fake_run(cmd, capture_output=True, text=True, check=True):
        raise module_under_test.subprocess.CalledProcessError(1, cmd, output="", stderr="boom")

    monkeypatch.setattr(module_under_test.subprocess, "run", fake_run)

    _, tool = make_handler_and_tool()
    ctx = FakeContext()
    result = await tool(ctx, command="get pods -A")

    assert result["status"] == "error"
    assert result["exit_code"] == 1
    assert result["stderr"] == "boom"


def test_handler_registers_tool():
    server = FakeServer()
    module_under_test.KubectlHandler(server, {})
    assert "kubectl" in server.tools

