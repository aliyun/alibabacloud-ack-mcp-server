"""Abstract interface for lifespan management in FastMCP."""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

import yaml
from mcp.server.fastmcp import FastMCP


class LifespanManager(ABC):
    """Abstract base class for lifespan management."""

    @abstractmethod
    @asynccontextmanager
    async def lifespan(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """
        Abstract lifespan method to be implemented by subclasses.

        Args:
            app: The FastMCP server instance

        Yields:
            A dictionary containing context objects
        """
        raise NotImplementedError
