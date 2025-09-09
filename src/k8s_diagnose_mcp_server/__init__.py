"""K8s Diagnose MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "Kubernetes Diagnosis MCP Server"

from .handler import K8sDiagnoseHandler
from .runtime_provider import K8sDiagnoseRuntimeProvider
from .server import create_mcp_server, main

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "K8sDiagnoseHandler",
    "K8sDiagnoseRuntimeProvider",
    "create_mcp_server",
    "main"
]