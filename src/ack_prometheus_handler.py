from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import httpx
import os
import json
from datetime import datetime
try:
    from .models import (
        ErrorModel,
        QueryPrometheusInput,
        QueryPrometheusSeriesPoint,
        QueryPrometheusOutput,
        QueryPrometheusMetricGuidanceInput,
        QueryPrometheusMetricGuidanceOutput,
        MetricDefinition,
    )
except ImportError:
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
                return {"error": ErrorModel(error_code="MissingEndpoint", error_message="无法获取 Prometheus HTTP API，请确定此集群是否已经正常部署阿里云Prometheus 或 环境变量 PROMETHEUS_HTTP_API[_<cluster_id>]").model_dump()}

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
            # guidance 文件位于 src/prometheus_metrics_dictionary 目录下
            guidance_dir = os.path.join(base_dir, "prometheus_metrics_guidance/metrics_dictionary")
            
            if not os.path.isdir(guidance_dir):
                return {"error": ErrorModel(error_code="GuidanceDirectoryNotFound", error_message=f"Directory not found: {guidance_dir}").model_dump()}

            metrics: List[MetricDefinition] = []
            errors: List[str] = []
            
            # 遍历目录下的所有 JSON 文件
            try:
                for filename in os.listdir(guidance_dir):
                    if not filename.endswith('.json'):
                        continue
                        
                    file_path = os.path.join(guidance_dir, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            guidance_data = json.load(f)
                            
                        # 处理每个 JSON 文件中的指标定义
                        # 支持不同的文件结构，如 {"cadvisor": {"metrics": [...]}} 或直接的 {"metrics": [...]}
                        if isinstance(guidance_data, dict):
                            # 如果文件结构是 {"cadvisor": {"metrics": [...]}}
                            if "metrics" in guidance_data:
                                items = guidance_data["metrics"]
                            # 如果整个文件就是一个指标数组
                            elif isinstance(guidance_data.get("metrics"), list):
                                items = guidance_data["metrics"]
                            else:
                                # 尝试将整个文件作为指标数组处理
                                items = guidance_data if isinstance(guidance_data, list) else []
                            
                            # 处理每个指标
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
                                    
                    except Exception as e:
                        error_msg = f"Error reading {filename}: {str(e)}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                        
            except Exception as e:
                return {"error": ErrorModel(error_code="GuidanceReadError", error_message=f"Error reading guidance directory: {str(e)}").model_dump()}

            # 如果有错误但也有一些成功的指标，记录警告但继续返回结果
            if errors:
                logger.warning(f"Some guidance files had errors: {errors}")

            return QueryPrometheusMetricGuidanceOutput(metrics=metrics, error=None)