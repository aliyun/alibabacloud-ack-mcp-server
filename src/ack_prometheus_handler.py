from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import httpx
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from models import (
    ErrorModel,
    QueryPrometheusSeriesPoint,
    QueryPrometheusOutput,
    QueryPrometheusMetricGuidanceOutput,
    MetricDefinition,
    PromQLSample,
    ExecutionLog,
    enable_execution_log_ctx,
)


class PrometheusHandler:
    """ACK Prometheus 查询与指标指引 Handler。"""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {}
        # prometheus_endpoint_mode: "ARMS_PUBLIC" (default), "ARMS_PRIVATE", or "LOCAL"
        self.prometheus_endpoint_mode = self.settings.get("prometheus_endpoint_mode", "ARMS_PUBLIC")

        self.allow_write = self.settings.get("allow_write", True)

        # Per-handler toggle
        self.enable_execution_log = self.settings.get("enable_execution_log", False)

        if server is None:
            return
        self.server = server

        self.server.tool(name="query_prometheus", description="查询一个ACK集群的阿里云Prometheus数据")(
            self.query_prometheus)

        self.server.tool(name="query_prometheus_metric_guidance", description="获取Prometheus指标定义和最佳实践")(
            self.query_prometheus_metric_guidance)
        logger.info("Prometheus Handler initialized")

    def _get_cluster_region(self, cs_client, cluster_id: str, execution_log: ExecutionLog) -> str:
        """通过DescribeClusterDetail获取集群的region信息

        Args:
            cs_client: CS客户端实例
            cluster_id: 集群ID

        Returns:
            集群所在的region
        """
        try:
            # 调用DescribeClusterDetail API获取集群详情
            api_start = int(time.time() * 1000)
            detail_response = cs_client.describe_cluster_detail(cluster_id)
            api_duration = int(time.time() * 1000) - api_start
            
            # Extract request_id
            request_id = None
            if hasattr(detail_response, 'headers') and detail_response.headers:
                request_id = detail_response.headers.get('x-acs-request-id', 'N/A')

            if not detail_response or not detail_response.body:
                execution_log.api_calls.append({
                    "api": "DescribeClusterDetail",
                    "cluster_id": cluster_id,
                    "request_id": request_id,
                    "duration_ms": api_duration,
                    "status": "failed",
                    "error": "No response body"
                })
                raise ValueError(f"Failed to get cluster details for {cluster_id}")

            cluster_info = detail_response.body
            # 获取集群的region信息
            region = getattr(cluster_info, 'region_id', '')

            if not region:
                execution_log.api_calls.append({
                    "api": "DescribeClusterDetail",
                    "cluster_id": cluster_id,
                    "request_id": request_id,
                    "duration_ms": api_duration,
                    "status": "failed",
                    "error": "No region_id in response"
                })
                raise ValueError(f"Could not determine region for cluster {cluster_id}")
            
            # Log successful API call
            execution_log.api_calls.append({
                "api": "DescribeClusterDetail",
                "cluster_id": cluster_id,
                "request_id": request_id,
                "duration_ms": api_duration,
                "status": "success",
                "region_id": region
            })

            return region

        except Exception as e:
            logger.error(f"Failed to get cluster region for {cluster_id}: {e}")
            raise ValueError(f"Failed to get cluster region for {cluster_id}: {e}")


    def _resolve_prometheus_endpoint(self, ctx: Context, cluster_id: str, execution_log: ExecutionLog) -> Optional[str]:
        lifespan = getattr(ctx.request_context, "lifespan_context", {}) or {}
        providers = lifespan.get("providers", {}) if isinstance(lifespan, dict) else {}
        
        # Check prometheus_endpoint_mode setting
        if self.prometheus_endpoint_mode == "LOCAL":
            # Mode: LOCAL - Use static config or environment variables only
            return self._resolve_from_local(providers, cluster_id, execution_log)
        elif self.prometheus_endpoint_mode == "ARMS_PRIVATE":
            # Mode: ARMS_PRIVATE - Use ARMS API to get private endpoint, fallback to local
            return self._resolve_from_arms(ctx, providers, cluster_id, execution_log, use_private=True)
        else:
            # Mode: ARMS_PUBLIC (default) - Use ARMS API to get public endpoint, fallback to local
            return self._resolve_from_arms(ctx, providers, cluster_id, execution_log, use_private=False)
    
    def _resolve_from_local(self, providers: dict, cluster_id: str, execution_log: ExecutionLog) -> Optional[str]:
        """Resolve Prometheus endpoint from local config (static config or env vars)"""
        # 1) providers 中的静态映射
        endpoints = providers.get("prometheus_endpoints", {}) if isinstance(providers, dict) else {}
        if isinstance(endpoints, dict):
            ep = endpoints.get(cluster_id) or endpoints.get("default")
            if ep:
                execution_log.api_calls.append({
                    "api": "GetPrometheusEndpoint",
                    "source": "static_config",
                    "mode": "LOCAL",
                    "cluster_id": cluster_id,
                    "endpoint": ep.rstrip("/"),
                    "status": "success"
                })
                return ep.rstrip("/")

        # 2) 环境变量：PROMETHEUS_HTTP_API_{cluster_id} 或 PROMETHEUS_HTTP_API
        env_key_specific = f"PROMETHEUS_HTTP_API_{cluster_id}"
        env_key_global = "PROMETHEUS_HTTP_API"
        ep = os.getenv(env_key_specific) or os.getenv(env_key_global)
        if ep:
            source = env_key_specific if os.getenv(env_key_specific) else env_key_global
            execution_log.api_calls.append({
                "api": "GetPrometheusEndpoint",
                "source": f"env_var:{source}",
                "mode": "LOCAL",
                "cluster_id": cluster_id,
                "endpoint": ep.rstrip("/"),
                "status": "success"
            })
            return ep.rstrip("/")
        return None
    
    def _resolve_from_arms(self, ctx: Context, providers: dict, cluster_id: str, execution_log: ExecutionLog, use_private: bool = False) -> Optional[str]:
        """Resolve Prometheus endpoint from ARMS API, with fallback to local
        
        Args:
            ctx: FastMCP context
            providers: Runtime providers
            cluster_id: ACK cluster ID
            execution_log: Execution log for tracking
            use_private: If True, use http_api_intra_url (private); if False, use http_api_inter_url (public)
        """
        # 1) 优先参考 alibabacloud-o11y-prometheus-mcp-server 中的方法：
        #    从 providers 里取 ARMS client，调用 GetPrometheusInstance
        mode = "ARMS_PRIVATE" if use_private else "ARMS_PUBLIC"
        try:
            cs_client = _get_cs_client(ctx, "CENTER")
            region_id = self._get_cluster_region(cs_client, cluster_id, execution_log)
            config = (ctx.request_context.lifespan_context.get("config", {}) or {}) if hasattr(ctx.request_context, "lifespan_context") and isinstance(ctx.request_context.lifespan_context, dict) else {}
            arms_client_factory = providers.get("arms_client_factory") if isinstance(providers, dict) else None
            if arms_client_factory and region_id:
                arms_client = arms_client_factory(region_id, config)
                from alibabacloud_arms20190808 import models as arms_models
                from alibabacloud_tea_util import models as util_models
                req = arms_models.GetPrometheusInstanceRequest(region_id=region_id, cluster_id=cluster_id)
                runtime = util_models.RuntimeOptions()
                
                # Call ARMS API with execution logging
                api_start = int(time.time() * 1000)
                resp = arms_client.get_prometheus_instance_with_options(req, runtime)
                api_duration = int(time.time() * 1000) - api_start
                
                # Extract request_id
                request_id = None
                if hasattr(resp, 'headers') and resp.headers:
                    request_id = resp.headers.get('x-acs-request-id', 'N/A')
                
                data = getattr(resp.body, 'data', None)
                if data:
                    # Select endpoint based on mode
                    if use_private:
                        # ARMS_PRIVATE: prefer intra_url (private network)
                        ep = getattr(data, 'http_api_intra_url', None) or getattr(data, 'http_api_inter_url', None)
                    else:
                        # ARMS_PUBLIC: prefer inter_url (public network)
                        ep = getattr(data, 'http_api_inter_url', None) or getattr(data, 'http_api_intra_url', None)
                    
                    if ep:
                        # Log successful ARMS API call
                        execution_log.api_calls.append({
                            "api": "GetPrometheusInstance",
                            "source": "arms_api",
                            "mode": mode,
                            "cluster_id": cluster_id,
                            "region_id": region_id,
                            "request_id": request_id,
                            "duration_ms": api_duration,
                            "status": "success",
                            "endpoint_type": "private" if use_private else "public"
                        })
                        return str(ep).rstrip('/')
                else:
                    execution_log.warnings.append(f"ARMS API returned no data for cluster {cluster_id}")
        except Exception as e:
            logger.debug(f"resolve endpoint via ARMS failed: {e}")
            execution_log.warnings.append(f"Failed to resolve endpoint via ARMS: {str(e)}")

        # 2) Fallback to local resolution
        return self._resolve_from_local(providers, cluster_id, execution_log)

    def _parse_time(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        # 允许传入 RFC3339 或 unix 秒/毫秒，统一转成秒级 unix 字符串
        try:
            # 尝试解析 RFC3339
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return str(int(dt.timestamp()))
        except Exception:
            # 直接传回（由后端 Prometheus 判定）
            return value

    async def query_prometheus(
            self,
            ctx: Context,
            cluster_id: str = Field(..., description="需要查询的阿里云prometheus所在的ACK集群的clusterId"),
            promql: str = Field(..., description="PromQL表达式"),
            start_time: Optional[str] = Field(None, description="RFC3339或unix时间；与end_time同时提供为range查询; 可能需要调用tool get_current_time获取当前时间"),
            end_time: Optional[str] = Field(None, description="RFC3339或unix时间；与start_time同时提供为range查询；可能需要调用tool get_current_time获取当前时间"),
            step: Optional[str] = Field(None, description="range查询步长，如30s"),
    ) -> QueryPrometheusOutput | Dict[str, Any]:
        # Set per-request context from handler setting
        enable_execution_log_ctx.set(self.enable_execution_log)
        
        # Initialize execution log
        start_ms = int(time.time() * 1000)
        execution_log = ExecutionLog(
            tool_call_id=f"query_prometheus_{cluster_id}_{start_ms}",
            start_time=datetime.utcnow().isoformat() + "Z"
        )
        
        try:
            endpoint = self._resolve_prometheus_endpoint(ctx, cluster_id, execution_log)
            if not endpoint:
                error_msg = "无法获取 Prometheus HTTP API，请确定此集群是否已经正常部署阿里云Prometheus 或 环境变量 PROMETHEUS_HTTP_API[_<cluster_id>]"
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": "MissingEndpoint",
                    "failure_stage": "resolve_endpoint"
                }
                return {
                    "error": ErrorModel(error_code="MissingEndpoint", error_message=error_msg).model_dump(),
                    "execution_log": execution_log
                }

            has_range = bool(start_time and end_time)
            params: Dict[str, Any] = {"query": promql}
            url = endpoint + ("/api/v1/query_range" if has_range else "/api/v1/query")
            if has_range:
                params["start"] = self._parse_time(start_time)
                params["end"] = self._parse_time(end_time)
                if step:
                    params["step"] = step

            execution_log.messages.append(f"Calling Prometheus API: {url} with params: {params}")

            # Call Prometheus API with execution logging
            api_start = int(time.time() * 1000)
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                
                api_duration = int(time.time() * 1000) - api_start
                
                # Calculate response content size
                response_size = len(resp.content) if resp.content else 0
                
                # Concise logging for success
                execution_log.api_calls.append({
                    "api": "PrometheusQuery",
                    "endpoint": url,
                    "cluster_id": cluster_id,
                    "duration_ms": api_duration,
                    "status": "success",
                    "http_status": resp.status_code,
                    "response_size_bytes": response_size
                })
                
            except httpx.HTTPStatusError as e:
                api_duration = int(time.time() * 1000) - api_start
                error_msg = f"Prometheus API error: {e.response.status_code} - {e.response.text}"
                execution_log.api_calls.append({
                    "api": "PrometheusQuery",
                    "endpoint": url,
                    "cluster_id": cluster_id,
                    "duration_ms": api_duration,
                    "status": "failed",
                    "http_status": e.response.status_code,
                    "error": error_msg
                })
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": "HTTPStatusError",
                    "failure_stage": "prometheus_query",
                    "http_status": e.response.status_code
                }
                return {
                    "error": ErrorModel(error_code="PrometheusAPIError", error_message=error_msg).model_dump(),
                    "execution_log": execution_log
                }
            except Exception as e:
                api_duration = int(time.time() * 1000) - api_start
                error_msg = f"Failed to query Prometheus: {str(e)}"
                execution_log.api_calls.append({
                    "api": "PrometheusQuery",
                    "endpoint": url,
                    "cluster_id": cluster_id,
                    "duration_ms": api_duration,
                    "status": "failed",
                    "error": error_msg
                })
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": type(e).__name__,
                    "failure_stage": "prometheus_query"
                }
                return {
                    "error": ErrorModel(error_code="QueryFailed", error_message=error_msg).model_dump(),
                    "execution_log": execution_log
                }

            # 直接透传 Prometheus 的 status/data，但补充兼容所需的 resultType/result 展示
            result = data.get("data", {}) if isinstance(data, dict) else {}
            result_type = result.get("resultType")
            raw_result = result.get("result", [])

            # 兼容输出：resultType + result 列表；对 instant query 将 value 适配为 values 列表
            normalized = []
            if isinstance(raw_result, list):
                for item in raw_result:
                    if not isinstance(item, dict):
                        continue
                    metric = item.get("metric", {})
                    if has_range:
                        values = item.get("values", [])
                    else:
                        v = item.get("value")
                        values = [v] if v else []
                    normalized.append({
                        "metric": metric,
                        "values": values,
                    })
            
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms

            return QueryPrometheusOutput(
                resultType=result_type or ("matrix" if has_range else "vector"),
                result=[QueryPrometheusSeriesPoint(**item) for item in normalized],
                execution_log=execution_log
            )
        
        except Exception as e:
            logger.error(f"Failed to query prometheus: {e}")
            execution_log.error = str(e)
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms
            execution_log.metadata = {
                "error_type": type(e).__name__,
                "failure_stage": "query_prometheus"
            }
            return {
                "error": ErrorModel(error_code="UnknownError", error_message=str(e)).model_dump(),
                "execution_log": execution_log
            }

    async def query_prometheus_metric_guidance(
            self,
            ctx: Context,
            resource_label: str = Field(...,
                                        description="资源维度label：node/pod/container/deployment/daemonset/job/coredns/ingress/hpa/persistentvolume/mountpoint 等"),
            metric_category: str = Field(..., description="指标分类：cpu/memory/network/disk/state"),
    ) -> QueryPrometheusMetricGuidanceOutput | Dict[str, Any]:
        # Set per-request context from handler setting
        enable_execution_log_ctx.set(self.enable_execution_log)
        
        # Initialize execution log
        start_ms = int(time.time() * 1000)
        execution_log = ExecutionLog(
            tool_call_id=f"query_prometheus_metric_guidance_{resource_label}_{metric_category}_{start_ms}",
            start_time=datetime.utcnow().isoformat() + "Z"
        )
        
        try:
            # 从 runtime context 获取 Prometheus 指标指引数据
            lifespan = getattr(ctx.request_context, "lifespan_context", {}) or {}
            providers = lifespan.get("providers", {}) if isinstance(lifespan, dict) else {}
            prometheus_guidance = providers.get("prometheus_guidance", {}) if isinstance(providers, dict) else {}

            if not prometheus_guidance or not prometheus_guidance.get("initialized"):
                error_msg = "Prometheus guidance not initialized"
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": "GuidanceNotInitialized",
                    "failure_stage": "check_initialization"
                }
                return {
                    "error": ErrorModel(error_code="GuidanceNotInitialized", error_message=error_msg).model_dump(),
                    "execution_log": execution_log
                }

            metrics: List[MetricDefinition] = []
            promql_samples: List[PromQLSample] = []

            # 查询指标定义
            metrics_dict = prometheus_guidance.get("metrics_dictionary", {})
            for file_key, file_data in metrics_dict.items():
                if not isinstance(file_data, dict):
                    continue

                # 处理不同的文件结构
                metrics_list = []
                if "metrics" in file_data:
                    metrics_list = file_data["metrics"]
                elif isinstance(file_data.get("metrics"), list):
                    metrics_list = file_data["metrics"]
                elif isinstance(file_data, list):
                    metrics_list = file_data

                # 过滤指标
                for m in metrics_list:
                    if not isinstance(m, dict):
                        continue
                    labels = m.get("labels", []) or []
                    category = str(m.get("category", "")).lower()
                    if (resource_label in labels) and (category == metric_category.lower()):
                        metrics.append(MetricDefinition(
                            description=m.get("description"),
                            category=m.get("category"),
                            labels=m.get("labels") or [],
                            name=m.get("name"),
                            type=m.get("type"),
                        ))

            # 查询 PromQL 最佳实践
            practice_dict = prometheus_guidance.get("promql_best_practice", {})
            for file_key, file_data in practice_dict.items():
                if not isinstance(file_data, dict):
                    continue

                # 处理不同的文件结构
                rules_list = []
                if "rules" in file_data:
                    rules_list = file_data["rules"]
                elif isinstance(file_data.get("rules"), list):
                    rules_list = file_data["rules"]
                elif isinstance(file_data, list):
                    rules_list = file_data

                # 过滤规则
                for rule in rules_list:
                    if not isinstance(rule, dict):
                        continue
                    rule_category = str(rule.get("category", "")).lower()
                    rule_labels = rule.get("labels", []) or []
                    if (rule_category == metric_category.lower()) and (resource_label in rule_labels):
                        promql_samples.append(PromQLSample(
                            rule_name=rule.get("rule_name", ""),
                            description=rule.get("description"),
                            recommendation_sop=rule.get("recommendation_sop"),
                            expression=rule.get("expression", ""),
                            severity=rule.get("severity", ""),
                            category=rule.get("category", ""),
                            labels=rule.get("labels", [])
                        ))
            
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms

            # 构建返回结果，包含指标定义和 PromQL 最佳实践
            return QueryPrometheusMetricGuidanceOutput(
                metrics=metrics,
                promql_samples=promql_samples,
                error=None,
                execution_log=execution_log
            )

        except Exception as e:
            logger.error(f"Error querying guidance data: {e}")
            execution_log.error = str(e)
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms
            execution_log.metadata = {
                "error_type": type(e).__name__,
                "failure_stage": "query_guidance"
            }
            return {
                "error": ErrorModel(error_code="GuidanceQueryError", error_message=f"Error querying guidance data: {str(e)}").model_dump(),
                "execution_log": execution_log
            }

def _get_cs_client(ctx: Context, region_id: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = ctx.request_context.lifespan_context
    if isinstance(lifespan_context, dict):
        providers = lifespan_context.get("providers", {})
        config = lifespan_context.get("config", {})
    else:
        providers = getattr(lifespan_context, "providers", {})
        config = getattr(lifespan_context, "config", {}) if hasattr(lifespan_context, "config") else {}

    cs_client_factory = providers.get("cs_client_factory")
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region_id, config)
