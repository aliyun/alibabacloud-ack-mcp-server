"""Kubernetes Client MCP Server.

This server provides Kubernetes client capabilities including:
- Get/List/Create/Delete/Patch K8s resources
- Get pod logs and events
- Describe resources in detail
"""

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

from .handler import KubernetesClientHandler
from .runtime_provider import KubernetesClientRuntimeProvider

# Server configuration
SERVER_NAME = "kubernetes-client-mcp-server"
SERVER_INSTRUCTIONS = """
Kubernetes Client MCP Server

This server provides comprehensive Kubernetes API client capabilities:

## Available Tools:

1. **k8s_resource_get_yaml**: Get resource YAML definition
   - Retrieve YAML manifests for any Kubernetes resource
   - Support all resource types (pods, services, deployments, etc.)
   - Include metadata and spec details

2. **k8s_resource_list**: List Kubernetes resources
   - List resources by type and namespace
   - Support filtering and labeling
   - Get resource summaries and status

3. **k8s_resource_create**: Create Kubernetes resources
   - Create resources from YAML manifests
   - Validate resource specifications
   - Support dry-run mode

4. **k8s_resource_delete**: Delete Kubernetes resources
   - Delete specific resources by name
   - Support cascade deletion options
   - Graceful termination handling

5. **k8s_resource_patch**: Patch/update Kubernetes resources
   - Update resource configurations
   - Support strategic merge patches
   - Modify resource specifications

6. **k8s_pod_logs**: Get pod logs
   - Retrieve container logs from pods
   - Support multi-container pods
   - Follow log streams and tail options

7. **k8s_events_get**: Get Kubernetes events
   - Retrieve cluster events and notifications
   - Filter by resource type and namespace
   - Get event history and details

8. **k8s_resource_describe**: Describe resources in detail
   - Get comprehensive resource descriptions
   - Include related events and status
   - Show resource relationships

## Authentication:
Configure environment variables:
- KUBECONFIG: Path to kubeconfig file (default: ~/.kube/config)

## Usage:
This server can run standalone or be mounted as a sub-server in the main
AlibabaCloud Container Service MCP Server architecture.
"""

SERVER_DEPENDENCIES = [
    "fastmcp",
    "pydantic",
    "loguru", 
    "kubernetes",  # Kubernetes Python client
    "pyyaml",     # YAML parsing
]


def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create Kubernetes Client MCP server instance.
    
    Args:
        config: Server configuration dictionary containing:
               - host: Server host (default: localhost)
               - port: Server port (default: 8004)
               - Other server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract server parameters from config
    host = config.get("host", "localhost")
    port = config.get("port", 8004)
    
    # Create runtime provider
    runtime_provider = KubernetesClientRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Store host and port for potential standalone usage
    server._host = host
    server._port = port
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    KubernetesClientHandler(server, allow_write, config)
    
    logger.info(f"Kubernetes Client MCP Server created successfully on {host}:{port}")
    return server


def main():
    """Run Kubernetes Client MCP server as standalone application."""
    # 首先加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    else:
        logger.warning("python-dotenv not available, using system environment variables only")
    
    parser = argparse.ArgumentParser(
        description="Kubernetes Client MCP Server"
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
        default=8004,
        help="Port for SSE transport (default: 8004)"
    )
    parser.add_argument(
        "--kubeconfig",
        "-k",
        type=str,
        help="Path to kubeconfig file (default: from env KUBECONFIG or ~/.kube/config)"
    )
    parser.add_argument(
        "--default-cluster-id",
        type=str,
        help="Default ACK cluster ID (default: from env DEFAULT_CLUSTER_ID)"
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
    
    # 构建完整的配置字典，优先级：命令行参数 > 环境变量 > 默认值
    config = {
        # 基本配置
        "allow_write": args.allow_write,
        "transport": args.transport,
        "host": args.host,
        "port": args.port,
        
        # Kubernetes配置
        "kubeconfig_path": args.kubeconfig or os.getenv("KUBECONFIG", "~/.kube/config"),
        "default_cluster_id": args.default_cluster_id or os.getenv("DEFAULT_CLUSTER_ID", ""),
        
        # 可选的阿里云配置（为了保持一致性）
        "access_key_id": os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": os.getenv("ACCESS_KEY_SECRET"),
        "region_id": os.getenv("REGION_ID", "cn-hangzhou"),
        
        # Kubernetes Client特有配置
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
        "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "max_log_lines": int(os.getenv("MAX_LOG_LINES", "1000")),
        "follow_logs": os.getenv("FOLLOW_LOGS", "false").lower() == "true",
        
        # 额外的环境配置
        "fastmcp_log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
        "development": os.getenv("DEVELOPMENT", "false").lower() == "true",
    }
    
    # 验证kubeconfig文件存在
    kubeconfig_path = os.path.expanduser(config["kubeconfig_path"])
    if not os.path.exists(kubeconfig_path):
        logger.warning(f"⚠️  Kubeconfig文件不存在: {kubeconfig_path}")
        logger.warning("⚠️  请确保正确配置KUBECONFIG环境变量或传入--kubeconfig参数")
    
    logger.info(f"Starting Kubernetes Client MCP Server (kubeconfig: {config['kubeconfig_path']})")
    if config.get('default_cluster_id'):
        logger.info(f"Default cluster: {config['default_cluster_id']}")
    
    try:
        # Create and run server with full config
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