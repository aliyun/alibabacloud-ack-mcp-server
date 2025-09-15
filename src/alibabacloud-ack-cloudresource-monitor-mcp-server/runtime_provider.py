"""Runtime provider for Observability Aliyun CloudMonitor Resource Monitor MCP Server."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from fastmcp import FastMCP
from alibabacloud_cms20190101.client import Client as CMS20190101Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient

# 添加父目录到路径以导入interfaces
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from interfaces.runtime_provider import RuntimeProvider


class ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider(RuntimeProvider):
    """Runtime provider for Aliyun CloudMonitor resource monitoring operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        # 合并传入的配置和环境变量（.env文件已在server.py中加载）
        self.config = self._load_config_with_env(config or {})
        self.providers = {}
        
        logger.info(f"ObservabilityAliyunCloudMonitorResourceMonitorRuntimeProvider initialized with region: {self.config.get('region_id')}")
    
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
            "development": os.getenv("DEVELOPMENT", "false").lower() == "true",
            "collection_interval": int(os.getenv("COLLECTION_INTERVAL", "60")),
            "metric_retention": int(os.getenv("METRIC_RETENTION", "7")),
            "escalation_policy": os.getenv("ESCALATION_POLICY", "default")
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
            access_key_secret = config.get("access_key_secret")
            region_id = config.get("region_id", "cn-hangzhou")
            
            if access_key_id and access_key_secret:
                credential_client = CredentialClient()
                cms_config = open_api_models.Config(credential=credential_client)
                cms_config.access_key_id = access_key_id
                cms_config.access_key_secret = access_key_secret
                cms_config.region_id = region_id
                cms_config.endpoint = f"cms.{region_id}.aliyuncs.com"
                cms_client = CMS20190101Client(cms_config)
                
                providers["cms_client"] = {
                    "client": cms_client,
                    "credential_client": credential_client,
                    "type": "cloudmonitor_service",
                    "region": region_id,
                    "initialized": True
                }
                logger.info(f"CloudMonitor client initialized for region: {region_id}")
            else:
                logger.warning("CloudMonitor credentials not provided, using mock client")
                providers["cms_client"] = {
                    "client": None,
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize metrics collector
            providers["metrics_collector"] = {
                "type": "metrics_collector",
                "collection_interval": config.get("collection_interval", 60),
                "metric_retention": config.get("metric_retention", 7),  # days
                "collected_metrics": {}
            }
            
            # Initialize alert manager
            providers["alert_manager"] = {
                "type": "alert_manager",
                "notification_channels": ["sms", "email", "webhook"],
                "escalation_policy": config.get("escalation_policy", "default"),
                "active_alerts": {}
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun CloudMonitor Resource Monitor providers: {e}")
            providers["cms_client"] = {"client": None, "type": "error", "error": str(e)}
        
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