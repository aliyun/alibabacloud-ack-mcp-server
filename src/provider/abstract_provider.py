"""Abstract interface for provider management in FastMCP."""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server.fastmcp import FastMCP

"""
MCP Server的依赖Provider抽象类
"""


class ProviderManager(ABC):
    """Abstract base class for provider management."""

    @abstractmethod
    @asynccontextmanager
    async def initialize(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """
        Abstract provider method to be implemented by subclasses.

        Args:
            app: The FastMCP server instance

        Yields:
            A dictionary containing context objects
        """
        raise NotImplementedError
