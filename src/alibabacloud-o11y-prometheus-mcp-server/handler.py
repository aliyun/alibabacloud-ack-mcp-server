"""Observability Aliyun Prometheus Handler."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cms20190101 import models as cms20190101_models
from alibabacloud_tea_util import models as util_models
import json


def _serialize_sdk_object(obj):
    """序列化阿里云SDK对象为可JSON序列化的字典."""
    if obj is None:
        return None
    
    # 如果是基本数据类型，直接返回
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # 如果是列表或元组，递归处理每个元素
    if isinstance(obj, (list, tuple)):
        return [_serialize_sdk_object(item) for item in obj]
    
    # 如果是字典，递归处理每个值
    if isinstance(obj, dict):
        return {key: _serialize_sdk_object(value) for key, value in obj.items()}
    
    # 尝试获取对象的属性字典
    try:
        # 对于阿里云SDK对象，通常有to_map()方法
        if hasattr(obj, 'to_map'):
            return obj.to_map()
        
        # 对于其他对象，尝试获取其__dict__属性
        if hasattr(obj, '__dict__'):
            return _serialize_sdk_object(obj.__dict__)
        
        # 尝试转换为字符串
        return str(obj)
    except Exception:
        # 如果都失败了，返回字符串表示
        return str(obj)


class ObservabilityAliyunPrometheusHandler:
    """Handler for Aliyun Prometheus observability operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the Aliyun Prometheus observability handler.
        
        Args:
            server: FastMCP server instance
            allow_write: Whether to allow write operations
            settings: Configuration settings
        """
        self.server = server
        self.allow_write = allow_write
        self.settings = settings or {}
        
        # Register tools
        self._register_tools()
        
        logger.info("Observability Aliyun Prometheus Handler initialized")
    
    def _register_tools(self):
        """Register Prometheus observability related tools."""
        
        @self.server.tool(
            name="cms_execute_promql_query",
            description="Execute PromQL query in Aliyun Prometheus"
        )
        async def cms_execute_promql_query(
            query: str,
            start_time: Optional[str] = None,
            end_time: Optional[str] = None,
            step: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Execute PromQL query.
            
            Args:
                query: PromQL query string
                start_time: Query start time (optional)
                end_time: Query end time (optional) 
                step: Query step interval (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Query result
            """
            # Get CMS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cms_client_info = providers.get("cms_client", {})
                cms_client = cms_client_info.get("client")
                
                if not cms_client:
                    return {"error": "CMS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CMS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # 使用云监控 API 执行 PromQL 查询
                request = cms20190101_models.DescribeMetricListRequest(
                    metric_name=query,  # 这里可能需要进一步解析 PromQL
                    namespace="acs_ecs_dashboard",  # 示例名称空间
                    start_time=start_time,
                    end_time=end_time,
                    period=step or "60"
                )
                runtime = util_models.RuntimeOptions()
                
                response = await cms_client.describe_metric_list_with_options_async(
                    request, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                data_points_data = _serialize_sdk_object(response.body.data_points) if response.body.data_points else []
                
                return {
                    "query": query,
                    "start_time": start_time,
                    "end_time": end_time,
                    "step": step,
                    "result": data_points_data,
                    "status": "success",
                    "request_id": getattr(response.body, 'request_id', None) if response.body else None
                }
                
            except Exception as e:
                logger.error(f"Failed to execute PromQL query: {e}")
                return {
                    "query": query,
                    "start_time": start_time,
                    "end_time": end_time,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="cms_translate_text_to_promql",
            description="Translate natural language to PromQL query"
        )
        async def cms_translate_text_to_promql(
            text: str,
            context: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Translate natural language to PromQL.
            
            Args:
                text: Natural language description
                context: Additional context (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Generated PromQL query
            """
            # Get prometheus engine from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                prometheus_engine = providers.get("prometheus_engine", {})
                
                if not prometheus_engine:
                    return {"error": "Prometheus engine not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get Prometheus engine from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # 简单的文本到 PromQL 的转换逻辑（实际应用中需要更复杂的 NLP 处理）
                promql_query = "# Generated PromQL query"
                confidence = 0.8
                
                # 根据关键词生成简单的 PromQL
                if "cpu" in text.lower():
                    promql_query = "cpu_usage_active"
                    confidence = 0.9
                elif "memory" in text.lower():
                    promql_query = "memory_utilization"
                    confidence = 0.9
                elif "disk" in text.lower():
                    promql_query = "diskusage_utilization"
                    confidence = 0.9
                elif "network" in text.lower():
                    promql_query = "networkin_rate"
                    confidence = 0.85
                
                return {
                    "input_text": text,
                    "context": context,
                    "promql_query": promql_query,
                    "explanation": f"Translated '{text}' to PromQL query",
                    "confidence": confidence
                }
                
            except Exception as e:
                logger.error(f"Failed to translate text to PromQL: {e}")
                return {
                    "input_text": text,
                    "context": context,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="get_prometheus_metrics",
            description="Get available Prometheus metrics"
        )
        async def get_prometheus_metrics(
            filter_pattern: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get available Prometheus metrics.
            
            Args:
                filter_pattern: Pattern to filter metrics (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of available metrics
            """
            # Get CMS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cms_client_info = providers.get("cms_client", {})
                cms_client = cms_client_info.get("client")
                
                if not cms_client:
                    return {"error": "CMS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CMS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # 获取可用的监控指标
                request = cms20190101_models.DescribeMetricMetaListRequest()
                runtime = util_models.RuntimeOptions()
                
                response = await cms_client.describe_metric_meta_list_with_options_async(
                    request, runtime
                )
                
                metrics = []
                if response.body and response.body.resources and response.body.resources.resource:
                    for resource in response.body.resources.resource:
                        if resource.metrics and resource.metrics.metric:
                            for metric in resource.metrics.metric:
                                metric_info = {
                                    "name": getattr(metric, 'metric_name', None),
                                    "description": getattr(metric, 'description', None) or getattr(metric, 'metric_name', None),
                                    "namespace": getattr(resource, 'namespace', None),
                                    "dimensions": _serialize_sdk_object(getattr(metric, 'dimensions', None)) or []
                                }
                                
                                # 应用过滤模式
                                if filter_pattern:
                                    if filter_pattern.lower() in (getattr(metric, 'metric_name', '') or '').lower():
                                        metrics.append(metric_info)
                                else:
                                    metrics.append(metric_info)
                
                return {
                    "filter_pattern": filter_pattern,
                    "metrics": metrics,
                    "total_count": len(metrics),
                    "request_id": getattr(response.body, 'request_id', None) if response.body else None
                }
                
            except Exception as e:
                logger.error(f"Failed to get Prometheus metrics: {e}")
                return {
                    "filter_pattern": filter_pattern,
                    "error": str(e),
                    "status": "error"
                }