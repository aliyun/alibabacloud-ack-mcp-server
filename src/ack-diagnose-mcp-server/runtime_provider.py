"""Runtime provider for ACK Diagnose MCP Server."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from mcp.server.fastmcp import FastMCP
from alibabacloud_cs20151215.client import Client as CS20151215Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient

from interfaces.runtime_provider import RuntimeProvider


class ACKDiagnoseRuntimeProvider(RuntimeProvider):
    """Runtime provider for ACK cluster diagnosis and inspection operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.providers = {}
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for ACK diagnosis.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing ACK Diagnose runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("ACK Diagnose runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK Diagnose runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up ACK Diagnose runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize ACK diagnosis providers.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Dictionary of initialized providers
        """
        providers = {}
        
        try:
            # Initialize Alibaba Cloud CS client
            region = config.get("region_id", "cn-hangzhou")
            
            # Use credential client for secure authentication
            credential = CredentialClient()
            cs_config = open_api_models.Config(credential=credential)
            cs_config.endpoint = f'cs.{region}.aliyuncs.com'
            
            cs_client = CS20151215Client(cs_config)
            
            providers["cs_client"] = {
                "type": "alibaba_cloud_cs",
                "client": cs_client,
                "region": region,
                "initialized": True
            }
            
            # Initialize diagnosis capabilities
            providers["diagnosis_capabilities"] = {
                "type": "ack_diagnosis",
                "supported_operations": [
                    "create_cluster_diagnosis",
                    "get_cluster_diagnosis_result", 
                    "get_cluster_diagnosis_check_items",
                    "list_cluster_inspect_reports",
                    "get_cluster_inspect_report_detail",
                    "run_cluster_inspect",
                    "create_cluster_inspect_config",
                    "update_cluster_inspect_config",
                    "get_cluster_inspect_config"
                ],
                "region": region
            }
            
            logger.info(f"ACK diagnosis providers initialized successfully for region: {region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK diagnosis providers: {e}")
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