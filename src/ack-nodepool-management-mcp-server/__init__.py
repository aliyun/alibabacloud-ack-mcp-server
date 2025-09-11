"""ACK NodePool Management MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK NodePool Management MCP Server"

# Import only when needed to avoid circular imports during testing
try:
    from .handler import ACKNodePoolManagementHandler
    from .runtime_provider import ACKNodePoolManagementRuntimeProvider
    from .server import create_mcp_server, main
    
    __all__ = [
        "__version__",
        "__author__", 
        "__email__",
        "__description__",
        "ACKNodePoolManagementHandler",
        "ACKNodePoolManagementRuntimeProvider",
        "create_mcp_server",
        "main"
    ]
except ImportError:
    # Allow module to be imported during testing without all dependencies
    __all__ = [
        "__version__",
        "__author__", 
        "__email__",
        "__description__"
    ]