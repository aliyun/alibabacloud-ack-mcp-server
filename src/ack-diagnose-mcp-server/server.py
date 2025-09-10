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
from mcp.server.fastmcp import FastMCP

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
   - Filter reports by time range and status
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
        config: Server configuration dictionary
        
    Returns:
        Configured FastMCP server instance
    """
    config = config or {}
    
    # Create runtime provider
    runtime_provider = ACKDiagnoseRuntimeProvider(config)
    
    # Create FastMCP server with runtime provider
    server = FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
        lifespan=runtime_provider.init_runtime,
    )
    
    # Initialize handler
    allow_write = config.get("allow_write", False)
    ACKDiagnoseHandler(server, allow_write, config)
    
    logger.info("ACK Diagnose MCP Server created successfully")
    return server


def main():
    """Run ACK Diagnose MCP server as standalone application."""
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
        "--region",
        "-r",
        type=str,
        default="cn-hangzhou",
        help="Alibaba Cloud region (default: cn-hangzhou)"
    )
    parser.add_argument(
        "--access-key-id",
        type=str,
        help="Alibaba Cloud Access Key ID (can also use environment variable ACCESS_KEY_ID)"
    )
    parser.add_argument(
        "--access-key-secret",
        type=str,
        help="Alibaba Cloud Access Key Secret (can also use environment variable ACCESS_KEY_SECRET)"
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
        "region_id": args.region,
        "access_key_id": args.access_key_id or os.environ.get("ACCESS_KEY_ID"),
        "access_key_secret": args.access_key_secret or os.environ.get("ACCESS_KEY_SECRET"),
        "default_cluster_id": os.environ.get("DEFAULT_CLUSTER_ID", ""),
        "cache_ttl": int(os.environ.get("CACHE_TTL", "300")),
        "cache_max_size": int(os.environ.get("CACHE_MAX_SIZE", "1000")),
    }
    
    logger.info(f"Starting ACK Diagnose MCP Server (region: {args.region})")
    
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