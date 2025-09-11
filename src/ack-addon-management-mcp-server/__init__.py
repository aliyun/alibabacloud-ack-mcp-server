"""ACK Addon Management MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK Addon Management MCP Server"

# Support both relative and absolute imports
try:
    from .handler import ACKAddonManagementHandler
    from .runtime_provider import ACKAddonManagementRuntimeProvider
    from .server import create_mcp_server, main
except ImportError:
    # If relative import fails, try absolute import
    try:
        from handler import ACKAddonManagementHandler
        from runtime_provider import ACKAddonManagementRuntimeProvider
        from server import create_mcp_server, main
    except ImportError:
        # If all fail, set to None
        ACKAddonManagementHandler = None
        ACKAddonManagementRuntimeProvider = None
        create_mcp_server = None
        main = None

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