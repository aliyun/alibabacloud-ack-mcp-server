"""Runtime provider for K8s Diagnose MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP

from interfaces.runtime_provider import RuntimeProvider


class K8sDiagnoseRuntimeProvider(RuntimeProvider):
    """Runtime provider for K8s diagnosis operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for K8s diagnosis.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing K8s Diagnose runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("K8s Diagnose runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize K8s Diagnose runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up K8s Diagnose runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize K8s diagnosis providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize Kubernetes client if kubeconfig is available
            kubeconfig_path = config.get("kubeconfig_path", "~/.kube/config")
            
            # TODO: Initialize actual Kubernetes client
            providers["k8s_client"] = {
                "type": "kubernetes",
                "kubeconfig": kubeconfig_path,
                "initialized": True
            }
            
            # Initialize diagnostic tools
            providers["diagnostic_tools"] = {
                "type": "diagnostic_suite",
                "health_checks": ["nodes", "pods", "services", "ingress"],
                "network_tools": ["connectivity", "dns", "port_check"]
            }
            
            logger.info("K8s diagnosis providers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize K8s diagnosis providers: {e}")
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