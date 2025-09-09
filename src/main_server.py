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

"""Main MCP Server with FastMCP Proxy Mount Architecture.

This is the main entry point for the AlibabaCloud Container Service MCP Server.
It implements a microservices architecture using FastMCP proxy mount mechanism
to connect various sub-MCP servers.
"""

import argparse
import os
import sys
import importlib
from typing import Dict, Any, Optional, Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from config import Configs, get_settings

# Define main server configuration
MAIN_SERVER_NAME = "alibabacloud-cs-main-server"
MAIN_SERVER_INSTRUCTIONS = """
AlibabaCloud Container Service Main MCP Server

This is the main MCP server that orchestrates multiple specialized sub-MCP servers
through FastMCP proxy mount mechanism. It provides comprehensive Kubernetes 
cluster management capabilities:

## Available Sub-Services:

1. **ACK Cluster Management** (/ack-cluster): 
   - Cluster task status queries
   - Cluster diagnostics creation and results

2. **ACK Addon Management** (/ack-addon):
   - List cluster addons
   - Install/uninstall cluster addons

3. **ACK NodePool Management** (/ack-nodepool):
   - Scale node pools
   - Remove nodes from node pools

4. **Kubernetes Client** (/kubernetes): 
   - Get/List/Create/Delete/Patch K8s resources
   - Get pod logs and events
   - Describe resources in detail

5. **K8s Diagnostics** (/k8s-diagnose):
   - Cluster health diagnosis
   - Pod issue diagnosis  
   - Network connectivity diagnosis

6. **Observability - Prometheus** (/observability-prometheus):
   - Execute PromQL queries
   - Natural language to PromQL translation
   - Get available metrics

7. **Observability - SLS APIServer** (/observability-sls):
   - Execute SLS SQL queries
   - Natural language to SLS SQL translation
   - APIServer error analysis

8. **Observability - CloudMonitor** (/observability-cloudmonitor):
   - Get resource metrics
   - Create alert rules
   - Monitor resource health status

9. **Audit Log Querying** (/audit-log):
   - Query Kubernetes audit logs from SLS
   - Filter by namespace, resource type, user, time range
   - Support wildcard patterns and multiple value filters

Each sub-service is implemented as an independent MCP server that can also
run standalone. The main server coordinates these services and provides
a unified interface for comprehensive Kubernetes operations.

Use this server to streamline your Kubernetes operations and monitoring workflows.
"""

MAIN_SERVER_DEPENDENCIES = [
    "fastmcp",
    "pydantic", 
    "loguru",
    "kubernetes",
    "requests",
    "pyyaml",
    "cachetools",
    "aliyun-log-python-sdk",
    "pydantic-settings",
]

# Sub-server configuration mapping
SUB_SERVERS_CONFIG = {
    "ack-cluster-management-mcp-server": {
        "prefix": "ack-cluster",
        "module_name": "ack-cluster-management-mcp-server",
        "create_function": "create_mcp_server"
    },
    "ack-addon-management-mcp-server": {
        "prefix": "ack-addon", 
        "module_name": "ack-addon-management-mcp-server",
        "create_function": "create_mcp_server"
    },
    "ack-nodepool-management-mcp-server": {
        "prefix": "ack-nodepool",
        "module_name": "ack-nodepool-management-mcp-server", 
        "create_function": "create_mcp_server"
    },
    "kubernetes-client-mcp-server": {
        "prefix": "kubernetes",
        "module_name": "kubernetes_client_mcp_server",
        "create_function": "create_mcp_server"
    },
    "k8s-diagnose-mcp-server": {
        "prefix": "k8s-diagnose", 
        "module_name": "k8s_diagnose_mcp_server",
        "create_function": "create_mcp_server"
    },
    "observability-aliyun-prometheus-mcp-server": {
        "prefix": "observability-prometheus",
        "module_name": "observability_aliyun_prometheus_mcp_server",
        "create_function": "create_mcp_server"
    },
    "observability-sls-cluster-apiserver-log-analysis-mcp-server": {
        "prefix": "observability-sls",
        "module_name": "observability_sls_cluster_apiserver_log_analysis_mcp_server", 
        "create_function": "create_mcp_server"
    },
    "observability-aliyun-cloudmonitor-resource-monitor-mcp-server": {
        "prefix": "observability-cloudmonitor",
        "module_name": "observability_aliyun_cloudmonitor_resource_monitor_mcp_server",
        "create_function": "create_mcp_server"
    },
    "alibabacloud-cluster-audit-log-mcp-server": {
        "prefix": "audit-log",
        "module_name": "alibabacloud_cluster_audit_log_mcp_server",
        "create_function": "create_mcp_server"
    }
}


def create_main_server(
    settings_dict: Optional[Dict[str, Any]] = None,
    transport: Literal["stdio", "sse"] = "stdio",
    host: str = "127.0.0.1", 
    port: int = 8000,
) -> FastMCP:
    """Create and configure the main MCP server instance with proxy mounts.
    
    Args:
        settings_dict: Main server settings for sub-servers
        transport: Transport method ("stdio" or "sse")
        host: Host for SSE transport
        port: Port for SSE transport
        
    Returns:
        Configured main FastMCP server instance with mounted sub-servers
    """
    # Create main MCP server
    main_mcp = FastMCP(
        name=MAIN_SERVER_NAME,
        instructions=MAIN_SERVER_INSTRUCTIONS, 
        dependencies=MAIN_SERVER_DEPENDENCIES,
        host=host,
        port=port,
    )
    
    # Store transport type for later use
    main_mcp._transport_type = transport
    
    # Mount sub-MCP servers using proxy mount mechanism
    mounted_servers = []
    failed_mounts = []
    
    for server_name, config in SUB_SERVERS_CONFIG.items():
        try:
            # Import the sub-server module using importlib
            if '-' in config["module_name"]:
                # Handle modules with hyphens in their names
                module = importlib.import_module(config["module_name"].replace('-', '_'))
            else:
                module = importlib.import_module(config["module_name"])
            
            create_function = getattr(module, config["create_function"])
            
            # Create sub-server instance with shared settings
            sub_server = create_function(settings_dict or {})
            
            # Mount sub-server with proxy
            main_mcp.mount(
                sub_server, 
                prefix=config["prefix"], 
                as_proxy=True
            )
            
            mounted_servers.append(f"{server_name} -> /{config['prefix']}")
            logger.info(f"Successfully mounted {server_name} at /{config['prefix']}")
            
        except Exception as e:
            failed_mounts.append(f"{server_name}: {str(e)}")
            logger.warning(f"Failed to mount {server_name}: {e}")
    
    # Log mount summary
    if mounted_servers:
        logger.info(f"Successfully mounted {len(mounted_servers)} sub-servers:")
        for mount_info in mounted_servers:
            logger.info(f"  - {mount_info}")
    
    if failed_mounts:
        logger.warning(f"Failed to mount {len(failed_mounts)} sub-servers:")
        for fail_info in failed_mounts:
            logger.warning(f"  - {fail_info}")
    
    return main_mcp


def main():
    """Run the main MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(
        description="AlibabaCloud Container Service Main MCP Server with Microservices Architecture"
    )
    parser.add_argument(
        "--allow-write",
        action=argparse.BooleanOptionalAction,
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
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    parser.add_argument(
        "--audit-config",
        "-c",
        type=str,
        help="Path to audit log configuration file (YAML format)"
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
    
    # Prepare settings for sub-servers
    settings_dict = {
        "allow_write": args.allow_write,
        "audit_config_path": args.audit_config,
        "audit_config_dict": None,  # Could be populated from other sources
        "access_key_id": os.environ.get("ACCESS_KEY_ID"),
        "access_secret_key": os.environ.get("ACCESS_SECRET_KEY"), 
        "region_id": os.environ.get("REGION_ID", "us-east-1"),
        "original_settings": Configs(vars(args)),
    }

    # Log startup mode
    mode_info = []
    if not args.allow_write:
        mode_info.append("read-only mode")
    if args.audit_config:
        mode_info.append("audit log enabled")

    mode_str = " in " + ", ".join(mode_info) if mode_info else ""
    logger.info(f"Starting AlibabaCloud Container Service Main MCP Server{mode_str}")

    try:
        # Create the main MCP server with proxy mounts
        main_server = create_main_server(
            settings_dict=settings_dict,
            transport=args.transport,
            host=args.host,
            port=args.port,
        )

        # Run server with specified transport
        logger.info(f"Starting main server with {args.transport} transport...")
        if args.transport == "stdio":
            logger.info("Starting stdio server...")
            main_server.run()
        elif args.transport == "sse":
            logger.info(f"Server will be available at http://{args.host}:{args.port}")
            main_server.run(transport="sse")
    
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Main server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()