"""Observability Aliyun CloudMonitor Resource Monitor MCP Server."""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from fastmcp import FastMCP

# 尝试导入python-dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv not available, environment variables will be read from system")

from .handler import ObservabilityAliyunCloudMonitorResourceMonitorHandler
from .runtime_provider import ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider

SERVER_NAME = "alibabacloud-ack-cloudresource-monitor-mcp-server"
SERVER_INSTRUCTIONS = """
AlibabaCloud ACK CloudMonitor Resource Monitor MCP Server

This server provides comprehensive AlibabaCloud CloudMonitor resource monitoring capabilities:

## Available Tools:

1. **describe_metric_list**: Get available metrics for resources
   - List available CloudMonitor metrics
   - Support filtering by namespace and dimensions
   - Get metric metadata and descriptions

2. **query_metric_data**: Query metric data from CloudMonitor
   - Retrieve historical metric data
   - Support time range and statistics aggregation
   - Get real-time monitoring data

## Authentication:
Configure AlibabaCloud credentials through environment variables:
- ACCESS_KEY_ID: AlibabaCloud Access Key ID
- ACCESS_KEY_SECRET: AlibabaCloud Access Key Secret
- REGION_ID: Target region (default: cn-hangzhou)

## Usage:
This server can run standalone or be mounted as a sub-server in the main
AlibabaCloud Container Service MCP Server architecture.
"""
SERVER_DEPENDENCIES = ["fastmcp", "pydantic", "loguru", "alibabacloud_cms20190101"]

def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create CloudMonitor Resource Monitor MCP server instance.
    
    Args:
        config: Server configuration dictionary containing:
               - host: Server host (default: localhost)
               - port: Server port (default: 8007)
               - Other server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract server parameters from config
    host = config.get("host", "localhost")
    port = config.get("port", 8009)
    
    runtime_provider = ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider(config)
    
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Store host and port for potential standalone usage
    server._host = host
    server._port = port
    
    allow_write = config.get("allow_write", False)
    ObservabilityAliyunCloudMonitorResourceMonitorHandler(server, allow_write, config)
    
    logger.info(f"CloudMonitor Resource Monitor MCP Server created successfully on {host}:{port}")
    return server

def main():
    """Run CloudMonitor Resource Monitor MCP server as standalone application."""
    # 首先加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    else:
        logger.warning("python-dotenv not available, using system environment variables only")
    
    parser = argparse.ArgumentParser(description="CloudMonitor Resource Monitor MCP Server")
    parser.add_argument("--allow-write", action="store_true", default=False, help="Enable write access mode")
    parser.add_argument("--transport", "-t", choices=["stdio", "sse"], default="stdio", help="Transport method")
    parser.add_argument("--host", default="localhost", help="Host for SSE transport")
    parser.add_argument("--port", "-p", type=int, default=8009, help="Port for SSE transport")
    parser.add_argument("--region", "-r", help="AlibabaCloud region (default: from env REGION_ID or cn-hangzhou)")
    parser.add_argument("--access-key-id", help="AlibabaCloud Access Key ID (default: from env ACCESS_KEY_ID)")
    parser.add_argument("--access-key-secret", help="AlibabaCloud Access Key Secret (default: from env ACCESS_KEY_SECRET)")
    parser.add_argument("--default-cluster-id", help="Default ACK cluster ID (default: from env DEFAULT_CLUSTER_ID)")
    
    args = parser.parse_args()
    logger.remove()
    logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'INFO'))
    
    # 构建完整的配置字典
    config = {
        # 基本配置
        "allow_write": args.allow_write,
        "transport": args.transport,
        "host": args.host,
        "port": args.port,
        
        # 阿里云认证配置
        "region_id": args.region or os.getenv("REGION_ID", "cn-hangzhou"),
        "access_key_id": args.access_key_id or os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),
        "default_cluster_id": args.default_cluster_id or os.getenv("DEFAULT_CLUSTER_ID", ""),
        
        # CloudMonitor特有配置
        "metric_query_timeout": int(os.getenv("METRIC_QUERY_TIMEOUT", "30")),
        "max_data_points": int(os.getenv("MAX_DATA_POINTS", "1000")),
        
        # 额外的环境配置
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
        "fastmcp_log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
        "development": os.getenv("DEVELOPMENT", "false").lower() == "true",
    }
    
    # 验证必要的配置
    if not config.get("access_key_id"):
        logger.warning("⚠️  未配置ACCESS_KEY_ID，部分功能可能无法使用")
    if not config.get("access_key_secret"):
        logger.warning("⚠️  未配置ACCESS_KEY_SECRET，部分功能可能无法使用")
    
    logger.info(f"Starting CloudMonitor Resource Monitor MCP Server (region: {config['region_id']})")
    if config.get('default_cluster_id'):
        logger.info(f"Default cluster: {config['default_cluster_id']}")
    
    # 记录敏感信息（隐藏部分内容）
    if config.get('access_key_id'):
        logger.info(f"Access Key ID: {config['access_key_id'][:8]}***")
    
    try:
        # Create and run server with full config
        server = create_mcp_server(config)
        if args.transport == "stdio":
            logger.info("Starting stdio server...")
            server.run()
        else:
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