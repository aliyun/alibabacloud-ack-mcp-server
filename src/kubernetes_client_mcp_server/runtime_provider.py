"""Runtime provider for Kubernetes Client MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from src.interfaces.runtime_provider import RuntimeProvider


class KubernetesClientRuntimeProvider(RuntimeProvider):
    """Runtime provider for Kubernetes client operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for Kubernetes client.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing Kubernetes Client runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("Kubernetes Client runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes Client runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up Kubernetes Client runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize Kubernetes client providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize Kubernetes client if kubeconfig is available
            kubeconfig_path = config.get("kubeconfig_path", "~/.kube/config")
            
            # TODO: Initialize actual Kubernetes client from kubeconfig
            providers["k8s_client"] = {
                "type": "kubernetes",
                "kubeconfig": kubeconfig_path,
                "initialized": True
            }
            
            # Initialize resource cache for performance
            providers["resource_cache"] = {
                "type": "resource_cache",
                "ttl": config.get("cache_ttl", 300),  # 5 minutes
                "max_size": config.get("cache_max_size", 1000)
            }
            
            # Initialize YAML parser
            providers["yaml_parser"] = {
                "type": "yaml_parser",
                "safe_load": True
            }
            
            logger.info("Kubernetes client providers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client providers: {e}")
            providers["k8s_client"] = {"type": "error", "error": str(e)}
        
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