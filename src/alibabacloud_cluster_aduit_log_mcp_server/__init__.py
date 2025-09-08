"""AlibabaCloud ACK MCP Server - Kubernetes audit log querying server."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK MCP Server for Kubernetes audit log querying"

# Import main components for easy access
from utils.context import (
    LifespanManager,
)
from alibabacloud_cluster_aduit_log_mcp_server.context.lifespan_manager import (
    KubeAuditLifespanManager,
    ConfigValidationError,
    ConfigLoader,
)

from alibabacloud_cluster_aduit_log_mcp_server.provider.provider import (
    Provider,
    AlibabaSLSProvider,
)


# Define what gets imported with "from alibabacloud_cluster_aduit_log_mcp_server import *"
__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    
    # Lifespan managers
    "LifespanManager",
    "KubeAuditLifespanManager",
    "ConfigValidationError",
    "ConfigLoader",
    
    # Providers
    "Provider",
    "AlibabaSLSProvider",
    
]
