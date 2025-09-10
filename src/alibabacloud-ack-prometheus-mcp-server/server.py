"""Observability Aliyun Prometheus MCP Server.

This server provides Aliyun Prometheus observability capabilities including:
- Execute PromQL queries
- Natural language to PromQL translation
- Get available metrics
"""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .handler import ObservabilityAliyunPrometheusHandler
from .runtime_provider import ObservabilityAliyunPrometheusRuntimeProvider

# Server configuration
SERVER_NAME = "alibabacloud-ack-prometheus-mcp-server"
SERVER_INSTRUCTIONS = """
Observability Aliyun Prometheus MCP Server

This server provides comprehensive Aliyun Prometheus observability capabilities:

## Available Tools:

1. **cms_execute_promql_query**: Execute PromQL queries in Aliyun Prometheus
   - Execute complex PromQL queries for metrics analysis
   - Support time range and step interval queries
   - Get historical and real-time metrics data

2. **cms_translate_text_to_promql**: Translate natural language to PromQL query
   - Convert natural language descriptions to PromQL
   - Intelligent query generation based on context
   - Support common monitoring scenarios

3. **get_prometheus_metrics**: Get available Prometheus metrics
   - List all available metrics in the system
   - Filter metrics by pattern or category
   - Get metric metadata and descriptions

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
    "alibabacloud_cms20190101",  # CloudMonitor SDK
]


def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create Observability Aliyun Prometheus MCP server instance.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Create runtime provider
    runtime_provider = ObservabilityAliyunPrometheusRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    ObservabilityAliyunPrometheusHandler(server, allow_write, config)
    
    logger.info("Observability Aliyun Prometheus MCP Server created successfully")
    return server


def main():
    """Run Observability Aliyun Prometheus MCP server as standalone application."""
    parser = argparse.ArgumentParser(
        description="Observability Aliyun Prometheus MCP Server"
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
        default=8005,
        help="Port for SSE transport (default: 8005)"
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
        "query_timeout": int(os.environ.get("QUERY_TIMEOUT", "30")),
        "max_series": int(os.environ.get("MAX_SERIES", "10000")),
    }
    
    # Validate credentials
    if not config["access_key_id"] or not config["access_secret_key"]:
        logger.warning("ACCESS_KEY_ID and ACCESS_SECRET_KEY environment variables not set")
        logger.warning("Server will run in mock mode")
    
    logger.info(f"Starting Observability Aliyun Prometheus MCP Server (region: {args.region})")
    
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