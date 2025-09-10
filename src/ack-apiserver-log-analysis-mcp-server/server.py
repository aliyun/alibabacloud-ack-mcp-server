"""Observability SLS Cluster APIServer Log Analysis MCP Server."""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .handler import ObservabilitySLSClusterAPIServerLogAnalysisHandler
from .runtime_provider import ObservabilitySLSClusterAPIServerLogAnalysisRuntimeProvider

SERVER_NAME = "ack-apiserver-log-analysis-mcp-server"
SERVER_DEPENDENCIES = ["fastmcp", "pydantic", "loguru", "aliyun-log-python-sdk"]

def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create SLS APIServer Log Analysis MCP server instance."""
    config = config or {}
    runtime_provider = ObservabilitySLSClusterAPIServerLogAnalysisRuntimeProvider(config)
    
    server = FastMCP(
        name=SERVER_NAME,
        instructions="SLS APIServer Log Analysis MCP Server",
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    allow_write = config.get("allow_write", False)
    ObservabilitySLSClusterAPIServerLogAnalysisHandler(server, allow_write, config)
    
    logger.info("SLS APIServer Log Analysis MCP Server created successfully")
    return server

def main():
    """Run SLS APIServer Log Analysis MCP server as standalone application."""
    parser = argparse.ArgumentParser(description="SLS APIServer Log Analysis MCP Server")
    parser.add_argument("--allow-write", action="store_true", default=False)
    parser.add_argument("--transport", "-t", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", "-p", type=int, default=8006)
    parser.add_argument("--region", "-r", default="cn-hangzhou")
    
    args = parser.parse_args()
    logger.remove()
    logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'INFO'))
    
    config = {
        "allow_write": args.allow_write,
        "access_key_id": os.environ.get("ACCESS_KEY_ID"),
        "access_secret_key": os.environ.get("ACCESS_SECRET_KEY"),
        "region_id": args.region,
        "default_cluster_id": os.environ.get("DEFAULT_CLUSTER_ID", ""),
    }
    
    try:
        server = create_mcp_server(config)
        if args.transport == "stdio":
            server.run()
        else:
            server.run(transport="sse", host=args.host, port=args.port)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()