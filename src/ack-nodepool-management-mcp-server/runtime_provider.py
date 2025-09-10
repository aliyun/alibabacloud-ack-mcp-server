"""Runtime provider for ACK NodePool Management MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from fastmcp import FastMCP

from interfaces.runtime_provider import RuntimeProvider


class ACKNodePoolManagementRuntimeProvider(RuntimeProvider):
    """Runtime provider for ACK nodepool management operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for ACK nodepool management.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing ACK NodePool Management runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("ACK NodePool Management runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK NodePool Management runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up ACK NodePool Management runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize ACK nodepool management providers.
        
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
            
            # Initialize nodepool management provider
            providers["nodepool_manager"] = {
                "type": "nodepool_manager",
                "max_nodes_per_operation": config.get("max_nodes_per_operation", 10),
                "scaling_timeout": config.get("scaling_timeout", 300)
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK nodepool management providers: {e}")
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