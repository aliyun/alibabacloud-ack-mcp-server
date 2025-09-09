"""Runtime provider for Observability Aliyun CloudMonitor Resource Monitor MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from src.interfaces.runtime_provider import RuntimeProvider


class ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider(RuntimeProvider):
    """Runtime provider for Aliyun CloudMonitor resource monitoring operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for Aliyun CloudMonitor resource monitoring.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing Observability Aliyun CloudMonitor Resource Monitor runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("Observability Aliyun CloudMonitor Resource Monitor runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun CloudMonitor Resource Monitor runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up Observability Aliyun CloudMonitor Resource Monitor runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize Aliyun CloudMonitor resource monitoring providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize CloudMonitor client if credentials are available
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
                logger.info(f"CloudMonitor client initialized for region: {region_id}")
            else:
                logger.warning("CloudMonitor credentials not provided, using mock client")
                providers["cms_client"] = {
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize metrics collector
            providers["metrics_collector"] = {
                "type": "metrics_collector",
                "collection_interval": config.get("collection_interval", 60),
                "metric_retention": config.get("metric_retention", 7)  # days
            }
            
            # Initialize alert manager
            providers["alert_manager"] = {
                "type": "alert_manager",
                "notification_channels": ["sms", "email", "webhook"],
                "escalation_policy": config.get("escalation_policy", "default")
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun CloudMonitor Resource Monitor providers: {e}")
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