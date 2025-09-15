"""Runtime provider for Kubernetes Client MCP Server."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any
from loguru import logger
from fastmcp import FastMCP
from kubernetes import client, config as k8s_config
import yaml

# 添加父目录到路径以导入interfaces
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from interfaces.runtime_provider import RuntimeProvider


class KubernetesClientRuntimeProvider(RuntimeProvider):
    """Runtime provider for Kubernetes client operations."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the runtime provider.
        
        Args:
            config: Configuration dictionary
        """
        # 合并传入的配置和环境变量（.env文件已在server.py中加载）
        self.config = self._load_config_with_env(config or {})
        self.providers = {}
        
        logger.info(f"KubernetesClientRuntimeProvider initialized with kubeconfig: {self.config.get('kubeconfig_path')}")
    
    def _load_config_with_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration from environment variables and merge with provided config.
        
        Args:
            config: Base configuration dictionary
            
        Returns:
            Merged configuration with environment variables
        """
        # 从环境变量加载配置，传入的config优先级更高
        env_config = {
            "kubeconfig_path": os.getenv("KUBECONFIG", "~/.kube/config"),
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
            
            # 尝试加载 kubeconfig
            try:
                if os.path.exists(os.path.expanduser(kubeconfig_path)):
                    k8s_config.load_kube_config(config_file=kubeconfig_path)
                else:
                    # 尝试使用集群内配置
                    k8s_config.load_incluster_config()
                
                # 创建 Kubernetes 客户端（移除已废弃的 ExtensionsV1beta1Api）
                v1_client = client.CoreV1Api()
                apps_v1_client = client.AppsV1Api()
                networking_v1_client = None
                batch_v1_client = None
                try:
                    networking_v1_client = client.NetworkingV1Api()
                except Exception:
                    networking_v1_client = None
                try:
                    batch_v1_client = client.BatchV1Api()
                except Exception:
                    batch_v1_client = None
                
                providers["k8s_client"] = {
                    "client": {
                        "core_v1": v1_client,
                        "apps_v1": apps_v1_client,
                        "networking_v1": networking_v1_client,
                        "batch_v1": batch_v1_client
                    },
                    "type": "kubernetes",
                    "kubeconfig": kubeconfig_path,
                    "initialized": True
                }
                logger.info(f"Kubernetes client initialized with kubeconfig: {kubeconfig_path}")
                
            except Exception as e:
                logger.warning(f"Failed to load kubeconfig, using mock client: {e}")
                providers["k8s_client"] = {
                    "client": None,
                    "type": "mock",
                    "kubeconfig": kubeconfig_path,
                    "initialized": False,
                    "error": str(e)
                }
            
            # Initialize resource cache for performance
            providers["resource_cache"] = {
                "type": "resource_cache",
                "ttl": config.get("cache_ttl", 300),  # 5 minutes
                "max_size": config.get("cache_max_size", 1000),
                "cache": {}
            }
            
            # Initialize YAML parser
            providers["yaml_parser"] = {
                "type": "yaml_parser",
                "safe_load": True,
                "parser": yaml
            }
            
            logger.info("Kubernetes client providers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client providers: {e}")
            providers["k8s_client"] = {"client": None, "type": "error", "error": str(e)}
        
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