from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import httpx
import os
from datetime import datetime
from models import (
    ErrorModel,
    QueryPrometheusInput,
    QueryPrometheusSeriesPoint,
    QueryPrometheusOutput,
    QueryPrometheusMetricGuidanceInput,
    QueryPrometheusMetricGuidanceOutput,
    MetricDefinition,
    PromQLSample,
)


class PrometheusHandler:
    """ACK Prometheus 查询与指标指引 Handler。"""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {}
        if server is None:
            return
        self.server = server
        self.allow_write = self.settings.get("allow_write", True)

        self.server.tool(name="query_prometheus", description="查询一个ACK集群的阿里云Prometheus数据")(
            self.query_prometheus)

        self.server.tool(name="query_prometheus_metric_guidance", description="获取Prometheus指标定义和最佳实践")(
            self.query_prometheus_metric_guidance)
        logger.info("Prometheus Handler initialized")

    def _get_cluster_region(self, cs_client, cluster_id: str) -> str:
        """通过DescribeClusterDetail获取集群的region信息

        Args:
            cs_client: CS客户端实例
            cluster_id: 集群ID

        Returns:
            集群所在的region
        """
        try:
            from alibabacloud_cs20151215 import models as cs_models

            # 调用DescribeClusterDetail API获取集群详情
            detail_response = cs_client.describe_cluster_detail(cluster_id)

            if not detail_response or not detail_response.body:
                raise ValueError(f"Failed to get cluster details for {cluster_id}")

            cluster_info = detail_response.body
            # 获取集群的region信息
            region = getattr(cluster_info, 'region_id', '')

            if not region:
                raise ValueError(f"Could not determine region for cluster {cluster_id}")

            return region

        except Exception as e:
            logger.error(f"Failed to get cluster region for {cluster_id}: {e}")
            raise ValueError(f"Failed to get cluster region for {cluster_id}: {e}")


    def _resolve_prometheus_endpoint(self, ctx: Context, cluster_id: str) -> Optional[str]:
        # 1) 优先参考 alibabacloud-o11y-prometheus-mcp-server 中的方法：
        #    从 providers 里取 ARMS client，调用 GetPrometheusInstance，获取 http_api_inter_url（公网）
        lifespan = getattr(ctx.request_context, "lifespan_context", {}) or {}
        providers = lifespan.get("providers", {}) if isinstance(lifespan, dict) else {}
        try:
            cs_client = _get_cs_client(ctx, "CENTER")
            region_id = self._get_cluster_region(cs_client, cluster_id)
            config = (lifespan.get("config", {}) or {}) if isinstance(lifespan, dict) else {}
            arms_client_factory = providers.get("arms_client_factory") if isinstance(providers, dict) else None
            if arms_client_factory and region_id:
                arms_client = arms_client_factory(region_id, config)
                from alibabacloud_arms20190808 import models as arms_models
                from alibabacloud_tea_util import models as util_models
                req = arms_models.GetPrometheusInstanceRequest(region_id=region_id, cluster_id=cluster_id)
                runtime = util_models.RuntimeOptions()
                resp = arms_client.get_prometheus_instance_with_options(req, runtime)
                data = getattr(resp.body, 'data', None)
                if data:
                    ep = getattr(data, 'http_api_inter_url', None) or getattr(data, 'http_api_intra_url', None)
                    if ep:
                        return str(ep).rstrip('/')
        except Exception as e:
            logger.debug(f"resolve endpoint via ARMS failed: {e}")

        # 2) providers 中的静态映射
        endpoints = providers.get("prometheus_endpoints", {}) if isinstance(providers, dict) else {}
        if isinstance(endpoints, dict):
            ep = endpoints.get(cluster_id) or endpoints.get("default")
            if ep:
                return ep.rstrip("/")

        # 2) 其次尝试环境变量：PROMETHEUS_HTTP_API_{cluster_id} 或 PROMETHEUS_HTTP_API
        env_key_specific = f"PROMETHEUS_HTTP_API_{cluster_id}"
        env_key_global = "PROMETHEUS_HTTP_API"
        ep = os.getenv(env_key_specific) or os.getenv(env_key_global)
        if ep:
            return ep.rstrip("/")
        return None

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
        endpoint = self._resolve_prometheus_endpoint(ctx, cluster_id)
        if not endpoint:
            return {"error": ErrorModel(error_code="MissingEndpoint",
                                        error_message="无法获取 Prometheus HTTP API，请确定此集群是否已经正常部署阿里云Prometheus 或 环境变量 PROMETHEUS_HTTP_API[_<cluster_id>]").model_dump()}

        has_range = bool(start_time and end_time)
        params: Dict[str, Any] = {"query": promql}
        url = endpoint + ("/api/v1/query_range" if has_range else "/api/v1/query")
        if has_range:
            params["start"] = self._parse_time(start_time)
            params["end"] = self._parse_time(end_time)
            if step:
                params["step"] = step

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

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

        return QueryPrometheusOutput(
            resultType=result_type or ("matrix" if has_range else "vector"),
            result=[QueryPrometheusSeriesPoint(**item) for item in normalized],
        )

    async def query_prometheus_metric_guidance(
            self,
            ctx: Context,
            resource_label: str = Field(...,
                                        description="资源维度label：node/pod/container/deployment/daemonset/job/coredns/ingress/hpa/persistentvolume/mountpoint 等"),
            metric_category: str = Field(..., description="指标分类：cpu/memory/network/disk/state"),
    ) -> QueryPrometheusMetricGuidanceOutput | Dict[str, Any]:
        # 从 runtime context 获取 Prometheus 指标指引数据
        lifespan = getattr(ctx.request_context, "lifespan_context", {}) or {}
        providers = lifespan.get("providers", {}) if isinstance(lifespan, dict) else {}
        prometheus_guidance = providers.get("prometheus_guidance", {}) if isinstance(providers, dict) else {}

        if not prometheus_guidance or not prometheus_guidance.get("initialized"):
            return {"error": ErrorModel(error_code="GuidanceNotInitialized",
                                        error_message="Prometheus guidance not initialized").model_dump()}

        metrics: List[MetricDefinition] = []
        promql_samples: List[PromQLSample] = []

        try:
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

        except Exception as e:
            return {"error": ErrorModel(error_code="GuidanceQueryError",
                                        error_message=f"Error querying guidance data: {str(e)}").model_dump()}

        # 构建返回结果，包含指标定义和 PromQL 最佳实践
        return QueryPrometheusMetricGuidanceOutput(
            metrics=metrics,
            promql_samples=promql_samples,
            error=None
        )

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
