# Copyright aliyun.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CLI entry point for directly executing MCP tools without starting the server.

Reuses the FastMCP server instance created by create_main_server() and calls
tools via mcp.list_tools() / mcp.call_tool().  Provider initialisation is
injected through mcp._lifespan_result so that ctx.lifespan_context works
without actually running the server event loop.

Tool parameters are automatically parsed from the tool's JSON schema and
exposed as CLI-friendly arguments (e.g. --cluster-id, --page-size).

Usage:
    ack-mcp-cli list                                                    # List all tools
    ack-mcp-cli describe <tool_name>                                    # Show tool parameters
    ack-mcp-cli call <tool_name> --cluster-id cxxx --command "get pods" # Schema-based args
    ack-mcp-cli call <tool_name> --args '<JSON>'                        # JSON fallback
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

# Try to import python-dotenv
try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from config import Configs
from main_server import create_main_server
from runtime_provider import ACKClusterRuntimeProvider


# ---------------------------------------------------------------------------
# Tool schema -> argparse helpers
# ---------------------------------------------------------------------------


def _resolve_param_type(prop_schema: Dict[str, Any]) -> Optional[str]:
    """Extract the effective JSON schema type from a property schema.

    Handles plain ``"type": "string"`` as well as the nullable
    ``"anyOf": [{"type": "string"}, {"type": "null"}]`` pattern.

    Returns one of: "string", "integer", "boolean", "number", or None.
    """
    if "type" in prop_schema:
        return prop_schema["type"]

    # anyOf nullable pattern
    any_of = prop_schema.get("anyOf")
    if isinstance(any_of, list):
        for entry in any_of:
            t = entry.get("type")
            if t and t != "null":
                return t
    return None


_UNSET = object()  # Sentinel to distinguish "not provided" from explicit default


def build_tool_arg_parser(tool_name: str, parameters: Dict[str, Any]) -> argparse.ArgumentParser:
    """Build an argparse parser from a tool's JSON schema ``parameters``.

    All schema-derived flags use ``default=_UNSET`` so that
    :func:`parse_tool_args` can tell which flags the user actually passed
    versus which were left at their schema default.

    Args:
        tool_name: Name of the tool (used in help text).
        parameters: The ``tool.parameters`` dict (JSON Schema object).

    Returns:
        An ArgumentParser whose namespace keys are the original parameter
        names (underscores preserved).
    """
    parser = argparse.ArgumentParser(
        prog=f"ack-mcp-cli call {tool_name}",
        description=f"Parameters for tool '{tool_name}'",
        add_help=False,  # We handle --help at the top level
    )

    properties: Dict[str, Any] = parameters.get("properties", {})

    for param_name, prop_schema in properties.items():
        cli_flag = f"--{param_name.replace('_', '-')}"
        param_type_str = _resolve_param_type(prop_schema)

        # First line of description for concise help
        raw_desc = prop_schema.get("description", "")
        help_text = raw_desc.split("\n")[0].strip() if raw_desc else ""

        kwargs: Dict[str, Any] = {
            "dest": param_name,
            "help": help_text,
            "default": _UNSET,
        }

        if param_type_str == "boolean":
            kwargs["action"] = argparse.BooleanOptionalAction
        else:
            type_map = {"string": str, "integer": int, "number": float}
            kwargs["type"] = type_map.get(param_type_str, str)

        # All flags are optional at the argparse level; requirement
        # validation happens in parse_tool_args after merging with --args.
        parser.add_argument(cli_flag, **kwargs)

    # Always add --args as JSON fallback
    parser.add_argument(
        "--args",
        "-a",
        dest="_json_args",
        type=str,
        default=None,
        help="JSON string of tool arguments (fallback, overridden by explicit flags)",
    )

    return parser


def parse_tool_args(
    tool_name: str,
    parameters: Dict[str, Any],
    argv: Sequence[str],
) -> Dict[str, Any]:
    """Parse CLI arguments for a tool call and return a merged dict.

    Priority: explicit CLI flags > ``--args`` JSON > schema defaults.
    Only parameters that are explicitly provided or have schema defaults
    are included in the result.
    """
    parser = build_tool_arg_parser(tool_name, parameters)
    ns = parser.parse_args(argv)

    properties = parameters.get("properties", {})
    required_set = set(parameters.get("required", []))

    # 1. Start with --args JSON if provided
    merged: Dict[str, Any] = {}
    if ns._json_args:
        try:
            merged = json.loads(ns._json_args)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid --args JSON: {e}")
            sys.exit(1)
        if not isinstance(merged, dict):
            logger.error("--args must be a JSON object (dict)")
            sys.exit(1)

    # 2. Overlay explicit CLI flags (only those the user actually passed)
    for param_name in properties:
        val = getattr(ns, param_name, _UNSET)
        if val is not _UNSET:
            merged[param_name] = val

    # 3. Fill in schema defaults for params still missing
    for param_name, prop_schema in properties.items():
        if param_name not in merged and "default" in prop_schema:
            default_val = prop_schema["default"]
            if default_val is not None:
                merged[param_name] = default_val

    # 4. Validate required params
    missing = [p for p in required_set if p not in merged]
    if missing:
        flags = ", ".join(f"--{p.replace('_', '-')}" for p in missing)
        logger.error(f"Missing required parameter(s) for '{tool_name}': {flags}")
        sys.exit(1)

    return merged


# ---------------------------------------------------------------------------
# CLI Runner
# ---------------------------------------------------------------------------


class CLIRunner:
    """Orchestrates provider initialisation and tool execution via FastMCP."""

    def __init__(self, settings_dict: Dict[str, Any]):
        self.settings = settings_dict

        # Create the FastMCP server with all tools registered
        self.mcp = create_main_server(settings_dict=settings_dict)

        # Initialise providers (same logic as the MCP server lifespan)
        runtime_provider = ACKClusterRuntimeProvider()
        self.providers = runtime_provider.initialize_providers(settings_dict)

        # Inject lifespan context so ctx.lifespan_context works in call_tool
        self.mcp._lifespan_result = {
            "config": settings_dict,
            "providers": self.providers,
        }

    # -- Cached tool metadata ---------------------------------------------------

    def _get_tools(self):
        """Return the list of registered tools (cached)."""
        if not hasattr(self, "_tools_cache"):
            self._tools_cache = asyncio.run(self.mcp.get_tools()).values()
        return self._tools_cache

    def _get_tool_by_name(self, name: str):
        """Look up a tool by name; exit with error if not found."""
        try:
            tool = asyncio.run(self.mcp.get_tool(name))
            return tool
        except Exception as e:
            available = ", ".join(sorted(t.name for t in self._get_tools()))
            logger.error(f"Unknown tool: '{name}'. Available tools: {available}")
            sys.exit(1)

    # -- Subcommands -----------------------------------------------------------

    def list_tools(self) -> None:
        """Print all available tools in a human-readable table."""
        tools = self._get_tools()
        if not tools:
            print("No tools registered.")
            return

        entries = []
        for t in tools:
            desc = (t.description or "").split("\n")[0].strip()
            entries.append((t.name, desc))
        entries.sort(key=lambda e: e[0])

        max_name = max(len(e[0]) for e in entries)
        col_width = max(max_name, len("Tool Name"))

        print(f"{'Tool Name':<{col_width}}  Description")
        print(f"{'-' * col_width}  {'-' * 50}")
        for name, desc in entries:
            print(f"{name:<{col_width}}  {desc}")

    def describe_tool(self, tool_name: str) -> None:
        """Print detailed parameter information for a single tool."""
        tool = self._get_tool_by_name(tool_name)

        print(f"Tool:  {tool.name}")
        desc_first = (tool.description or "").split("\n")[0].strip()
        print(f"Description:  {desc_first}")
        print()

        parameters = tool.parameters or {}
        properties = parameters.get("properties", {})
        required_set = set(parameters.get("required", []))

        if not properties:
            print("  (no parameters)")
            return

        print("Parameters:")
        for param_name, prop in properties.items():
            ptype = _resolve_param_type(prop) or "any"
            is_req = param_name in required_set and "default" not in prop
            default_val = prop.get("default", None)
            cli_flag = f"--{param_name.replace('_', '-')}"
            raw_desc = prop.get("description", "")
            desc_line = raw_desc.split("\n")[0].strip() if raw_desc else ""

            req_label = "required" if is_req else f"default={default_val!r}"
            print(f"  {cli_flag:<30}  type={ptype:<8}  {req_label}")
            if desc_line:
                print(f"      {desc_line}")

    def call_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """Call a tool by name with the given arguments dict and print the result."""
        try:
            tool = self._get_tool_by_name(tool_name)
            result = asyncio.run(tool.run(tool_args))
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            sys.exit(1)

        self._print_result(result)

    @staticmethod
    def _print_result(result: Any) -> None:
        """Serialize and print the tool result as JSON to stdout."""
        if hasattr(result, "structured_content") and result.structured_content is not None:
            print(json.dumps(result.structured_content, indent=2, ensure_ascii=False, default=str))
        elif hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            if len(texts) == 1:
                try:
                    parsed = json.loads(texts[0])
                    print(json.dumps(parsed, indent=2, ensure_ascii=False, default=str))
                except (json.JSONDecodeError, TypeError):
                    print(texts[0])
            else:
                print("\n".join(texts))
        else:
            print(json.dumps({"result": str(result)}, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Argument parsing & entry point
# ---------------------------------------------------------------------------


def _build_global_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with global flags and subcommands.

    The ``call`` subcommand only captures the tool name; the remaining
    argv is parsed later by the tool-specific schema parser.
    """
    parser = argparse.ArgumentParser(
        prog="ack-mcp-cli",
        description="AlibabaCloud ACK MCP CLI - Execute MCP tools directly from the command line",
    )

    # ---- Global arguments ----
    parser.add_argument(
        "--allow-write",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable write access mode (allow mutating operations)",
    )
    parser.add_argument(
        "--region",
        "-r",
        type=str,
        help="AlibabaCloud region (default: from env REGION_ID or cn-hangzhou)",
    )
    parser.add_argument(
        "--access-key-id",
        type=str,
        help="AlibabaCloud Access Key ID (default: from env ACCESS_KEY_ID)",
    )
    parser.add_argument(
        "--access-key-secret",
        type=str,
        help="AlibabaCloud Access Key Secret (default: from env ACCESS_KEY_SECRET)",
    )
    parser.add_argument(
        "--kubeconfig-mode",
        type=str,
        choices=["ACK_PUBLIC", "ACK_PRIVATE", "INCLUSTER", "LOCAL"],
        help="Mode to obtain kubeconfig (default: from env KUBECONFIG_MODE)",
    )
    parser.add_argument(
        "--kubeconfig-path",
        type=str,
        help="Path to local kubeconfig file when KUBECONFIG_MODE is LOCAL",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s 1.0.0",
    )

    # ---- Sub-commands ----
    subparsers = parser.add_subparsers(dest="subcommand", help="Available sub-commands")
    subparsers.add_parser("list", help="List all available tools")

    desc_parser = subparsers.add_parser("describe", help="Show detailed parameters for a tool")
    desc_parser.add_argument("tool_name", type=str, help="Name of the tool")

    call_parser = subparsers.add_parser("call", help="Call a tool by name")
    call_parser.add_argument("tool_name", type=str, help="Name of the tool to call")

    return parser


def build_settings_dict(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the unified settings dict from CLI arguments and environment variables."""
    return {
        "allow_write": args.allow_write,
        "region_id": args.region or os.getenv("REGION_ID", "cn-hangzhou"),
        "access_key_id": args.access_key_id or os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),
        "kubeconfig_mode": args.kubeconfig_mode or os.getenv("KUBECONFIG_MODE", "ACK_PUBLIC"),
        "kubeconfig_path": args.kubeconfig_path or os.getenv("KUBECONFIG_PATH", "~/.kube/config"),
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
        "diagnose_timeout": int(os.getenv("DIAGNOSE_TIMEOUT", "600")),
        "diagnose_poll_interval": int(os.getenv("DIAGNOSE_POLL_INTERVAL", "15")),
        "kubectl_timeout": int(os.getenv("KUBECTL_TIMEOUT", "30")),
        "api_timeout": int(os.getenv("API_TIMEOUT", "60")),
        "access_secret_key": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),
        "original_settings": Configs(vars(args)),
    }


def main() -> None:
    """Entry point for the ack-mcp-cli command."""
    if DOTENV_AVAILABLE:
        load_dotenv()

    parser = _build_global_parser()

    # Use parse_known_args so that tool-specific flags (e.g. --cluster-id)
    # are not rejected at the global level.
    args, remaining_argv = parser.parse_known_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    # Configure logging to stderr so JSON output on stdout stays clean
    logger.remove()
    logger.add(sys.stderr, level=os.getenv("FASTMCP_LOG_LEVEL", "INFO"))

    settings_dict = build_settings_dict(args)
    runner = CLIRunner(settings_dict)

    if args.subcommand == "list":
        runner.list_tools()

    elif args.subcommand == "describe":
        runner.describe_tool(args.tool_name)

    elif args.subcommand == "call":
        # Look up tool schema and parse remaining argv as tool parameters
        tool = runner._get_tool_by_name(args.tool_name)
        tool_args = parse_tool_args(
            args.tool_name,
            tool.parameters or {},
            remaining_argv,
        )
        runner.call_tool(args.tool_name, tool_args)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
