"""Runtime provider for Observability Aliyun Prometheus MCP Server."""

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


class ObservabilityAliyunPrometheusRuntimeProvider(RuntimeProvider):
    """Runtime provider for Aliyun Prometheus observability operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        # 合并传入的配置和环境变量（.env文件已在server.py中加载）
        self.config = self._load_config_with_env(config or {})
        self.providers = {}
        
        logger.info(f"ObservabilityAliyunPrometheusRuntimeProvider initialized with region: {self.config.get('region_id')}")
    
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
            "query_timeout": int(os.getenv("PROMETHEUS_QUERY_TIMEOUT", "30")),
            "max_series": int(os.getenv("PROMETHEUS_MAX_SERIES", "10000"))
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
            access_key_secret = config.get("access_key_secret")
            region_id = config.get("region_id", "cn-hangzhou")
            
            if access_key_id and access_key_secret:
                # 初始化阿里云凭证客户端
                credential_config = open_api_models.Config(
                    access_key_id=access_key_id,
                    access_key_secret=access_key_secret
                )
                credential_client = CredentialClient(credential_config)
                
                # 初始化云监控服务客户端
                cms_config = open_api_models.Config(
                    access_key_id=access_key_id,
                    access_key_secret=access_key_secret,
                    region_id=region_id,
                    endpoint=f"cms.{region_id}.aliyuncs.com"
                )
                cms_client = CMS20190101Client(cms_config)
                
                providers["cms_client"] = {
                    "client": cms_client,
                    "credential_client": credential_client,
                    "type": "cloudmonitor_service",
                    "region": region_id,
                    "initialized": True
                }
                logger.info(f"CloudMonitor Service client initialized for region: {region_id}")
            else:
                logger.warning("CloudMonitor Service credentials not provided, using mock client")
                providers["cms_client"] = {
                    "client": None,
                    "type": "mock",
                    "region": region_id,
                    "initialized": False
                }
            
            # Initialize Prometheus query engine
            providers["prometheus_engine"] = {
                "type": "prometheus_query_engine",
                "query_timeout": config.get("query_timeout", 30),
                "max_series": config.get("max_series", 10000),
                "query_cache": {}
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize Observability Aliyun Prometheus providers: {e}")
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