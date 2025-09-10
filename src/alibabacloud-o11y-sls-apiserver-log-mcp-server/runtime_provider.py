"""Runtime provider for Observability SLS Cluster APIServer Log Analysis MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from interfaces.runtime_provider import RuntimeProvider


class ObservabilitySLSClusterAPIServerLogAnalysisRuntimeProvider(RuntimeProvider):
    """Runtime provider for SLS APIServer log analysis operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for SLS APIServer log analysis.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing Observability SLS APIServer Log Analysis runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("Observability SLS APIServer Log Analysis runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability SLS APIServer Log Analysis runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up Observability SLS APIServer Log Analysis runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize SLS APIServer log analysis providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize SLS client if credentials are available
            access_key_id = config.get("access_key_id")
            access_secret_key = config.get("access_secret_key")
            region_id = config.get("region_id", "cn-hangzhou")
            
            if access_key_id and access_secret_key:
                # TODO: Initialize actual AlibabaCloud SLS client
                providers["sls_client"] = {
                    "type": "simple_log_service",
                    "region": region_id,
                    "initialized": True
                }
                logger.info(f"SLS client initialized for region: {region_id}")
            else:
                logger.warning("SLS credentials not provided, using mock client")
                providers["sls_client"] = {
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize SQL query engine
            providers["sql_engine"] = {
                "type": "sls_sql_engine",
                "query_timeout": config.get("query_timeout", 60),
                "max_results": config.get("max_results", 1000)
            }
            
            # Initialize log analysis engine
            providers["log_analyzer"] = {
                "type": "apiserver_log_analyzer",
                "error_patterns": ["error", "failed", "timeout", "denied"],
                "warning_patterns": ["warning", "retry", "slow"]
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability SLS APIServer Log Analysis providers: {e}")
            providers["sls_client"] = {"type": "error", "error": str(e)}
        
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