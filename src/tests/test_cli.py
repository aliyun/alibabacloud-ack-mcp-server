"""Tests for the ack-mcp-cli module."""

import json
import os
import sys
import pytest

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cli import (
    CLIRunner,
    build_settings_dict,
    build_tool_arg_parser,
    parse_tool_args,
    _resolve_param_type,
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
# _resolve_param_type tests
# ---------------------------------------------------------------------------


class TestResolveParamType:
    """Tests for JSON schema type resolution."""

    def test_plain_string(self):
        assert _resolve_param_type({"type": "string"}) == "string"

    def test_plain_integer(self):
        assert _resolve_param_type({"type": "integer"}) == "integer"

    def test_plain_boolean(self):
        assert _resolve_param_type({"type": "boolean"}) == "boolean"

    def test_nullable_string(self):
        schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        assert _resolve_param_type(schema) == "string"

    def test_nullable_integer(self):
        schema = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
        assert _resolve_param_type(schema) == "integer"

    def test_no_type(self):
        assert _resolve_param_type({}) is None


# ---------------------------------------------------------------------------
# build_tool_arg_parser tests
# ---------------------------------------------------------------------------


class TestBuildToolArgParser:
    """Tests for dynamic argparse generation from tool schema."""

    def test_string_required(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "Cluster ID"},
            },
            "required": ["cluster_id"],
        }
        parser = build_tool_arg_parser("test_tool", params)
        ns = parser.parse_args(["--cluster-id", "c123"])
        assert ns.cluster_id == "c123"

    def test_integer_with_default(self):
        """Schema defaults are applied by parse_tool_args, not at parser level."""
        params = {
            "properties": {
                "page_size": {"type": "integer", "default": 10, "description": "Page size"},
            },
        }
        # Default applied by parse_tool_args
        result = parse_tool_args("t", params, [])
        assert result["page_size"] == 10

        # Override
        result = parse_tool_args("t", params, ["--page-size", "20"])
        assert result["page_size"] == 20

    def test_boolean_param(self):
        params = {
            "properties": {
                "is_result_exception": {
                    "type": "boolean",
                    "default": True,
                    "description": "Filter exceptions",
                },
            },
        }
        # Default
        result = parse_tool_args("t", params, [])
        assert result["is_result_exception"] is True

        # Explicit true
        result = parse_tool_args("t", params, ["--is-result-exception"])
        assert result["is_result_exception"] is True

        # Explicit false
        result = parse_tool_args("t", params, ["--no-is-result-exception"])
        assert result["is_result_exception"] is False

    def test_nullable_optional_not_provided(self):
        params = {
            "properties": {
                "namespace": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "default": None,
                    "description": "Optional namespace",
                },
            },
        }
        # Not provided -> omitted (None default is not included)
        result = parse_tool_args("t", params, [])
        assert "namespace" not in result

    def test_nullable_optional_provided(self):
        params = {
            "properties": {
                "namespace": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "default": None,
                    "description": "Optional namespace",
                },
            },
        }
        result = parse_tool_args("t", params, ["--namespace", "kube-system"])
        assert result["namespace"] == "kube-system"

    def test_no_properties(self):
        params = {"properties": {}}
        parser = build_tool_arg_parser("test_tool", params)
        ns = parser.parse_args([])
        assert ns._json_args is None

    def test_json_args_fallback(self):
        params = {"properties": {}}
        parser = build_tool_arg_parser("test_tool", params)
        ns = parser.parse_args(["--args", '{"key": "val"}'])
        assert ns._json_args == '{"key": "val"}'


# ---------------------------------------------------------------------------
# parse_tool_args tests
# ---------------------------------------------------------------------------


class TestParseToolArgs:
    """Tests for merging CLI flags and --args JSON."""

    def test_cli_flags_only(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
                "limit": {"type": "integer", "default": 10, "description": "Limit"},
            },
            "required": ["cluster_id"],
        }
        result = parse_tool_args("t", params, ["--cluster-id", "c1", "--limit", "50"])
        assert result == {"cluster_id": "c1", "limit": 50}

    def test_json_fallback_only(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
            },
            "required": ["cluster_id"],
        }
        result = parse_tool_args("t", params, ["--args", '{"cluster_id": "c1"}'])
        assert result == {"cluster_id": "c1"}

    def test_cli_flags_override_json(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
                "limit": {"type": "integer", "default": 10, "description": "Limit"},
            },
            "required": ["cluster_id"],
        }
        result = parse_tool_args(
            "t",
            params,
            ["--args", '{"cluster_id": "from_json", "limit": 5}', "--cluster-id", "from_cli"],
        )
        # CLI flag overrides JSON for cluster_id
        assert result["cluster_id"] == "from_cli"
        # limit comes from JSON (CLI didn't pass --limit)
        assert result["limit"] == 5

    def test_schema_default_applied(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
                "limit": {"type": "integer", "default": 10, "description": "Limit"},
            },
            "required": ["cluster_id"],
        }
        result = parse_tool_args("t", params, ["--cluster-id", "c1"])
        assert result["cluster_id"] == "c1"
        assert result["limit"] == 10  # schema default

    def test_none_default_omitted(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
                "namespace": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                    "default": None,
                    "description": "NS",
                },
            },
            "required": ["cluster_id"],
        }
        result = parse_tool_args("t", params, ["--cluster-id", "c1"])
        assert result == {"cluster_id": "c1"}
        assert "namespace" not in result

    def test_missing_required_exits(self):
        params = {
            "properties": {
                "cluster_id": {"type": "string", "description": "ID"},
            },
            "required": ["cluster_id"],
        }
        with pytest.raises(SystemExit):
            parse_tool_args("t", params, [])

    def test_empty_params(self):
        params = {"properties": {}}
        result = parse_tool_args("t", params, [])
        assert result == {}


# ---------------------------------------------------------------------------
# CLIRunner tests
# ---------------------------------------------------------------------------


class TestCLIRunner:
    """Tests for CLIRunner."""

    def test_runner_initialisation(self):
        runner = _make_runner()
        assert runner.mcp is not None
        assert runner.providers is not None
        assert runner.mcp._lifespan_result is not None

    def test_list_tools_output(self, capsys):
        runner = _make_runner()
        runner.list_tools()
        captured = capsys.readouterr()
        assert "list_clusters" in captured.out
        assert "ack_kubectl" in captured.out
        assert "get_current_time" in captured.out

    def test_list_tools_contains_all_tools(self, capsys):
        runner = _make_runner()
        runner.list_tools()
        captured = capsys.readouterr()
        expected = [
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
        for name in expected:
            assert name in captured.out, f"Tool '{name}' not in list output"

    def test_describe_tool_output(self, capsys):
        runner = _make_runner()
        runner.describe_tool("query_audit_log")
        captured = capsys.readouterr()
        assert "query_audit_log" in captured.out
        assert "--cluster-id" in captured.out
        assert "--namespace" in captured.out
        assert "--limit" in captured.out
        assert "required" in captured.out
        assert "default=" in captured.out

    def test_describe_tool_no_params(self, capsys):
        runner = _make_runner()
        runner.describe_tool("get_current_time")
        captured = capsys.readouterr()
        assert "get_current_time" in captured.out
        assert "(no parameters)" in captured.out

    def test_describe_unknown_tool(self):
        runner = _make_runner()
        with pytest.raises(SystemExit):
            runner.describe_tool("nonexistent")

    def test_call_get_current_time(self, capsys):
        runner = _make_runner()
        runner.call_tool("get_current_time", {})
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "current_time_iso" in result
        assert "current_time_unix" in result

    def test_call_unknown_tool(self):
        runner = _make_runner()
        with pytest.raises(SystemExit):
            runner.call_tool("nonexistent", {})


# ---------------------------------------------------------------------------
# FastMCP integration tests
# ---------------------------------------------------------------------------


class TestCLIRunnerFastMCPIntegration:
    """Tests verifying FastMCP list_tools/call_tool integration."""

    def test_mcp_has_lifespan_result(self):
        runner = _make_runner()
        assert "config" in runner.mcp._lifespan_result
        assert "providers" in runner.mcp._lifespan_result

    def test_mcp_list_tools_returns_tools(self):
        import asyncio

        runner = _make_runner()
        tools = asyncio.run(runner.mcp.list_tools())
        assert len(tools) >= 9
        tool_names = {t.name for t in tools}
        assert "list_clusters" in tool_names
        assert "ack_kubectl" in tool_names

    def test_mcp_call_tool_get_current_time(self):
        import asyncio

        runner = _make_runner()
        result = asyncio.run(runner.mcp.call_tool("get_current_time", {}))
        assert result.structured_content is not None
        assert "current_time_iso" in result.structured_content

    def test_tool_parameters_have_schema(self):
        """Every tool should have a parameters schema with properties."""
        import asyncio

        runner = _make_runner()
        tools = asyncio.run(runner.mcp.list_tools())
        for tool in tools:
            assert tool.parameters is not None, f"Tool '{tool.name}' has no parameters"
            assert "properties" in tool.parameters, f"Tool '{tool.name}' has no properties"


# ---------------------------------------------------------------------------
# build_settings_dict tests
# ---------------------------------------------------------------------------


class TestBuildSettingsDict:
    """Tests for the settings dict builder."""

    def test_default_values(self):
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
        assert settings["region_id"] == "cn-hangzhou"
        assert settings["kubectl_timeout"] == 30

    def test_cli_args_override(self):
        import argparse

        args = argparse.Namespace(
            allow_write=True,
            region="us-west-1",
            access_key_id="AK",
            access_key_secret="SK",
            kubeconfig_mode="LOCAL",
            kubeconfig_path="/tmp/kc",
        )
        settings = build_settings_dict(args)
        assert settings["allow_write"] is True
        assert settings["region_id"] == "us-west-1"
        assert settings["access_key_id"] == "AK"
