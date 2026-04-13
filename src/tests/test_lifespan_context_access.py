"""Tests verifying all handlers access lifespan_context via ctx.lifespan_context.
This ensures that every _get_cs_client / _get_sls_client helper function works
correctly in both normal MCP server mode (request_context available) and CLI mode
(request_context is None, falls back to _lifespan_result).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import clients.cs_client as cs_client_module
import ack_cluster_handler as cluster_module
import ack_diagnose_handler as diagnose_module
import ack_inspect_handler as inspect_module
import ack_prometheus_handler as prometheus_module
import ack_audit_log_handler as audit_module
import ack_controlplane_log_handler as controlplane_module
import kubectl_handler as kubectl_module

# ---------------------------------------------------------------------------
# Fake context helpers
# ---------------------------------------------------------------------------
FAKE_CONFIG = {"region_id": "cn-hangzhou", "access_key_id": "ak", "access_key_secret": "sk"}


class _FakeCSClient:
    """Minimal CS client stub."""

    pass


class _FakeSLSClient:
    """Minimal SLS client stub."""

    pass


def _cs_factory(region, config):
    return _FakeCSClient()


def _sls_factory(region, config):
    return _FakeSLSClient()


FULL_PROVIDERS = {
    "cs_client_factory": _cs_factory,
    "sls_client_factory": _sls_factory,
}
FULL_LIFESPAN = {"config": FAKE_CONFIG, "providers": FULL_PROVIDERS}


class FakeRequestContext:
    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


class NormalModeContext:
    """Simulates normal MCP server mode: request_context is available."""

    def __init__(self, lifespan_context):
        self.request_context = FakeRequestContext(lifespan_context)
        self.lifespan_context = lifespan_context


class CLIModeContext:
    """Simulates CLI mode: request_context is None, lifespan_context set directly."""

    def __init__(self, lifespan_context):
        self.request_context = None
        self.lifespan_context = lifespan_context


class EmptyContext:
    """Simulates a context with no providers at all."""

    def __init__(self):
        self.request_context = None
        self.lifespan_context = {}


# ---------------------------------------------------------------------------
# clients/cs_client.py :: get_cs_client
# ---------------------------------------------------------------------------
class TestClientsGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = cs_client_module.get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = cs_client_module.get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            cs_client_module.get_cs_client(ctx, "cn-hangzhou")

    def test_factory_receives_region_and_config(self):
        captured = {}

        def capturing_factory(region, config):
            captured["region"] = region
            captured["config"] = config
            return _FakeCSClient()

        lifespan = {
            "config": FAKE_CONFIG,
            "providers": {"cs_client_factory": capturing_factory},
        }
        ctx = CLIModeContext(lifespan)
        cs_client_module.get_cs_client(ctx, "us-west-1")
        assert captured["region"] == "us-west-1"
        assert captured["config"] == FAKE_CONFIG


# ---------------------------------------------------------------------------
# ack_cluster_handler.py :: _get_cs_client
# ---------------------------------------------------------------------------
class TestClusterHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = cluster_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = cluster_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            cluster_module._get_cs_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# ack_diagnose_handler.py :: _get_cs_client
# ---------------------------------------------------------------------------
class TestDiagnoseHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = diagnose_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = diagnose_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            diagnose_module._get_cs_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# ack_inspect_handler.py :: _get_cs_client
# ---------------------------------------------------------------------------
class TestInspectHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = inspect_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = inspect_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            inspect_module._get_cs_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# ack_prometheus_handler.py :: _get_cs_client
# ---------------------------------------------------------------------------
class TestPrometheusHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = prometheus_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = prometheus_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            prometheus_module._get_cs_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# ack_audit_log_handler.py :: _get_cs_client / _get_sls_client
# ---------------------------------------------------------------------------
class TestAuditLogHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = audit_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = audit_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            audit_module._get_cs_client(ctx, "cn-hangzhou")


class TestAuditLogHandlerGetSLSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = audit_module._get_sls_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeSLSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = audit_module._get_sls_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeSLSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="sls_client_factory not available"):
            audit_module._get_sls_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# ack_controlplane_log_handler.py :: _get_cs_client / _get_sls_client
# ---------------------------------------------------------------------------
class TestControlPlaneLogHandlerGetCSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = controlplane_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = controlplane_module._get_cs_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeCSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="cs_client_factory not available"):
            controlplane_module._get_cs_client(ctx, "cn-hangzhou")


class TestControlPlaneLogHandlerGetSLSClient:
    def test_normal_mode(self):
        ctx = NormalModeContext(FULL_LIFESPAN)
        client = controlplane_module._get_sls_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeSLSClient)

    def test_cli_mode(self):
        ctx = CLIModeContext(FULL_LIFESPAN)
        client = controlplane_module._get_sls_client(ctx, "cn-hangzhou")
        assert isinstance(client, _FakeSLSClient)

    def test_empty_providers_raises(self):
        ctx = EmptyContext()
        with pytest.raises(RuntimeError, match="sls_client_factory not available"):
            controlplane_module._get_sls_client(ctx, "cn-hangzhou")


# ---------------------------------------------------------------------------
# kubectl_handler.py :: KubectlHandler._setup_cs_client
# ---------------------------------------------------------------------------
class TestKubectlHandlerSetupCSClient:
    def _make_handler(self):
        class FakeServer:
            def __init__(self):
                self.tools = {}

            def tool(self, name=None, description=None):
                def decorator(func):
                    self.tools[name or func.__name__] = func
                    return func

                return decorator

        server = FakeServer()
        handler = kubectl_module.KubectlHandler(server, {"allow_write": False})
        return handler

    def test_normal_mode(self):
        handler = self._make_handler()
        ctx = NormalModeContext(FULL_LIFESPAN)
        handler._setup_cs_client(ctx)
        cm = kubectl_module.get_context_manager()
        assert cm._cs_client is not None

    def test_cli_mode(self):
        handler = self._make_handler()
        ctx = CLIModeContext(FULL_LIFESPAN)
        handler._setup_cs_client(ctx)
        cm = kubectl_module.get_context_manager()
        assert cm._cs_client is not None

    def test_empty_providers_no_crash(self):
        handler = self._make_handler()
        ctx = EmptyContext()
        # Should not raise, just logs a warning
        handler._setup_cs_client(ctx)


# ---------------------------------------------------------------------------
# cli.py :: CLIRunner sets _lifespan_result_set
# ---------------------------------------------------------------------------
class TestCLIRunnerLifespanResult:
    def _make_runner(self):
        from cli import CLIRunner

        settings = {
            "allow_write": False,
            "region_id": "cn-hangzhou",
            "access_key_id": None,
            "access_key_secret": None,
            "kubeconfig_mode": "LOCAL",
            "kubeconfig_path": "~/.kube/config",
            "cache_ttl": 300,
            "cache_max_size": 1000,
            "diagnose_timeout": 600,
            "diagnose_poll_interval": 15,
            "kubectl_timeout": 30,
            "api_timeout": 60,
            "access_secret_key": None,
            "original_settings": None,
        }
        return CLIRunner(settings)

    def test_lifespan_result_set_flag(self):
        runner = self._make_runner()
        assert runner.mcp._lifespan_result_set is True

    def test_lifespan_result_has_providers(self):
        runner = self._make_runner()
        result = runner.mcp._lifespan_result
        assert "providers" in result
        assert "config" in result

    def test_lifespan_result_has_cs_client_factory(self):
        runner = self._make_runner()
        providers = runner.mcp._lifespan_result["providers"]
        assert "cs_client_factory" in providers
        assert callable(providers["cs_client_factory"])
