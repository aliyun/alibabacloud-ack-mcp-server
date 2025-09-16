from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import httpx
import os
import json
from datetime import datetime
from models import (
    ErrorModel,
    QueryPrometheusInput,
    QueryPrometheusSeriesPoint,
    QueryPrometheusOutput,
    QueryPrometheusMetricGuidanceInput,
    QueryPrometheusMetricGuidanceOutput,
    MetricDefinition,
)


class PrometheusHandler:
    """ACK Prometheus 查询与指标指引 Handler。"""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)
        self._register_tools()
        logger.info("Prometheus Handler initialized")

    def _resolve_prometheus_endpoint(self, ctx: Context, cluster_id: str) -> Optional[str]:
        # 1) 优先参考 alibabacloud-o11y-prometheus-mcp-server 中的方法：
        #    从 providers 里取 ARMS client，调用 GetPrometheusInstance，获取 http_api_inter_url（公网）
        lifespan = getattr(ctx.request_context, "lifespan_context", {}) or {}
        providers = lifespan.get("providers", {}) if isinstance(lifespan, dict) else {}
        try:
            arms_info = providers.get("arms_client", {}) if isinstance(providers, dict) else {}
            arms_client = arms_info.get("client") if isinstance(arms_info, dict) else None
            region_id = (lifespan.get("config", {}) or {}).get("region_id") if isinstance(lifespan, dict) else None
            if arms_client and region_id:
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

    def _register_tools(self):
        @self.server.tool(name="query_prometheus", description="查询一个ACK集群的阿里云Prometheus数据")
        async def query_prometheus(
                ctx: Context,
                cluster_id: str = Field(..., description="需要查询的prometheus所在的集群clusterId"),
                promql: str = Field(..., description="PromQL表达式"),
                start_time: Optional[str] = Field(None, description="RFC3339或unix时间；与end_time同时提供为range查询"),
                end_time: Optional[str] = Field(None, description="RFC3339或unix时间；与start_time同时提供为range查询"),
                step: Optional[str] = Field(None, description="range查询步长，如30s"),
        ) -> QueryPrometheusOutput | Dict[str, Any]:
            endpoint = self._resolve_prometheus_endpoint(ctx, cluster_id)
            if not endpoint:
                return {"error": ErrorModel(error_code="MissingEndpoint", error_message="无法解析 Prometheus HTTP API，请配置 ARMS 客户端或环境变量 PROMETHEUS_HTTP_API[_<cluster_id>]").model_json()}

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

        @self.server.tool(name="query_prometheus_metric_guidance", description="获取Prometheus指标定义")
        async def query_prometheus_metric_guidance(
                ctx: Context,
                resource_label: str = Field(..., description="资源维度label：node/pod/container 等"),
                metric_category: str = Field(..., description="指标分类：cpu/memory/network/disk"),
        ) -> QueryPrometheusMetricGuidanceOutput | Dict[str, Any]:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            # guidance 文件位于 src/data 下
            guidance_path = os.path.join(os.path.dirname(base_dir), "data", "ack_prometheus_metrics_guidance_cadvisor.json")
            if not os.path.isfile(guidance_path):
                return {"error": ErrorModel(error_code="GuidanceNotFound", error_message=f"not found: {guidance_path}").model_json()}

            try:
                with open(guidance_path, "r", encoding="utf-8") as f:
                    guidance = json.load(f)
            except Exception as e:
                return {"error": {"error_code": "GuidanceReadError", "error_message": str(e)}}

            metrics: List[MetricDefinition] = []
            cadvisor = guidance.get("cadvisor", {}) if isinstance(guidance, dict) else {}
            items = cadvisor.get("metrics", []) if isinstance(cadvisor, dict) else []
            for m in items:
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

            return QueryPrometheusMetricGuidanceOutput(metrics=metrics, error=None)