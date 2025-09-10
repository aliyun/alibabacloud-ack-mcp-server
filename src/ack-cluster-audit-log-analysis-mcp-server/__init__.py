"""AlibabaCloud ACK Cluster Audit Log Analysis MCP Server."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK Cluster Audit Log Analysis MCP Server"

# Import main components for easy access
from interfaces.runtime_provider import RuntimeProvider
from .context.lifespan_manager import (
    KubeAuditRuntimeProvider,
    ConfigValidationError,
    ConfigLoader,
)

from .provider import (
    Provider,
    AlibabaSLSProvider,
)

from .server import (
    create_server,
    create_mcp_server,
    main,
)

from .toolkits import KubeAuditTool


# Define what gets imported with "from ack_cluster_audit_log_analysis_mcp_server import *"
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
    "create_mcp_server",
    "main",
    
    # Tools
    "KubeAuditTool",
    
]
