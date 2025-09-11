"""ACK Diagnose MCP Server.

This server provides Alibaba Cloud Container Service (ACK) diagnosis capabilities including:
- Create cluster diagnosis tasks
- Get diagnosis results and check items
- List and get cluster inspection reports
- Run cluster inspections
- Manage inspection configurations
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

# 直接导入模块文件以避免相对导入问题
try:
    from handler import ACKDiagnoseHandler
    from runtime_provider import ACKDiagnoseRuntimeProvider
except ImportError:
    # 如果直接导入失败，尝试相对导入（用于子模块调用）
    try:
        from .handler import ACKDiagnoseHandler
        from .runtime_provider import ACKDiagnoseRuntimeProvider
    except ImportError as e:
        print(f"Failed to import modules: {e}")
        raise

# Server configuration
SERVER_NAME = "ack-diagnose-mcp-server"
SERVER_INSTRUCTIONS = """
ACK Diagnose MCP Server

This server provides comprehensive Alibaba Cloud Container Service (ACK) cluster diagnosis and inspection capabilities:

## Cluster Diagnosis Tools:

1. **create_cluster_diagnosis**: Create a cluster diagnosis task
   - Initiate comprehensive cluster health analysis
   - Support various diagnosis types (all, node, pod, network, etc.)
   - Return diagnosis task ID for result tracking

2. **get_cluster_diagnosis_result**: Get cluster diagnosis result
   - Retrieve diagnosis results by task ID
   - Get detailed diagnosis findings and recommendations
   - Monitor diagnosis progress and status

3. **get_cluster_diagnosis_check_items**: Get available diagnosis check items
   - List available diagnosis check categories
   - Get localized check item descriptions
   - Understand diagnosis scope and coverage

## Cluster Inspection Tools:

4. **list_cluster_inspect_reports**: List cluster inspection reports
   - Get paginated list of historical inspection reports
   - Support pagination with next_token and max_results parameters
   - Access inspection report metadata

5. **get_cluster_inspect_report_detail**: Get detailed inspection report
   - Retrieve complete inspection report content
   - Access detailed findings and recommendations
   - Get inspection timing and status information

6. **run_cluster_inspect**: Run cluster inspection
   - Initiate on-demand cluster inspection
   - Support different inspection types
   - Generate new inspection reports

## Inspection Configuration Tools:

7. **create_cluster_inspect_config**: Create inspection configuration
   - Define custom inspection parameters
   - Set inspection schedules and scope
   - Configure inspection rules and thresholds

8. **update_cluster_inspect_config**: Update inspection configuration
   - Modify existing inspection settings
   - Update inspection frequency and scope
   - Adjust inspection parameters

9. **get_cluster_inspect_config**: Get inspection configuration
   - Retrieve current inspection settings
   - View configured inspection parameters
   - Check inspection schedule and rules

## Authentication:
Configure Alibaba Cloud credentials through environment variables or credential files:
- ACCESS_KEY_ID: Alibaba Cloud Access Key ID
- ACCESS_KEY_SECRET: Alibaba Cloud Access Key Secret
- REGION_ID: Target region (default: cn-hangzhou)

## Usage:
This server can run standalone or be mounted as a sub-server in the main
AlibabaCloud Container Service MCP Server architecture.
"""

SERVER_DEPENDENCIES = [
    "fastmcp",
    "pydantic",
    "loguru", 
    "alibabacloud-cs20151215",  # Alibaba Cloud Container Service SDK
    "alibabacloud-credentials",  # Alibaba Cloud credentials
    "alibabacloud-tea-openapi",  # Alibaba Cloud OpenAPI SDK
    "alibabacloud-tea-util",     # Alibaba Cloud utility SDK
]


def create_mcp_server(config: Optional[Dict[str, Any]] = None) -> FastMCP:
    """Create ACK Diagnose MCP server instance.
    
    Args:
        config: Server configuration dictionary containing:
               - host: Server host (default: localhost)
               - port: Server port (default: 8003)
               - Other server configurations
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Extract server parameters from config
    host = config.get("host", "localhost")
    port = config.get("port", 8003)
    
    # Create runtime provider
    runtime_provider = ACKDiagnoseRuntimeProvider(config)
    
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
    ACKDiagnoseHandler(server, allow_write, config)
    
    logger.info(f"ACK Diagnose MCP Server created successfully on {host}:{port}")
    return server


def main():
    """Run ACK Diagnose MCP server as standalone application."""
    # 首先加载.env文件
    if DOTENV_AVAILABLE:
        load_dotenv()
        logger.info("Loaded configuration from .env file")
    else:
        logger.warning("python-dotenv not available, using system environment variables only")
    
    parser = argparse.ArgumentParser(
        description="ACK Diagnose MCP Server"
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
        default="sse",
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
    
    logger.info(f"Starting ACK Diagnose MCP Server (region: {config['region_id']})")
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