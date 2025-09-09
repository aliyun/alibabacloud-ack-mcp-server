"""ACK Addon Management MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK Addon Management MCP Server"

from .handler import ACKAddonManagementHandler
from .runtime_provider import ACKAddonManagementRuntimeProvider
from .server import create_mcp_server, main

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "ACKAddonManagementHandler",
    "ACKAddonManagementRuntimeProvider",
    "create_mcp_server",
    "main"
]