"""Runtime provider for ACK Addon Management MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from src.interfaces.runtime_provider import RuntimeProvider


class ACKAddonManagementRuntimeProvider(RuntimeProvider):
    """Runtime provider for ACK addon management operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for ACK addon management.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing ACK Addon Management runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("ACK Addon Management runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK Addon Management runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up ACK Addon Management runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize ACK addon management providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize Container Service client if credentials are available
            access_key_id = config.get("access_key_id")
            access_secret_key = config.get("access_secret_key")
            region_id = config.get("region_id", "cn-hangzhou")
            
            if access_key_id and access_secret_key:
                # TODO: Initialize actual AlibabaCloud Container Service client
                providers["cs_client"] = {
                    "type": "container_service",
                    "region": region_id,
                    "initialized": True
                }
                logger.info(f"Container Service client initialized for region: {region_id}")
            else:
                logger.warning("Container Service credentials not provided, using mock client")
                providers["cs_client"] = {
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize addon catalog provider
            providers["addon_catalog"] = {
                "type": "addon_catalog",
                "cached_addons": {},
                "last_refresh": None
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK addon management providers: {e}")
            providers["cs_client"] = {"type": "error", "error": str(e)}
        
        return providers
    
    def get_default_cluster(self, config: Dict[str, Any]) -> str:
        """Get default cluster ID for operations.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Default cluster ID
        """
        default_cluster = config.get("default_cluster_id", "")
        if not default_cluster:
            logger.warning("No default cluster ID configured")
        return default_cluster