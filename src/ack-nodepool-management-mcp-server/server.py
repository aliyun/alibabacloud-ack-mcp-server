"""ACK NodePool Management MCP Server.

This server provides ACK nodepool management capabilities including:
- Scale node pools
- Remove nodes from node pools
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
    from typing import Any
    # 定义一个空的load_dotenv函数
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return True
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv not available, environment variables will be read from system")

# 支持相对导入和绝对导入
try:
    from .handler import ACKNodePoolManagementHandler
    from .runtime_provider import ACKNodePoolManagementRuntimeProvider
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from handler import ACKNodePoolManagementHandler
    from runtime_provider import ACKNodePoolManagementRuntimeProvider

# Server configuration
SERVER_NAME = "ack-nodepool-management-mcp-server"
SERVER_INSTRUCTIONS = """
ACK NodePool Management MCP Server

This server provides comprehensive ACK (AlibabaCloud Container Service for Kubernetes) 
nodepool management capabilities:

## Available Tools:

### Node Pool Query Operations:
1. **describe_cluster_node_pools**: List and query ACK cluster node pools
   - List all node pools in a cluster
   - Filter by node pool name
   - Get basic information about node pools

2. **describe_cluster_node_pool_detail**: Get detailed information of a specific node pool
   - Get comprehensive node pool configuration
   - View scaling group details
   - Check node pool status and health

### Node Pool Lifecycle Management:
3. **create_cluster_node_pool**: Create a new node pool in ACK cluster
   - Create node pools with custom configurations
   - Set instance types, sizes, and networking
   - Configure auto-scaling parameters

4. **delete_cluster_nodepool**: Delete a node pool from ACK cluster
   - Safely remove node pools from clusters
   - Handle graceful termination of nodes
   - Clean up associated resources

5. **modify_cluster_node_pool**: Modify node pool configuration
   - Update node pool settings
   - Change scaling configurations
   - Modify node pool metadata

### Node Pool Scaling Operations:
6. **scale_nodepool**: Scale ACK cluster node pool
   - Increase or decrease the number of nodes
   - Support manual scaling operations
   - Set desired node count

7. **remove_nodepool_nodes**: Remove nodes from ACK cluster node pool
   - Safely drain and remove specific nodes
   - Maintain cluster stability during removal
   - Support graceful node termination

### Node Pool Configuration:
8. **modify_nodepool_node_config**: Modify node pool node configuration
   - Update kubelet configurations
   - Modify OS-level settings
   - Configure container runtime parameters

9. **upgrade_cluster_nodepool**: Upgrade node pool Kubernetes version
   - Upgrade Kubernetes version on nodes
   - Update node images
   - Manage rolling upgrades

### Security and Maintenance:
10. **describe_nodepool_vuls**: Query node pool security vulnerabilities
    - Scan for security vulnerabilities in nodes
    - Filter by vulnerability severity
    - Get detailed vulnerability reports

11. **fix_nodepool_vuls**: Fix node pool security vulnerabilities
    - Apply security patches to nodes
    - Configure parallel patching
    - Handle automatic restarts

12. **repair_cluster_node_pool**: Repair cluster node pool nodes
    - Perform maintenance operations on nodes
    - Execute repair scripts
    - Handle node health issues

### Advanced Operations:
13. **sync_cluster_node_pool**: Sync cluster node pool configuration
    - Synchronize node pool state
    - Reconcile configuration drift
    - Ensure consistency across nodes

14. **attach_instances_to_node_pool**: Attach existing instances to node pool
    - Add existing ECS instances to node pools
    - Configure instance joining settings
    - Handle disk formatting options

15. **create_autoscaling_config**: Create autoscaling configuration for cluster
    - Configure cluster autoscaler settings
    - Set scaling thresholds and policies
    - Define resource utilization targets

16. **describe_cluster_attach_scripts**: Get scripts for attaching existing nodes to cluster node pool
    - Generate scripts for manual node joining
    - Support different architectures
    - Provide customizable options

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
    """Create ACK NodePool Management MCP server instance.
    
    Args:
        config: Server configuration dictionary containing:
               - host: Server host (default: localhost)
               - port: Server port (default: 8002)
               - Other server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract server parameters from config
    host = config.get("host", "localhost")
    port = config.get("port", 8004)
    
    # Create runtime provider
    runtime_provider = ACKNodePoolManagementRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    ACKNodePoolManagementHandler(server, allow_write, config)
    
    logger.info(f"ACK NodePool Management MCP Server created successfully on {host}:{port}")
    return server


def main():
    """Run ACK NodePool Management MCP server as standalone application."""
    # 首先加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    else:
        logger.warning("python-dotenv not available, using system environment variables only")
    
    parser = argparse.ArgumentParser(
        description="ACK NodePool Management MCP Server"
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
        default=8002,
        help="Port for SSE transport (default: 8002)"
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
        
        # 阿里云认证配置
        "region_id": args.region or os.getenv("REGION_ID", "cn-hangzhou"),
        "access_key_id": args.access_key_id or os.getenv("ACCESS_KEY_ID"),
        "access_key_secret": args.access_key_secret or os.getenv("ACCESS_KEY_SECRET"),
        "default_cluster_id": args.default_cluster_id or os.getenv("DEFAULT_CLUSTER_ID", ""),
        
        # NodePool特有配置
        "max_nodes_per_operation": int(os.getenv("MAX_NODES_PER_OPERATION", "10")),
        "scaling_timeout": int(os.getenv("SCALING_TIMEOUT", "300")),
        
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
    
    logger.info(f"Starting ACK NodePool Management MCP Server (region: {config['region_id']})")
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