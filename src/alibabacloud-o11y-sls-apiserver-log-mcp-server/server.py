"""Observability SLS Cluster APIServer Log Analysis MCP Server."""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

# 尝试导入python-dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv not available, environment variables will be read from system")

from .handler import ObservabilitySLSClusterAPIServerLogAnalysisHandler
from .runtime_provider import ObservabilitySLSClusterAPIServerLogAnalysisRuntimeProvider

SERVER_NAME = "ack-apiserver-log-analysis-mcp-server"
SERVER_INSTRUCTIONS = """
Observability SLS Cluster APIServer Log Analysis MCP Server

This server provides comprehensive SLS (Simple Log Service) APIServer log analysis capabilities:

## Available Tools:

1. **query_apiserver_logs**: Query APIServer access logs
   - Search and filter APIServer request logs
   - Analyze API request patterns and performance
   - Support time range and keyword filtering

2. **analyze_apiserver_errors**: Analyze APIServer error logs
   - Identify and categorize API errors
   - Get error statistics and trends
   - Monitor API health and performance

3. **get_apiserver_metrics**: Get APIServer metrics from logs
   - Extract performance metrics from logs
   - Analyze request latency and throughput
   - Monitor resource usage patterns

## Authentication:
Configure AlibabaCloud credentials through environment variables:
- ACCESS_KEY_ID: AlibabaCloud Access Key ID
- ACCESS_KEY_SECRET: AlibabaCloud Access Key Secret
- REGION_ID: Target region (default: cn-hangzhou)
- SLS_ENDPOINT: SLS service endpoint
- SLS_PROJECT: SLS project name
- SLS_LOGSTORE: SLS logstore name

## Usage:
This server can run standalone or be mounted as a sub-server in the main
AlibabaCloud Container Service MCP Server architecture.
"""
SERVER_DEPENDENCIES = ["fastmcp", "pydantic", "loguru", "aliyun-log-python-sdk"]

def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create SLS APIServer Log Analysis MCP server instance.
    
    Args:
        config: Server configuration dictionary containing:
               - host: Server host (default: localhost)
               - port: Server port (default: 8006)
               - Other server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract server parameters from config
    host = config.get("host", "localhost")
    port = config.get("port", 8006)
    
    runtime_provider = ObservabilitySLSClusterAPIServerLogAnalysisRuntimeProvider(config)
    
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
        host=host,
        port=port,
    )
    
    allow_write = config.get("allow_write", False)
    ObservabilitySLSClusterAPIServerLogAnalysisHandler(server, allow_write, config)
    
    logger.info(f"SLS APIServer Log Analysis MCP Server created successfully on {host}:{port}")
    return server

def main():
    """Run SLS APIServer Log Analysis MCP server as standalone application."""
    # 首先加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    else:
        logger.warning("python-dotenv not available, using system environment variables only")
    
    parser = argparse.ArgumentParser(description="SLS APIServer Log Analysis MCP Server")
    parser.add_argument("--allow-write", action="store_true", default=False, help="Enable write access mode")
    parser.add_argument("--transport", "-t", choices=["stdio", "sse"], default="stdio", help="Transport method")
    parser.add_argument("--host", default="localhost", help="Host for SSE transport")
    parser.add_argument("--port", "-p", type=int, default=8006, help="Port for SSE transport")
    parser.add_argument("--region", "-r", help="AlibabaCloud region (default: from env REGION_ID or cn-hangzhou)")
    parser.add_argument("--access-key-id", help="AlibabaCloud Access Key ID (default: from env ACCESS_KEY_ID)")
    parser.add_argument("--access-key-secret", help="AlibabaCloud Access Key Secret (default: from env ACCESS_KEY_SECRET)")
    parser.add_argument("--default-cluster-id", help="Default ACK cluster ID (default: from env DEFAULT_CLUSTER_ID)")
    parser.add_argument("--sls-endpoint", help="SLS service endpoint (default: from env SLS_ENDPOINT)")
    parser.add_argument("--sls-project", help="SLS project name (default: from env SLS_PROJECT)")
    parser.add_argument("--sls-logstore", help="SLS logstore name (default: from env SLS_LOGSTORE)")
    
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
        
        # SLS特有配置
        "sls_endpoint": args.sls_endpoint or os.getenv("SLS_ENDPOINT"),
        "sls_project": args.sls_project or os.getenv("SLS_PROJECT"),
        "sls_logstore": args.sls_logstore or os.getenv("SLS_LOGSTORE"),
        "query_timeout": int(os.getenv("QUERY_TIMEOUT", "30")),
        "max_log_lines": int(os.getenv("MAX_LOG_LINES", "1000")),
        
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
    if not config.get("sls_endpoint"):
        logger.warning("⚠️  未配置SLS_ENDPOINT，部分功能可能无法使用")
    
    logger.info(f"Starting SLS APIServer Log Analysis MCP Server (region: {config['region_id']})")
    if config.get('default_cluster_id'):
        logger.info(f"Default cluster: {config['default_cluster_id']}")
    if config.get('sls_project'):
        logger.info(f"SLS project: {config['sls_project']}")
    
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
            server.run(transport="sse")
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()