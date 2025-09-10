"""AlibabaCloud ACK Cluster Audit Log Analysis MCP Server - Main server implementation."""

import argparse
import sys
import os
import asyncio
from pathlib import Path
from typing import Optional, Literal

from fastmcp import FastMCP

from .context.lifespan_manager import KubeAuditRuntimeProvider
from .toolkits.kube_aduit_tool import KubeAuditTool


def create_mcp_server(config: Optional[dict] = None) -> FastMCP:
    """Create MCP server instance for proxy mounting.
    
    Args:
        config: Server configuration dictionary containing:
               - audit_config_path: Path to audit configuration file
               - audit_config_dict: Audit configuration dictionary
               - Other standard MCP server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract audit configuration from config dict
    audit_config_path = config.get("audit_config_path")
    audit_config_dict = config.get("audit_config_dict")
    
    # Extract transport settings from config if available
    transport = config.get("transport", "stdio")
    host = config.get("host", "127.0.0.1")
    port = config.get("port", 8000)
    
    # Use the existing create_server function
    return create_server(
        config_path=audit_config_path,
        config_dict=audit_config_dict,
        transport=transport,
        host=host,
        port=port,
    )


def create_server(
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        transport: Literal["stdio", "sse"] = "stdio",
        host: str = "127.0.0.1",
        port: int = 8000
) -> FastMCP:
    """Create and configure the MCP server.
    
    Args:
        config_path: Path to configuration file
        config_dict: Configuration dictionary
        transport: Transport method ("stdio" or "sse")
        host: Host for SSE transport
        port: Port for SSE transport
        
    Returns:
        Configured FastMCP server instance
    """
    # Initialize lifespan manager
    if config_path:
        lifespan_manager = KubeAuditRuntimeProvider(config_path=config_path)
    elif config_dict:
        lifespan_manager = KubeAuditRuntimeProvider(config=config_dict)
    else:
        # Try to find default config file
        default_config_path = Path(__file__).parent / "config.yaml"
        if default_config_path.exists():
            lifespan_manager = KubeAuditRuntimeProvider(config_path=str(default_config_path))
        else:
            raise FileNotFoundError("No configuration file found!")

    # Create MCP server
    mcp = FastMCP(
        "ack-cluster-audit-log-analysis-mcp-server",
        lifespan=lifespan_manager.init_runtime,
        host=host,
        port=port
    )

    # Initialize and register tools
    KubeAuditTool(server=mcp)

    # Store transport type for later use
    mcp._transport_type = transport

    return mcp


def run_server(
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        transport: Literal["stdio", "sse"] = "stdio",
        host: str = "localhost",
        port: int = 8000
):
    """Run the MCP server with specified transport.
    
    Args:
        config_path: Path to configuration file
        config_dict: Configuration dictionary
        transport: Transport method ("stdio" or "sse")
        host: Host for SSE transport
        port: Port for SSE transport
    """
    server = create_server(
        config_path=config_path,
        config_dict=config_dict,
        transport=transport,
        host=host,
        port=port
    )

    print(f"Starting AlibabaCloud ACK MCP Server with {transport} transport...")

    try:
        if transport == "stdio":
            # Use stdio transport - FastMCP handles this automatically
            print("Starting stdio server...")
            server.run()
        elif transport == "sse":
            print(f"Server will be available at http://{host}:{port}")
            server.run(transport="sse")
    except KeyboardInterrupt:
        print("\nReceived shutdown signal...")
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}")
        raise


def main():
    """Main entry point for the server."""
    parser = argparse.ArgumentParser(
        description="AlibabaCloud ACK Cluster Audit Log Analysis MCP Server"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file (YAML format)"
    )
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport method (default: stdio)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host for SSE transport (default: localhost)"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s 0.1.0"
    )

    args = parser.parse_args()

    try:
        # Run server with specified transport
        run_server(
            config_path=args.config,
            transport=args.transport,
            host=args.host,
            port=args.port
        )

    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


# For backward compatibility and direct execution
if __name__ == "__main__":
    main()
