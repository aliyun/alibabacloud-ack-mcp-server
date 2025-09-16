"""Observability Aliyun Prometheus Handler."""

from fastmcp import FastMCP, Context

from typing import Any, Callable, Dict, List, Optional, TypeVar, cast
from loguru import logger
from alibabacloud_sls20201230.client import Client as SLSClient
from alibabacloud_sls20201230.models import (
    CallAiToolsRequest,
    CallAiToolsResponse,
    GetLogsRequest,
    GetLogsResponse,
    ListLogStoresRequest,
    ListLogStoresResponse,
    ListProjectRequest,
    ListProjectResponse,
)
from alibabacloud_tea_util import models as util_models
from pydantic import Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from utils.utils import handle_tea_exception
from alibabacloud_arms20190808 import models as arms_models
import httpx
import os
import json
from pydantic import BaseModel


class ObservabilityAliyunPrometheusHandler:
    """aliyun observability tools manager"""
    
    def __init__(self, server: FastMCP):
        """
        initialize the tools manager
        
        Args:
            server: FastMCP server instance
        """
        self.server = server
        self._register_tools()
    
    def _register_tools(self):
        """register alibabacloud prometheus related tools functions"""

        # @self.server.tool()
        # @retry(
        #     stop=stop_after_attempt(2),
        #     wait=wait_fixed(1),
        #     retry=retry_if_exception_type(Exception),
        #     reraise=True,
        # )
        # @handle_tea_exception
        # def alibabacloud_prometheus_translate_text_to_promql(
        #         ctx: Context,
        #         text: str = Field(
        #             ...,
        #             description="the natural language text to generate promql",
        #         ),
        #         project: str = Field(..., description="sls project name"),
        #         metricStore: str = Field(..., description="sls metric store name"),
        #         regionId: str = Field(
        #             default=...,
        #             description="aliyun region id,region id format like 'xx-xxx',like 'cn-hangzhou'",
        #         ),
        # ) -> str:
        #     """将自然语言转换为Prometheus PromQL查询语句。
        #
        #     ## 功能概述
        #
        #     该工具可以将自然语言描述转换为有效的PromQL查询语句，便于用户使用自然语言表达查询需求。
        #
        #     ## 使用场景
        #
        #     - 当用户不熟悉PromQL查询语法时
        #     - 当需要快速构建复杂查询时
        #     - 当需要从自然语言描述中提取查询意图时
        #
        #     ## 使用限制
        #
        #     - 仅支持生成PromQL查询
        #     - 生成的是查询语句，而非查询结果
        #     - 禁止使用sls_execute_query工具执行，两者接口不兼容
        #
        #     ## 最佳实践
        #
        #     - 提供清晰简洁的自然语言描述
        #     - 不要在描述中包含项目或时序库名称
        #     - 首次生成的查询可能不完全符合要求，可能需要多次尝试
        #
        #     ## 查询示例
        #
        #     - "帮我生成 XXX 的PromQL查询语句"
        #     - "查询每个namespace下的Pod数量"
        #
        #     Args:
        #         ctx: MCP上下文，用于访问SLS客户端
        #         text: 用于生成查询的自然语言文本
        #         project: SLS项目名称
        #         metricStore: SLS时序库名称
        #         regionId: 阿里云区域ID
        #
        #     Returns:
        #         生成的PromQL查询语句
        #     """
        #     try:
        #         providers = ctx.request_context.lifespan_context.get("providers", {})
        #         sls_client_info = providers.get("sls_client", {})
        #         sls_client: SLSClient = sls_client_info.get("client")
        #         if not sls_client:
        #             raise RuntimeError("SLS client not available in lifespan context")
        #         request: CallAiToolsRequest = CallAiToolsRequest()
        #         request.tool_name = "text_to_promql"
        #         request.region_id = regionId
        #         params: dict[str, Any] = {
        #             "project": project,
        #             "metricstore": metricStore,
        #             "sys.query": text,
        #         }
        #         request.params = params
        #         runtime: util_models.RuntimeOptions = util_models.RuntimeOptions()
        #         runtime.read_timeout = 60000
        #         runtime.connect_timeout = 60000
        #         tool_response: CallAiToolsResponse = (
        #             sls_client.call_ai_tools_with_options(
        #                 request=request, headers={}, runtime=runtime
        #             )
        #         )
        #         data = tool_response.body
        #         if "------answer------\n" in data:
        #             data = data.split("------answer------\n")[1]
        #         return data
        #     except Exception as e:
        #         logger.error(f"调用CMS AI工具失败: {e}")
        #         raise

        @self.server.tool()
        @retry(
            stop=stop_after_attempt(2),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        @handle_tea_exception
        def get_cluster_aliyun_prometheus_endpoints(
                ctx: Context,
                clusterId: str = Field(
                    ..., description="Prometheus 实例 ID (ClusterId)"
                ),
                regionId: Optional[str] = Field(
                    None, description="地域 ID，如 cn-hangzhou；默认取运行时配置 REGION_ID"
                ),
        ) -> dict:
            """获取指定 Prometheus 实例的访问端点信息。

            参考阿里云文档 GetPrometheusInstance 接口：获取指定 Prometheus 实例信息，并提取常用访问端点。
            返回字段包含（若存在）：
            - http_api_inter_url / http_api_intra_url
            - remote_read_inter_url / remote_read_intra_url
            - remote_write_inter_url / remote_write_intra_url
            - push_gateway_inter_url / push_gateway_intra_url
            - auth_token（如开启鉴权）
            - product, version, access_type 等概要信息

            Args:
                ctx: MCP上下文，用于访问ARMS客户端
                clusterId: Prometheus 实例 ID (ClusterId)
                regionId: 地域 ID，如 cn-hangzhou；默认取运行时配置 REGION_ID
            """
            # 读取 region 与客户端
            lifespan = ctx.request_context.lifespan_context
            lifespan_config = lifespan.get("config", {})
            reg = regionId or lifespan_config.get("region_id") or "cn-hangzhou"
            providers = lifespan.get("providers", {})
            arms_client_info = providers.get("arms_client", {})
            arms_client = arms_client_info.get("client")
            if not arms_client:
                raise RuntimeError("ARMS client not available in lifespan context")

            # 构造请求并调用
            req = arms_models.GetPrometheusInstanceRequest(
                region_id=reg,
                cluster_id=clusterId,
            )
            runtime = util_models.RuntimeOptions()
            resp = arms_client.get_prometheus_instance_with_options(req, runtime)

            body = resp.body
            data = getattr(body, 'data', None)
            if not data:
                return {
                    "cluster_id": clusterId,
                    "region_id": reg,
                    "message": getattr(body, 'message', None),
                    "code": getattr(body, 'code', None),
                    "endpoints": {},
                }

            # 提取端点
            endpoints = {
                "http_api_inter_url": getattr(data, 'http_api_inter_url', None),
                "http_api_intra_url": getattr(data, 'http_api_intra_url', None),
                # "remote_read_inter_url": getattr(data, 'remote_read_inter_url', None),
                # "remote_read_intra_url": getattr(data, 'remote_read_intra_url', None),
                # "remote_write_inter_url": getattr(data, 'remote_write_inter_url', None),
                # "remote_write_intra_url": getattr(data, 'remote_write_intra_url', None),
                # "push_gateway_inter_url": getattr(data, 'push_gateway_inter_url', None),
                # "push_gateway_intra_url": getattr(data, 'push_gateway_intra_url', None),
            }

            result = {
                # "cluster_id": getattr(data, 'cluster_id', clusterId),
                # "region_id": getattr(data, 'region_id', reg),
                # "cluster_name": getattr(data, 'cluster_name', None),
                # "cluster_type": getattr(data, 'cluster_type', None),
                # "product": getattr(data, 'product', None),
                # "version": getattr(data, 'version', None),
                # "access_type": getattr(data, 'access_type', None),
                "enable_auth_token": getattr(data, 'enable_auth_token', None),
                "auth_token": getattr(data, 'auth_token', None),
                "endpoints": endpoints,
                "request_id": getattr(body, 'request_id', None),
            }
            return result

        @self.server.tool()
        async def execute_prometheus_instant_query(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                prometheus_endpoint: str = Field(
                    ..., description="Prometheus HTTP base endpoint, e.g. https://example.com/api/v1/"
                ),
                query_promql: str = Field(
                    ..., description="PromQL expression"
                ),
                time: Optional[str] = Field(
                    None, description="RFC3339 or unix timestamp (optional)"
                )
        ) -> Dict[str, Any]:
            """执行 Prometheus 瞬时查询 /api/v1/query
            
            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点，例如 https://example.com/api/v1/
                query_promql: PromQL表达式
                time: RFC3339或unix时间戳（可选）
            """
            params = {"query": query_promql}
            if time:
                params["time"] = time
            url = prometheus_endpoint + "/api/v1/query"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()

        @self.server.tool()
        async def execute_prometheus_range_query(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                prometheus_endpoint: str = Field(
                    ..., description="Prometheus HTTP base endpoint, e.g. https://example.com/api/v1/"
                ),
                query_promql: str = Field(
                    ..., description="PromQL expression"
                ),
                start: str = Field(
                    ..., description="range start (rfc3339 or unix)"
                ),
                end: str = Field(
                    ..., description="range end (rfc3339 or unix)"
                ),
                step: str = Field(
                    ..., description="query step, e.g. 30s"
                )
        ) -> Dict[str, Any]:
            """执行 Prometheus 区间查询 /api/v1/query_range
            
            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点，例如 https://example.com/api/v1/
                query_promql: PromQL表达式
                start: 查询开始时间 (rfc3339或unix格式)
                end: 查询结束时间 (rfc3339或unix格式)
                step: 查询步长，例如 30s
            """
            params = {"query": query_promql, "start": start, "end": end, "step": step}
            url = prometheus_endpoint + "/api/v1/query_range"
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()

        @self.server.tool()
        async def list_prometheus_metrics(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                prometheus_endpoint: str = Field(
                    ..., description="Prometheus HTTP base endpoint"
                )
        ) -> List[str]:
            """获取所有指标名 /api/v1/label/__name__/values
            
            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点
            """
            url = prometheus_endpoint + "/api/v1/label/__name__/values"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == "success":
                    return cast(List[str], data.get("data", []))
                return []

        @self.server.tool()
        async def get_prometheus_metric_metadata(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
                prometheus_endpoint: str = Field(
                    ..., description="Prometheus HTTP base endpoint"
                ),
                metric_name: str = Field(
                    ..., description="metric name"
                )
        ) -> List[Dict[str, Any]]:
            """获取指标元数据 /api/v1/metadata?metric=<name>
            
            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
                prometheus_endpoint: Prometheus HTTP基础端点
                metric_name: 指标名称
            """
            url = prometheus_endpoint + "/api/v1/metadata"
            params = {"metric": metric_name}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == "success":
                    meta = data.get("data", {})
                    if isinstance(meta, dict):
                        values = meta.get(metric_name)
                        if isinstance(values, list):
                            return cast(List[Dict[str, Any]], values)
                return []

        # @self.server.tool()
        # @retry(
        #     stop=stop_after_attempt(2),
        #     wait=wait_fixed(1),
        #     retry=retry_if_exception_type(Exception),
        #     reraise=True,
        # )
        # @handle_tea_exception
        # def alibabacloud_prometheus_execute_promql_query(
        #         ctx: Context,
        #         project: str = Field(..., description="sls project name"),
        #         metricStore: str = Field(..., description="sls metric store name"),
        #         query: str = Field(..., description="query"),
        #         fromTimestampInSeconds: int = Field(
        #             ...,
        #             description="from timestamp,unit is second,should be unix timestamp, only number,no other characters",
        #         ),
        #         toTimestampInSeconds: int = Field(
        #             ...,
        #             description="to timestamp,unit is second,should be unix timestamp, only number,no other characters",
        #         ),
        #         regionId: str = Field(
        #             default=...,
        #             description="aliyun region id,region id format like 'xx-xxx',like 'cn-hangzhou'",
        #         ),
        # ) -> dict:
        #     """执行Prometheus指标查询。
        #
        #     ## 功能概述
        #
        #     该工具用于在指定的SLS项目和时序库上执行查询语句，并返回查询结果。查询将在指定的时间范围内执行。
        #     如果上下文没有提到具体的 SQL 语句，必须优先使用 alibabacloud_prometheus_translate_text_to_promql 工具生成查询语句,无论问题有多简单。
        #     如果上下文没有提到具体的时间戳，必须优先使用 sls_get_current_time 工具生成时间戳参数，默认为最近15分钟
        #
        #     ## 使用场景
        #
        #     - 当需要根据特定条件查询日志数据时
        #     - 当需要分析特定时间范围内的日志信息时
        #     - 当需要检索日志中的特定事件或错误时
        #     - 当需要统计日志数据的聚合信息时
        #
        #
        #     ## 查询语法
        #
        #     查询必须使用PromQL有效的查询语法，而非自然语言。
        #
        #     ## 时间范围
        #
        #     查询必须指定时间范围：
        #     - fromTimestampInSeconds: 开始时间戳（秒）
        #     - toTimestampInSeconds: 结束时间戳（秒）
        #     默认为最近15分钟，需要调用 sls_get_current_time 工具获取当前时间
        #
        #     ## 查询示例
        #
        #     - "帮我查询下 job xxx 的采集状态"
        #     - "查一下当前有多少个 Pod"
        #
        #     ## 输出
        #     查询结果为：xxxxx
        #     对应的图示：将 image 中的 URL 连接到图示中，并展示在图示中。
        #
        #     Args:
        #         ctx: MCP上下文，用于访问CMS客户端
        #         project: SLS项目名称
        #         metricStore: SLS日志库名称
        #         query: PromQL查询语句
        #         fromTimestampInSeconds: 查询开始时间戳（秒）
        #         toTimestampInSeconds: 查询结束时间戳（秒）
        #         regionId: 阿里云区域ID
        #
        #     Returns:
        #         查询结果列表，每个元素为一条日志记录
        #     """
        #     spls = CMSSPLContainer()
        #     providers = ctx.request_context.lifespan_context.get("providers", {})
        #     sls_client_info = providers.get("sls_client", {})
        #     sls_client: SLSClient = sls_client_info.get("client")
        #     if not sls_client:
        #         raise RuntimeError("SLS client not available in lifespan context")
        #     # query = spls.get_spl("raw-promql-template").replace("<PROMQL>", query)
        #     print(query)
        #
        #     request: GetLogsRequest = GetLogsRequest(
        #         query=query,
        #         from_=fromTimestampInSeconds,
        #         to=toTimestampInSeconds,
        #     )
        #     runtime: util_models.RuntimeOptions = util_models.RuntimeOptions()
        #     runtime.read_timeout = 60000
        #     runtime.connect_timeout = 60000
        #     response: GetLogsResponse = sls_client.get_logs_with_options(
        #         project, metricStore, request, headers={}, runtime=runtime
        #     )
        #     response_body: List[Dict[str, Any]] = response.body
        #
        #     result = {
        #         "data": response_body,
        #         "message": (
        #             "success"
        #             if response_body
        #             else "Not found data by query,you can try to change the query or time range"
        #         ),
        #     }
        #     print(result)
        #     return result

        class MetricsGuidanceResponse(BaseModel):
            resource_type: str
            matched_files: List[str]
            matched_metrics: List[Dict[str, Any]]

        @self.server.tool()
        async def get_ack_prometheus_metric_guidance(
                ctx: Context,
                resource_type: str = Field(
                    ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
                ),
        ) -> MetricsGuidanceResponse:
            """遍历 ack_metrics_guidance 目录的 JSON，匹配入参 resource_type 的 labels 提示集。
            
            Args:
                ctx: MCP上下文，用于访问生命周期提供者
                resource_type: 资源类型，用于获取相关指标 (cluster, node, pod, namespace, )
            """
            base_dir = os.path.dirname(os.path.abspath(__file__))
            guidance_dir = os.path.join(base_dir, 'ack_metrics_guidance')
            matched_files: List[str] = []
            matched_metrics: List[Dict[str, Any]] = []

            if not os.path.isdir(guidance_dir):
                return MetricsGuidanceResponse(resource_type=resource_type, matched_files=[], matched_metrics=[])

            for name in os.listdir(guidance_dir):
                if not name.endswith('.json'):
                    continue
                fpath = os.path.join(guidance_dir, name)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    logger.warning(f"skip {name}: {e}")
                    continue

                # 约定结构：每个 json 中包含一个 metrics 列表，每项至少包含 labels 与（可选）resource_type/description/promql 示例
                metrics_list = data if isinstance(data, list) else data.get('metrics') if isinstance(data, dict) else []
                if not isinstance(metrics_list, list):
                    continue

                file_matched = False
                for item in metrics_list:
                    if not isinstance(item, dict):
                        continue
                    labels = item.get('labels') or {}
                    item_resource_type = (item.get('resource_type') or labels.get('resource_type') or '').lower()
                    if item_resource_type == resource_type.lower():
                        matched_metrics.append(item)
                        file_matched = True

                if file_matched:
                    matched_files.append(name)

            return MetricsGuidanceResponse(
                resource_type=resource_type,
                matched_files=matched_files,
                matched_metrics=matched_metrics,
            )


# class CMSSPLContainer:
#     def __init__(self):
#         self.spls = {}
#         self.spls[
#             "raw-promql-template"
#         ] = r"""
# .set "sql.session.velox_support_row_constructor_enabled" = 'true';
# .set "sql.session.presto_velox_mix_run_not_check_linked_agg_enabled" = 'true';
# .set "sql.session.presto_velox_mix_run_support_complex_type_enabled" = 'true';
# .set "sql.session.velox_sanity_limit_enabled" = 'false';
# .metricstore with(promql_query='<PROMQL>',range='1m')| extend latest_ts = element_at(__ts__,cardinality(__ts__)), latest_val = element_at(__value__,cardinality(__value__))
# |  stats arr_ts = array_agg(__ts__), arr_val = array_agg(__value__), title_agg = array_agg(json_format(cast(__labels__ as json))), anomalies_score_series = array_agg(array[0.0]), anomalies_type_series = array_agg(array['']), cnt = count(*), latest_ts = array_agg(latest_ts), latest_val = array_agg(latest_val)
# | extend cluster_res = cluster(arr_val,'kmeans') | extend params = concat('{"n_col": ', cast(cnt as varchar), ',"subplot":true}')
# | extend image = series_anomalies_plot(arr_ts, arr_val, anomalies_score_series, anomalies_type_series, title_agg, params)| project title_agg,cnt,latest_ts,latest_val,image
# """
#
#     def get_spl(self, key) -> str:
#         return self.spls.get(key, "Key not found")
