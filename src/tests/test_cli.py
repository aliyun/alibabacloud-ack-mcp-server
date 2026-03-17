"""Tests for the ack-mcp-cli module."""

import json
import os
import sys
import pytest

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cli import (
    CLIRunner,
    build_settings_dict,
)


# ---------------------------------------------------------------------------
# Helper to create a CLIRunner with minimal settings
# ---------------------------------------------------------------------------

def _make_runner(**overrides):
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
    settings.update(overrides)
    return CLIRunner(settings)


# ---------------------------------------------------------------------------
# CLIRunner tests
# ---------------------------------------------------------------------------

class TestCLIRunner:
    """Tests for CLIRunner initialisation and tool listing."""

    def test_runner_initialisation(self):
        runner = _make_runner()
        assert runner.mcp is not None
        assert runner.providers is not None

    def test_list_tools_output(self, capsys):
        runner = _make_runner()
        runner.list_tools()
        captured = capsys.readouterr()
        # Should contain known tool names
        assert "list_clusters" in captured.out
        assert "ack_kubectl" in captured.out
        assert "get_current_time" in captured.out

    def test_list_tools_contains_all_tools(self, capsys):
        """All 9 registered tools must appear in list output."""
        runner = _make_runner()
        runner.list_tools()
        captured = capsys.readouterr()

        expected_tools = [
            "list_clusters",
            "ack_kubectl",
            "query_prometheus",
            "query_prometheus_metric_guidance",
            "diagnose_resource",
            "query_inspect_report",
            "query_audit_log",
            "get_current_time",
            "query_controlplane_logs",
        ]
        for tool_name in expected_tools:
            assert tool_name in captured.out, f"Tool '{tool_name}' not found in list output"

    def test_call_get_current_time_output(self, capsys):
        """get_current_time should produce valid JSON output on stdout."""
        runner = _make_runner()
        runner.call_tool("get_current_time", "{}")
        captured = capsys.readouterr()

        # Parse the JSON output
        result = json.loads(captured.out)
        assert "current_time_iso" in result
        assert "current_time_unix" in result
        assert "timezone" in result

    def test_call_tool_unknown_tool(self):
        """Calling an unknown tool should exit with error."""
        runner = _make_runner()
        with pytest.raises(SystemExit):
            runner.call_tool("nonexistent_tool", "{}")

    def test_call_tool_invalid_json(self):
        """Calling with invalid JSON should exit with error."""
        runner = _make_runner()
        with pytest.raises(SystemExit):
            runner.call_tool("get_current_time", "not-valid-json{")

    def test_call_tool_non_dict_json(self):
        """Calling with non-dict JSON (e.g. list) should exit with error."""
        runner = _make_runner()
        with pytest.raises(SystemExit):
            runner.call_tool("get_current_time", "[1,2,3]")


# ---------------------------------------------------------------------------
# FastMCP integration tests
# ---------------------------------------------------------------------------

class TestCLIRunnerFastMCPIntegration:
    """Tests verifying that CLI uses FastMCP list_tools/call_tool correctly."""

    def test_mcp_has_lifespan_result(self):
        """The FastMCP instance should have _lifespan_result set."""
        runner = _make_runner()
        assert runner.mcp._lifespan_result is not None
        assert "config" in runner.mcp._lifespan_result
        assert "providers" in runner.mcp._lifespan_result

    def test_mcp_list_tools_returns_tools(self):
        """mcp.list_tools() should return the registered tools."""
        import asyncio
        runner = _make_runner()
        tools = asyncio.run(runner.mcp.list_tools())
        assert len(tools) >= 9
        tool_names = {t.name for t in tools}
        assert "list_clusters" in tool_names
        assert "ack_kubectl" in tool_names

    def test_mcp_call_tool_get_current_time(self):
        """mcp.call_tool should successfully execute get_current_time."""
        import asyncio
        runner = _make_runner()
        result = asyncio.run(runner.mcp.call_tool("get_current_time", {}))
        assert result is not None
        assert result.structured_content is not None
        assert "current_time_iso" in result.structured_content


# ---------------------------------------------------------------------------
# build_settings_dict tests
# ---------------------------------------------------------------------------

class TestBuildSettingsDict:
    """Tests for the settings dict builder."""

    def test_default_values(self):
        """Verify defaults when no CLI args or env vars are set."""
        import argparse
        args = argparse.Namespace(
            allow_write=False,
            region=None,
            access_key_id=None,
            access_key_secret=None,
            kubeconfig_mode=None,
            kubeconfig_path=None,
        )
        settings = build_settings_dict(args)

        assert settings["allow_write"] is False
        assert settings["region_id"] == "cn-hangzhou"  # default
        assert settings["kubectl_timeout"] == 30

    def test_cli_args_override(self):
        """CLI arguments should take precedence over defaults."""
        import argparse
        args = argparse.Namespace(
            allow_write=True,
            region="us-west-1",
            access_key_id="MY_AK",
            access_key_secret="MY_SK",
            kubeconfig_mode="LOCAL",
            kubeconfig_path="/tmp/kubeconfig",
        )
        settings = build_settings_dict(args)

        assert settings["allow_write"] is True
        assert settings["region_id"] == "us-west-1"
        assert settings["access_key_id"] == "MY_AK"
        assert settings["access_key_secret"] == "MY_SK"
        assert settings["kubeconfig_mode"] == "LOCAL"
        assert settings["kubeconfig_path"] == "/tmp/kubeconfig"
