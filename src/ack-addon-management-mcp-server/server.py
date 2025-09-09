"""ACK Addon Management MCP Server.

This server provides ACK addon management capabilities including:
- List available cluster addons
- Install cluster addons  
- Uninstall cluster addons
"""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .handler import ACKAddonManagementHandler
from .runtime_provider import ACKAddonManagementRuntimeProvider

# Server configuration
SERVER_NAME = "ack-addon-management-mcp-server"
SERVER_INSTRUCTIONS = """
ACK Addon Management MCP Server

This server provides comprehensive ACK (AlibabaCloud Container Service for Kubernetes) 
addon management capabilities:

## Available Tools:

1. **list_cluster_addons**: List available addons for ACK cluster
   - Get comprehensive list of available cluster addons
   - Check addon status and versions

2. **install_cluster_addon**: Install addon to ACK cluster  
   - Install specific addons to target clusters
   - Configure addon parameters during installation
   - Support version specification

3. **uninstall_cluster_addon**: Uninstall addon from ACK cluster
   - Remove addons from target clusters
   - Clean up addon resources and configurations

## Authentication:
Configure environment variables:
- ACCESS_KEY_ID: Your AlibabaCloud Access Key ID
- ACCESS_SECRET_KEY: Your AlibabaCloud Access Secret Key  
- REGION_ID: Target region (default: cn-hangzhou)

## Usage:
This server can run standalone or be mounted as a sub-server in the main
AlibabaCloud Container Service MCP Server architecture.
"""

SERVER_DEPENDENCIES = [
    "fastmcp",
    "pydantic",
    "loguru", 
    "alibabacloud_cs20151215",  # Container Service SDK
]


def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create ACK Addon Management MCP server instance.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Create runtime provider
    runtime_provider = ACKAddonManagementRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    ACKAddonManagementHandler(server, allow_write, config)
    
    logger.info("ACK Addon Management MCP Server created successfully")
    return server


def main():
    """Run ACK Addon Management MCP server as standalone application."""
    parser = argparse.ArgumentParser(
        description="ACK Addon Management MCP Server"
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        default=False,
        help="Enable write access mode (allow mutating operations)",
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
        default=8001,
        help="Port for SSE transport (default: 8001)"
    )
    parser.add_argument(
        "--region",
        "-r",
        type=str,
        default="cn-hangzhou",
        help="AlibabaCloud region (default: cn-hangzhou)"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'INFO'))
    
    # Prepare server configuration
    config = {
        "allow_write": args.allow_write,
        "access_key_id": os.environ.get("ACCESS_KEY_ID"),
        "access_secret_key": os.environ.get("ACCESS_SECRET_KEY"),
        "region_id": args.region,
        "default_cluster_id": os.environ.get("DEFAULT_CLUSTER_ID", ""),
    }
    
    # Validate credentials
    if not config["access_key_id"] or not config["access_secret_key"]:
        logger.warning("ACCESS_KEY_ID and ACCESS_SECRET_KEY environment variables not set")
        logger.warning("Server will run in mock mode")
    
    logger.info(f"Starting ACK Addon Management MCP Server (region: {args.region})")
    
    try:
        # Create and run server
        server = create_mcp_server(config)
        
        if args.transport == "stdio":
            logger.info("Starting stdio server...")
            server.run()
        elif args.transport == "sse":
            logger.info(f"Server will be available at http://{args.host}:{args.port}")
            server.run(transport="sse", host=args.host, port=args.port)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()