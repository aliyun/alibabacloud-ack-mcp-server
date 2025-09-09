"""AlibabaCloud ACK MCP Server - Kubernetes audit log querying server."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK MCP Server for Kubernetes audit log querying"

# Import main components for easy access
from src.runtime_provider import RuntimeProvider
from alibabacloud_cluster_audit_log_mcp_server.context.lifespan_manager import (
    KubeAuditRuntimeProvider,
    ConfigValidationError,
    ConfigLoader,
)

from alibabacloud_cluster_audit_log_mcp_server.provider import (
    Provider,
    AlibabaSLSProvider,
)

from alibabacloud_cluster_audit_log_mcp_server.server import (
    create_server,
    main,
)

from alibabacloud_cluster_audit_log_mcp_server.toolkits import KubeAuditTool


# Define what gets imported with "from alibabacloud_cluster_audit_log_mcp_server import *"
__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    
    # Runtime providers
    "RuntimeProvider",
    "KubeAuditRuntimeProvider",
    "ConfigValidationError",
    "ConfigLoader",
    
    # Providers
    "Provider",
    "AlibabaSLSProvider",
    
    # Server functions
    "create_server",
    "main",
    
    # Tools
    "KubeAuditTool",
    
]
