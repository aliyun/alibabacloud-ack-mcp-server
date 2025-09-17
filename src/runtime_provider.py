"""Runtime provider for ACK Addon Management MCP Server."""

import os
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional
from loguru import logger
from fastmcp import FastMCP
from alibabacloud_cs20151215.client import Client as CS20151215Client
from alibabacloud_arms20190808.client import Client as ARMSClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_sls20201230.client import Client as SLSClient

# 添加父目录到路径以导入interfaces
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from interfaces.runtime_provider import RuntimeProvider
except ImportError:
    from .interfaces.runtime_provider import RuntimeProvider


class ACKClusterRuntimeProvider(RuntimeProvider):
    """Runtime provider for ACK Cluster Handler."""

    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Initialize runtime context for ACK Cluster Handler."""
        logger.info("Initializing ACK Cluster Handler runtime...")

        # 获取配置
        config = getattr(app, '_config', {})

        # 初始化提供者
        providers = self.initialize_providers(config)

        # 构建运行时上下文
        lifespan_context = {
            "config": config,
            "providers": providers,
        }

        try:
            yield lifespan_context
        finally:
            logger.info("ACK Cluster Handler runtime cleanup completed")

    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize providers for ACK Cluster Handler."""
        providers: Dict[str, Any] = {}

        # 初始化凭证客户端（使用全局默认凭证链）
        try:
            credential_client = CredentialClient()

            def cs_client_factory(target_region: str) -> CS20151215Client:
                """每次调用都重新创建 CS 客户端，不使用缓存。"""
                cs_config = open_api_models.Config(credential=credential_client)
                # 明确支持通过 config 覆盖 AK 信息
                if config.get("access_key_id"):
                    cs_config.access_key_id = config.get("access_key_id")
                if config.get("access_key_secret"):
                    cs_config.access_key_secret = config.get("access_key_secret")

                # 如果传入的 target_region = "CENTER"，则使用中心化endpoint
                if target_region == "CENTER":
                    cs_config.endpoint = f"cs.aliyuncs.com"
                else:
                    cs_config.region_id = target_region or config.get("region_id")
                    cs_config.endpoint = f"cs.{cs_config.region_id}.aliyuncs.com"
                client = CS20151215Client(cs_config)
                logger.debug(f"Created new CS client for region: {target_region}")
                return client

            providers["credential_client"] = credential_client
            providers["cs_client_factory"] = cs_client_factory
            providers["region_id"] = config.get("region_id")
            logger.info("ACK Cluster Handler providers initialized (cs_client_factory ready)")
        except Exception as e:
            logger.warning(f"Initialize providers partially without CS factory: {e}")
            providers["credential_client"] = None
            providers["cs_client_factory"] = None

        # 初始化 ARMS Client（Prometheus 管理端点解析使用）
        try:
            region_id = config.get("region_id") or "cn-hangzhou"
            arms_cfg = open_api_models.Config(credential=credential_client)
            if config.get("access_key_id"):
                arms_cfg.access_key_id = config.get("access_key_id")
            if config.get("access_key_secret"):
                arms_cfg.access_key_secret = config.get("access_key_secret")
            arms_cfg.region_id = region_id
            arms_cfg.endpoint = f"arms.{region_id}.aliyuncs.com"
            arms_client = ARMSClient(arms_cfg)
            providers["arms_client"] = {
                "client": arms_client,
                "region": region_id,
                "initialized": True,
            }
            logger.info("ARMS client initialized for region: {}".format(region_id))
        except Exception as e:
            logger.warning(f"Initialize ARMS client failed: {e}")
            providers["arms_client"] = {
                "client": None,
                "region": config.get("region_id"),
                "initialized": False,
                "error": str(e),
            }

        # 初始化 SLS Client Factory（审计日志查询使用）
        try:
            sls_client_factory = self.create_sls_client_factory(config)
            providers["sls_client_factory"] = sls_client_factory
            logger.info("SLS client factory initialized")
        except Exception as e:
            logger.warning(f"Initialize SLS client factory failed: {e}")
            providers["sls_client_factory"] = None

        # 初始化 Prometheus 指标指引
        try:
            prometheus_guidance = self.initialize_prometheus_guidance()
            providers["prometheus_guidance"] = prometheus_guidance
            logger.info("Prometheus guidance initialized")
        except Exception as e:
            logger.warning(f"Initialize Prometheus guidance failed: {e}")
            providers["prometheus_guidance"] = None

        return providers

    def get_default_cluster(self, config: Dict[str, Any]) -> str:
        """Get default cluster name."""
        return config.get("default_cluster_id", "")

    def create_sls_client_factory(self, config: Dict[str, Any]):
        """Create SLS client factory for audit log queries."""
        def sls_client_factory(cluster_id: str, region_id: str):
            """每次调用都重新创建 SLS 客户端，不使用缓存。"""
            try:
                # 获取访问密钥
                access_key_id = config.get("access_key_id") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
                access_key_secret = config.get("access_key_secret") or os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
                
                if not access_key_id or not access_key_secret:
                    raise ValueError("SLS access key credentials not found in config or environment variables")

                # 构建 SLS 配置
                sls_config = open_api_models.Config(
                    access_key_id=access_key_id,
                    access_key_secret=access_key_secret,
                    region_id=region_id,
                    # endpoint=f"https://{region_id}.log.aliyuncs.com"
                )
                # refer: https://help.aliyun.com/zh/sls/developer-reference/get-oss-ingestion
                sls_config.endpoint = f"{region_id}.log.aliyuncs.com"

                # 创建 SLS 客户端
                sls_client = SLSClient(sls_config)
                
                logger.debug(f"Created new SLS client for cluster {cluster_id} in region {region_id}")
                return sls_client
                
            except Exception as e:
                logger.error(f"Failed to create SLS client for cluster {cluster_id}: {e}")
                raise RuntimeError(f"SLS client initialization failed: {str(e)}")
        
        return sls_client_factory

    def initialize_prometheus_guidance(self) -> Dict[str, Any]:
        """初始化 Prometheus 指标指引数据。"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        guidance_dir = os.path.join(base_dir, "prometheus_metrics_guidance")
        
        guidance_data = {
            "metrics_dictionary": {},
            "promql_best_practice": {},
            "initialized": True,
            "error": None
        }
        
        try:
            # 读取指标定义文件
            metrics_dict_dir = os.path.join(guidance_dir, "metrics_dictionary")
            if os.path.isdir(metrics_dict_dir):
                guidance_data["metrics_dictionary"] = self._load_metrics_dictionary(metrics_dict_dir)
            
            # 读取 PromQL 最佳实践文件
            promql_practice_dir = os.path.join(guidance_dir, "promql_best_practice")
            if os.path.isdir(promql_practice_dir):
                guidance_data["promql_best_practice"] = self._load_promql_best_practice(promql_practice_dir)
                
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus guidance: {e}")
            guidance_data["initialized"] = False
            guidance_data["error"] = str(e)
            
        return guidance_data

    def _load_metrics_dictionary(self, directory: str) -> Dict[str, Any]:
        """加载指标定义文件。"""
        metrics_data = {}
        
        for filename in os.listdir(directory):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # 提取文件名作为key（去掉.json后缀）
                key = filename[:-5] if filename.endswith('.json') else filename
                metrics_data[key] = data
                
            except Exception as e:
                logger.warning(f"Failed to load metrics dictionary file {filename}: {e}")
                continue
                
        return metrics_data

    def _load_promql_best_practice(self, directory: str) -> Dict[str, Any]:
        """加载 PromQL 最佳实践文件。"""
        practice_data = {}
        
        for filename in os.listdir(directory):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # 提取文件名作为key（去掉.json后缀）
                key = filename[:-5] if filename.endswith('.json') else filename
                practice_data[key] = data
                
            except Exception as e:
                logger.warning(f"Failed to load PromQL best practice file {filename}: {e}")
                continue
                
        return practice_data

    def query_metrics_by_category_and_label(self, category: str, resource_label: str) -> List[Dict[str, Any]]:
        """根据分类和资源标签查询指标定义。"""
        # 重新初始化指引数据
        guidance = self.initialize_prometheus_guidance()
        if not guidance or not guidance.get("initialized"):
            return []
            
        metrics = []
        metrics_dict = guidance.get("metrics_dictionary", {})
        
        for file_key, file_data in metrics_dict.items():
            # 处理不同的文件结构
            metrics_list = []
            if isinstance(file_data, list):
                # 直接是数组结构
                metrics_list = file_data
            elif isinstance(file_data, dict):
                if "metrics" in file_data:
                    metrics_list = file_data["metrics"]
                elif isinstance(file_data.get("metrics"), list):
                    metrics_list = file_data["metrics"]
            else:
                continue
                
            # 过滤指标
            for metric in metrics_list:
                if not isinstance(metric, dict):
                    continue
                    
                metric_category = str(metric.get("category", "")).lower()
                metric_labels = metric.get("labels", []) or []
                
                if (metric_category == category.lower()) and (resource_label in metric_labels):
                    metrics.append({
                        "file_source": file_key,
                        "metric": metric
                    })
                    
        return metrics

    def query_promql_practices_by_category_and_label(self, category: str, resource_label: str) -> List[Dict[str, Any]]:
        """根据分类和资源标签查询 PromQL 最佳实践。"""
        # 重新初始化指引数据
        guidance = self.initialize_prometheus_guidance()
        if not guidance or not guidance.get("initialized"):
            return []
            
        practices = []
        practice_dict = guidance.get("promql_best_practice", {})
        
        for file_key, file_data in practice_dict.items():
            # 处理不同的文件结构
            rules_list = []
            if isinstance(file_data, list):
                # 直接是数组结构
                rules_list = file_data
            elif isinstance(file_data, dict):
                if "rules" in file_data:
                    rules_list = file_data["rules"]
                elif isinstance(file_data.get("rules"), list):
                    rules_list = file_data["rules"]
            else:
                continue
                
            # 过滤规则
            for rule in rules_list:
                if not isinstance(rule, dict):
                    continue
                    
                rule_category = str(rule.get("category", "")).lower()
                rule_labels = rule.get("labels", []) or []
                
                if (rule_category == category.lower()) and (resource_label in rule_labels):
                    practices.append({
                        "file_source": file_key,
                        "rule": rule
                    })
                    
        return practices