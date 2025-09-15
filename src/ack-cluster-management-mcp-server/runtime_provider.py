"""Runtime provider for ACK Cluster Management MCP Server."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from fastmcp import FastMCP
from alibabacloud_cs20151215.client import Client as CS20151215Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient

# 添加父目录到路径以导入interfaces
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from interfaces.runtime_provider import RuntimeProvider


class ACKClusterManagementRuntimeProvider(RuntimeProvider):
    """Runtime provider for ACK cluster management operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        # 合并传入的配置和环境变量（.env文件已在server.py中加载）
        self.config = self._load_config_with_env(config or {})
        self.providers = {}
        
        logger.info(f"ACKClusterManagementRuntimeProvider initialized with region: {self.config.get('region_id')}")
    
    def _load_config_with_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration from environment variables and merge with provided config.
        
        Args:
            config: Base configuration dictionary
            
        Returns:
            Merged configuration with environment variables
        """
        # 从环境变量加载配置，传入的config优先级更高
        env_config = {
            "region_id": os.getenv("REGION_ID", "cn-hangzhou"),
            "access_key_id": os.getenv("ACCESS_KEY_ID"),
            "access_key_secret": os.getenv("ACCESS_KEY_SECRET"),
            "default_cluster_id": os.getenv("DEFAULT_CLUSTER_ID", ""),
            "cache_ttl": int(os.getenv("CACHE_TTL", "300")),
            "cache_max_size": int(os.getenv("CACHE_MAX_SIZE", "1000")),
            "fastmcp_log_level": os.getenv("FASTMCP_LOG_LEVEL", "INFO"),
            "development": os.getenv("DEVELOPMENT", "false").lower() == "true"
        }
        
        # 合并配置，传入的config覆盖环境变量
        merged_config = {**env_config, **config}
        
        # 记录配置信息（隐藏敏感信息）
        safe_config = merged_config.copy()
        if safe_config.get("access_key_secret"):
            safe_config["access_key_secret"] = safe_config["access_key_secret"][:8] + "***"
        
        logger.debug(f"Loaded configuration: {safe_config}")
        
        return merged_config
        
    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime environment for ACK cluster management.
        
        Args:
            app: FastMCP server instance
            
        Yields:
            Runtime context containing initialized providers
        """
        logger.info("Initializing ACK Cluster Management runtime environment")
        
        try:
            # Initialize providers
            self.providers = self.initialize_providers(self.config)
            
            # Create runtime context
            runtime_context = {
                "providers": self.providers,
                "config": self.config,
                "default_cluster": self.get_default_cluster(self.config)
            }
            
            logger.info("ACK Cluster Management runtime environment initialized successfully")
            yield runtime_context
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK Cluster Management runtime: {e}")
            raise
        finally:
            # Cleanup if needed
            logger.info("Cleaning up ACK Cluster Management runtime environment")
    
    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize ACK cluster management providers.
        
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
            cs_config.access_key_id = config.get("access_key_id")
            cs_config.access_key_secret = config.get("access_key_secret")
            cs_config.region_id = region
            cs_config.endpoint = f'cs.{region}.aliyuncs.com'
            
            cs_client = CS20151215Client(cs_config)
            
            providers["cs_client"] = {
                "type": "alibaba_cloud_cs",
                "client": cs_client,
                "region": region,
                "initialized": True
            }
            
            # Initialize cluster management capabilities
            providers["cluster_management_capabilities"] = {
                "type": "ack_cluster_management",
                "supported_operations": [
                    "describe_task_info",
                    "create_cluster_diagnosis",
                    "get_cluster_diagnosis_result",
                    "scale_nodepool",
                    "remove_nodepool_nodes"
                ],
                "region": region
            }
            
            logger.info(f"ACK cluster management providers initialized successfully for region: {region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ACK cluster management providers: {e}")
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