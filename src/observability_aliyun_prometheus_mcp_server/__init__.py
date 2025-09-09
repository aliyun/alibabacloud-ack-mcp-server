"""Observability Aliyun Prometheus MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "Observability Aliyun Prometheus MCP Server"

from .handler import ObservabilityAliyunPrometheusHandler
from .runtime_provider import ObservabilityAliyunPrometheusRuntimeProvider
from .server import create_mcp_server, main

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "ObservabilityAliyunPrometheusHandler",
    "ObservabilityAliyunPrometheusRuntimeProvider",
    "create_mcp_server",
    "main"
]