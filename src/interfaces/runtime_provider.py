"""Abstract interface for runtime provider management in FastMCP.

This module defines the core interface for managing MCP server runtime providers,
including configuration management, service initialization, and resource lifecycle management.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from fastmcp import FastMCP


class RuntimeProvider(ABC):
    """Abstract base class for runtime provider management.
    
    RuntimeProvider负责管理MCP服务器运行时的各种提供者（providers），
    包括配置管理、服务初始化、资源生命周期管理等。

    RuntimeProvider基于FastMCP服务器的AbstractAsyncContextManager机制进行扩展，
    每个子MCP Server运行时提供者都继承了RuntimeProvider抽象类，并实现了抽象方法。
    主MCP Server需要以Proxy Mounting方式链接各个子MCP Server。
    子MCP Server被主MCP Server proxy mount时会触发各自的 FastMCP lifespan回调方法，
    并触发子MCP Server的init_runtime方法，完成子MCP Server的初始化。
    提供了抽象的运行时初始化方法、初始化提供者方法以及获取默认集群名称方法。
    """

    @abstractmethod
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """
        抽象的运行时初始化方法，由子类实现。
        
        Args:
            app: FastMCP服务器实例
            
        Yields:
            包含运行时上下文对象的字典
        """
        raise NotImplementedError
    
    @abstractmethod
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        初始化所有提供者，由子类实现。
        
        Args:
            config: 配置字典
            
        Returns:
            初始化后的提供者字典
        """
        raise NotImplementedError