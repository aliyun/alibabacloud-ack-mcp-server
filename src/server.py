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


import argparse
from AlibabaCloudlabs.ContainerService_mcp_server.cloudwatch_handler import CloudWatchHandler
from AlibabaCloudlabs.ContainerService_mcp_server.cloudwatch_metrics_guidance_handler import CloudWatchMetricsHandler
from AlibabaCloudlabs.ContainerService_mcp_server.ContainerService_kb_handler import ContainerServiceKnowledgeBaseHandler
from AlibabaCloudlabs.ContainerService_mcp_server.ContainerService_stack_handler import ContainerServiceStackHandler
from AlibabaCloudlabs.ContainerService_mcp_server.iam_handler import IAMHandler
from AlibabaCloudlabs.ContainerService_mcp_server.insights_handler import InsightsHandler
from AlibabaCloudlabs.ContainerService_mcp_server.k8s_handler import K8sHandler
from AlibabaCloudlabs.ContainerService_mcp_server.vpc_config_handler import VpcConfigHandler
from loguru import logger
from mcp.server.fastmcp import FastMCP

from src.config import get_settings, Configs

# Define server instructions and dependencies
# TODO
SERVER_INSTRUCTIONS = """

"""

SERVER_NAME = "alibabacloud-cs-mcp-server"

SERVER_DEPENDENCIES = [
    'pydantic',
    'loguru',
    'boto3',
    'kubernetes',
    'requests',
    'pyyaml',
    'cachetools',
    'requests_auth_AlibabaCloud_sigv4',
]

# Global reference to the MCP server instance for testing purposes
mcp = None
settings_dict = None


def create_server():
    """Create and configure the MCP server instance."""
    return FastMCP(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        dependencies=SERVER_DEPENDENCIES,
    )


def main():
    """Run the MCP server with CLI argument support."""
    global mcp
    global settings_dict

    parser = argparse.ArgumentParser(
        description='An AlibabaCloud Model Context Protocol (MCP) server for ContainerService'
    )
    parser.add_argument(
        '--allow-write',
        action=argparse.BooleanOptionalAction,
        default=False,
        help='Enable write access mode (allow mutating operations)',
    )

    args = parser.parse_args()
    allow_write = args.allow_write

    settings_dict = Configs(vars(args))

    # Log startup mode
    mode_info = []
    if not allow_write:
        mode_info.append('read-only mode')

    mode_str = ' in ' + ', '.join(mode_info) if mode_info else ''
    logger.info(f'Starting ContainerService MCP Server{mode_str}')

    # Create the MCP server instance
    mcp = create_server()

    # Initialize handlers - all tools are always registered, access control is handled within tools
    K8sHandler(mcp, allow_write, settings_dict)


    # Run server
    mcp.run()

    return mcp


if __name__ == '__main__':
    main()
