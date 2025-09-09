"""Kubernetes Client MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "Kubernetes Client MCP Server"

from .handler import KubernetesClientHandler
from .runtime_provider import KubernetesClientRuntimeProvider
from .server import create_mcp_server, main

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "KubernetesClientHandler",
    "KubernetesClientRuntimeProvider",
    "create_mcp_server",
    "main"
]