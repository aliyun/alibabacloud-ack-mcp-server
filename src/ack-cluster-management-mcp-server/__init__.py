"""ACK Cluster Management MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK Cluster Management MCP Server"

# 支持相对导入和绝对导入
try:
    from .handler import ACKClusterManagementHandler
    from .runtime_provider import ACKClusterManagementRuntimeProvider
    from .server import create_mcp_server, main
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    try:
        from handler import ACKClusterManagementHandler
        from runtime_provider import ACKClusterManagementRuntimeProvider
        from server import create_mcp_server, main
    except ImportError:
        # 如果都失败，则设置为None
        ACKClusterManagementHandler = None
        ACKClusterManagementRuntimeProvider = None
        create_mcp_server = None
        main = None

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "ACKClusterManagementHandler",
    "ACKClusterManagementRuntimeProvider",
    "create_mcp_server",
    "main"
]