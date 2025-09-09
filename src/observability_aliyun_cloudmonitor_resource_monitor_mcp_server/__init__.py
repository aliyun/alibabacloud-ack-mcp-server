"""Observability Aliyun CloudMonitor Resource Monitor MCP Server Module."""

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "Observability Aliyun CloudMonitor Resource Monitor MCP Server"

from .handler import ObservabilityAliyunCloudMonitorResourceMonitorHandler
from .runtime_provider import ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider
from .server import create_mcp_server, main

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "ObservabilityAliyunCloudMonitorResourceMonitorHandler",
    "ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider",
    "create_mcp_server",
    "main"
]