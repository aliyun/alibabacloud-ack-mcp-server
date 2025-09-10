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

# 尝试导入python-dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv not available, environment variables will be read from system")

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

5. **ACK Diagnostics** (/ack-diagnose):
   - Cluster health diagnosis
   - Pod issue diagnosis  
   - Network connectivity diagnosis

6. **AlibabaCloud ACK Prometheus** (/observability-prometheus):
   - Execute PromQL queries
   - Natural language to PromQL translation
   - Get available metrics

7. **ACK APIServer Log Analysis** (/observability-sls):
   - Execute SLS SQL queries
   - Natural language to SLS SQL translation
   - APIServer error analysis

8. **AlibabaCloud ACK CloudResource Monitor** (/observability-cloudmonitor):
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
    "ack-diagnose-mcp-server": {
        "prefix": "ack-diagnose", 
        "module_name": "ack_diagnose_mcp_server",
        "create_function": "create_mcp_server"
    },
    "alibabacloud-o11y-prometheus-mcp-server": {
        "prefix": "observability-prometheus",
        "module_name": "alibabacloud_o11y_prometheus_mcp_server",
        "create_function": "create_mcp_server"
    },
    "alibabacloud-o11y-sls-apiserver-log-mcp-server": {
        "prefix": "observability-sls",
        "module_name": "alibabacloud_o11y_sls_apiserver_log_mcp_server", 
        "create_function": "create_mcp_server"
    },
    "alibabacloud-ack-cloudresource-monitor-mcp-server": {
        "prefix": "observability-cloudmonitor",
        "module_name": "alibabacloud_ack_cloudresource_monitor_mcp_server",
        "create_function": "create_mcp_server"
    },
    "alibabacloud-o11y-sls-audit-log-analysis-mcp-server": {
        "prefix": "audit-log",
        "module_name": "alibabacloud_o11y_sls_audit_log_analysis_mcp_server",
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
            module_name = config["module_name"]
            
            # For modules with hyphens in directory names, use spec_from_file_location
            if '-' in server_name:
                import importlib.util
                import sys
                import os
                
                # Add src directory to Python path if not already there
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                
                module_path = f"{server_name}/__init__.py"
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                
                # Add module to sys.modules to support relative imports
                sys.modules[module_name] = module
                
                # Execute the module
                spec.loader.exec_module(module)
            else:
                module = importlib.import_module(module_name)
            
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
    # 加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    
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
        "--region",
        "-r",
        type=str,
        help="AlibabaCloud region (default: from env REGION_ID or cn-hangzhou)"
    )
    parser.add_argument(
        "--access-key-id",
        type=str,
        help="AlibabaCloud Access Key ID (default: from env ACCESS_KEY_ID)"
    )
    parser.add_argument(
        "--access-key-secret",
        type=str,
        help="AlibabaCloud Access Key Secret (default: from env ACCESS_KEY_SECRET)"
    )
    parser.add_argument(
        "--default-cluster-id",
        type=str,
        help="Default ACK cluster ID (default: from env DEFAULT_CLUSTER_ID)"
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
    
    # 构建完整的配置字典，优先级：命令行参数 > 环境变量 > 默认值
    settings_dict = {
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
        
        # 审计日志配置
        "audit_config_path": args.audit_config,
        "audit_config_dict": None,
        
        # 额外的环境配置
        "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
        "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
        "fastmcp_log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
        "development": os.getenv("DEVELOPMENT", "false").lower() == "true",
        
        # 兼容性配置
        "access_secret_key": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),  # 兼容旧字段名
        "original_settings": Configs(vars(args)),
    }
    
    # 验证必要的配置
    if not settings_dict.get("access_key_id"):
        logger.warning("⚠️  未配置ACCESS_KEY_ID，部分功能可能无法使用")
    if not settings_dict.get("access_key_secret"):
        logger.warning("⚠️  未配置ACCESS_KEY_SECRET，部分功能可能无法使用")

    # Log startup info with configuration
    mode_info = []
    if not args.allow_write:
        mode_info.append("read-only mode")
    if args.audit_config:
        mode_info.append("audit log enabled")

    mode_str = " in " + ", ".join(mode_info) if mode_info else ""
    logger.info(f"Starting AlibabaCloud Container Service Main MCP Server{mode_str}")
    logger.info(f"Region: {settings_dict['region_id']}")
    if settings_dict.get('default_cluster_id'):
        logger.info(f"Default Cluster: {settings_dict['default_cluster_id']}")
    
    # 记录敏感信息（隐藏部分内容）
    if settings_dict.get('access_key_id'):
        logger.info(f"Access Key ID: {settings_dict['access_key_id'][:8]}***")

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