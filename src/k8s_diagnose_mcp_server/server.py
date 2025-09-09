"""K8s Diagnose MCP Server.

This server provides Kubernetes diagnosis capabilities including:
- Diagnose cluster health
- Diagnose pod issues  
- Diagnose network connectivity
"""

import argparse
import os
import sys
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .handler import K8sDiagnoseHandler
from .runtime_provider import K8sDiagnoseRuntimeProvider

# Server configuration
SERVER_NAME = "k8s-diagnose-mcp-server"
SERVER_INSTRUCTIONS = """
K8s Diagnose MCP Server

This server provides comprehensive Kubernetes cluster diagnosis capabilities:

## Available Tools:

1. **diagnose_cluster_health**: Diagnose overall cluster health
   - Check node status and availability
   - Verify core system components
   - Analyze resource utilization and capacity

2. **diagnose_pod_issues**: Diagnose pod-related issues  
   - Identify pod scheduling problems
   - Check resource constraints and limits
   - Analyze container startup and runtime issues

3. **diagnose_network_connectivity**: Diagnose network connectivity issues
   - Test pod-to-pod communication
   - Verify service discovery and DNS resolution
   - Check ingress and load balancer connectivity

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
]


def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create K8s Diagnose MCP server instance.
    
    Args:
        config: Server configuration dictionary
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Create runtime provider
    runtime_provider = K8sDiagnoseRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    K8sDiagnoseHandler(server, allow_write, config)
    
    logger.info("K8s Diagnose MCP Server created successfully")
    return server


def main():
    """Run K8s Diagnose MCP server as standalone application."""
    parser = argparse.ArgumentParser(
        description="K8s Diagnose MCP Server"
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
        default=8003,
        help="Port for SSE transport (default: 8003)"
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
    
    logger.info(f"Starting K8s Diagnose MCP Server (kubeconfig: {args.kubeconfig})")
    
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