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
from mcp.server.fastmcp import FastMCP

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
        config: Server configuration dictionary
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Create runtime provider
    runtime_provider = KubernetesClientRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    KubernetesClientHandler(server, allow_write, config)
    
    logger.info("Kubernetes Client MCP Server created successfully")
    return server


def main():
    """Run Kubernetes Client MCP server as standalone application."""
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
        default="~/.kube/config",
        help="Path to kubeconfig file (default: ~/.kube/config)"
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
        "kubeconfig_path": args.kubeconfig,
        "default_cluster_id": os.environ.get("DEFAULT_CLUSTER_ID", ""),
        "cache_ttl": int(os.environ.get("CACHE_TTL", "300")),
        "cache_max_size": int(os.environ.get("CACHE_MAX_SIZE", "1000")),
    }
    
    logger.info(f"Starting Kubernetes Client MCP Server (kubeconfig: {args.kubeconfig})")
    
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