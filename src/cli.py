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

Usage:
    ack-mcp-cli list                              # List all available tools
    ack-mcp-cli call <tool_name> --args '<JSON>'  # Call a tool with JSON arguments
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict

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

    def list_tools(self) -> None:
        """Print all available tools in a human-readable table."""
        tools = asyncio.run(self.mcp.list_tools())
        if not tools:
            print("No tools registered.")
            return

        # Collect tool info
        entries = []
        for t in tools:
            name = t.name
            desc = (t.description or "").split("\n")[0].strip()
            entries.append((name, desc))

        entries.sort(key=lambda e: e[0])

        # Calculate column widths
        max_name = max(len(e[0]) for e in entries)
        col_width = max(max_name, len("Tool Name"))

        header = f"{'Tool Name':<{col_width}}  Description"
        separator = f"{'-' * col_width}  {'-' * 50}"
        print(header)
        print(separator)
        for name, desc in entries:
            print(f"{name:<{col_width}}  {desc}")

    def call_tool(self, tool_name: str, args_json: str) -> None:
        """Call a tool by name with the given JSON arguments and print the result."""
        # Parse JSON arguments
        try:
            args: Dict[str, Any] = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON arguments: {e}")
            sys.exit(1)

        if not isinstance(args, dict):
            logger.error("Arguments must be a JSON object (dict)")
            sys.exit(1)

        try:
            result = asyncio.run(self.mcp.call_tool(tool_name, args))
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            sys.exit(1)

        # Extract output from ToolResult
        self._print_result(result)

    @staticmethod
    def _print_result(result: Any) -> None:
        """Serialize and print the tool result as JSON to stdout."""
        # FastMCP ToolResult has structured_content (dict) and content (list of TextContent)
        if hasattr(result, "structured_content") and result.structured_content is not None:
            print(json.dumps(result.structured_content, indent=2, ensure_ascii=False, default=str))
        elif hasattr(result, "content") and result.content:
            # Fall back to text content
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            if len(texts) == 1:
                # Try to parse as JSON for pretty printing
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

def build_settings_dict(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the unified settings dict from CLI arguments and environment variables."""
    return {
        # Basic config
        "allow_write": args.allow_write,

        # AlibabaCloud credentials
        "region_id": args.region or os.getenv("REGION_ID", "cn-hangzhou"),
        "access_key_id": args.access_key_id or os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),

        # Kubeconfig
        "kubeconfig_mode": args.kubeconfig_mode or os.getenv("KUBECONFIG_MODE", "ACK_PUBLIC"),
        "kubeconfig_path": args.kubeconfig_path or os.getenv("KUBECONFIG_PATH", "~/.kube/config"),

        # Cache
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),

        # Timeout
        "diagnose_timeout": int(os.getenv("DIAGNOSE_TIMEOUT", "600")),
        "diagnose_poll_interval": int(os.getenv("DIAGNOSE_POLL_INTERVAL", "15")),
        "kubectl_timeout": int(os.getenv("KUBECTL_TIMEOUT", "30")),
        "api_timeout": int(os.getenv("API_TIMEOUT", "60")),

        # Compatibility
        "access_secret_key": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),
        "original_settings": Configs(vars(args)),
    }


def main() -> None:
    """Entry point for the ack-mcp-cli command."""
    # Load .env file if available
    if DOTENV_AVAILABLE:
        load_dotenv()

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
        "--region", "-r",
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
        help="Mode to obtain kubeconfig for ACK clusters (default: from env KUBECONFIG_MODE)",
    )
    parser.add_argument(
        "--kubeconfig-path",
        type=str,
        help="Path to local kubeconfig file when KUBECONFIG_MODE is LOCAL",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="%(prog)s 1.0.0",
    )

    # ---- Sub-commands ----
    subparsers = parser.add_subparsers(dest="subcommand", help="Available sub-commands")

    # list
    subparsers.add_parser("list", help="List all available tools")

    # call
    call_parser = subparsers.add_parser("call", help="Call a tool by name")
    call_parser.add_argument(
        "tool_name",
        type=str,
        help="Name of the tool to call",
    )
    call_parser.add_argument(
        "--args", "-a",
        type=str,
        default="{}",
        help="JSON string of tool arguments (default: '{}')",
    )

    args = parser.parse_args()

    # If no sub-command is given, print help and exit
    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    # Configure logging to stderr so JSON output on stdout stays clean
    logger.remove()
    logger.add(sys.stderr, level=os.getenv("FASTMCP_LOG_LEVEL", "INFO"))

    # Build settings
    settings_dict = build_settings_dict(args)

    # Execute requested sub-command
    runner = CLIRunner(settings_dict)

    if args.subcommand == "list":
        runner.list_tools()
    elif args.subcommand == "call":
        runner.call_tool(args.tool_name, args.args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
