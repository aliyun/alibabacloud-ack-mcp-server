"""ACK Diagnose MCP Server Module."""

import importlib
import os
import sys

__version__ = "0.1.0"
__author__ = "AlibabaCloud"
__email__ = "support@alibabacloud.com"
__description__ = "AlibabaCloud ACK Cluster Diagnosis and Inspection MCP Server"

# 获取当前模块所在目录
current_dir = os.path.dirname(__file__)
module_name = os.path.basename(current_dir)

# 动态导入模块内的子模块
try:
    handler_module = importlib.import_module(f'{module_name}.handler')
    runtime_provider_module = importlib.import_module(f'{module_name}.runtime_provider')
    server_module = importlib.import_module(f'{module_name}.server')
    
    ACKDiagnoseHandler = handler_module.ACKDiagnoseHandler
    ACKDiagnoseRuntimeProvider = runtime_provider_module.ACKDiagnoseRuntimeProvider
    create_mcp_server = server_module.create_mcp_server
    main = server_module.main
except ImportError:
    # 如果动态导入失败，尝试直接导入（用于开发环境）
    try:
        from . import handler, runtime_provider, server
        ACKDiagnoseHandler = handler.ACKDiagnoseHandler
        ACKDiagnoseRuntimeProvider = runtime_provider.ACKDiagnoseRuntimeProvider
        create_mcp_server = server.create_mcp_server
        main = server.main
    except ImportError:
        # 最后的备选方案
        ACKDiagnoseHandler = None
        ACKDiagnoseRuntimeProvider = None
        create_mcp_server = None
        main = None

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "ACKDiagnoseHandler",
    "ACKDiagnoseRuntimeProvider",
    "create_mcp_server",
    "main"
]