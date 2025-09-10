"""Runtime provider for Observability Aliyun Prometheus MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from interfaces.runtime_provider import RuntimeProvider


class ObservabilityAliyunPrometheusRuntimeProvider(RuntimeProvider):
    """Runtime provider for Aliyun Prometheus observability operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for Aliyun Prometheus observability.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing Observability Aliyun Prometheus runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("Observability Aliyun Prometheus runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun Prometheus runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up Observability Aliyun Prometheus runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize Aliyun Prometheus observability providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize CloudMonitor Service client if credentials are available
            access_key_id = config.get("access_key_id")
            access_secret_key = config.get("access_secret_key")
            region_id = config.get("region_id", "cn-hangzhou")
            
            if access_key_id and access_secret_key:
                # TODO: Initialize actual AlibabaCloud CloudMonitor client
                providers["cms_client"] = {
                    "type": "cloudmonitor_service",
                    "region": region_id,
                    "initialized": True
                }
                logger.info(f"CloudMonitor Service client initialized for region: {region_id}")
            else:
                logger.warning("CloudMonitor Service credentials not provided, using mock client")
                providers["cms_client"] = {
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize Prometheus query engine
            providers["prometheus_engine"] = {
                "type": "prometheus_query_engine",
                "query_timeout": config.get("query_timeout", 30),
                "max_series": config.get("max_series", 10000)
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun Prometheus providers: {e}")
            providers["cms_client"] = {"type": "error", "error": str(e)}
        
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