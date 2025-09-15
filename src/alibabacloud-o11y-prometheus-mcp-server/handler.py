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

        @self.server.tool()
        @retry(
            stop=stop_after_attempt(2),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        @handle_tea_exception
        def alibabacloud_prometheus_translate_text_to_promql(
                ctx: Context,
                text: str = Field(
                    ...,
                    description="the natural language text to generate promql",
                ),
                project: str = Field(..., description="sls project name"),
                metricStore: str = Field(..., description="sls metric store name"),
                regionId: str = Field(
                    default=...,
                    description="aliyun region id,region id format like 'xx-xxx',like 'cn-hangzhou'",
                ),
        ) -> str:
            """将自然语言转换为Prometheus PromQL查询语句。

            ## 功能概述

            该工具可以将自然语言描述转换为有效的PromQL查询语句，便于用户使用自然语言表达查询需求。

            ## 使用场景

            - 当用户不熟悉PromQL查询语法时
            - 当需要快速构建复杂查询时
            - 当需要从自然语言描述中提取查询意图时

            ## 使用限制

            - 仅支持生成PromQL查询
            - 生成的是查询语句，而非查询结果
            - 禁止使用sls_execute_query工具执行，两者接口不兼容

            ## 最佳实践

            - 提供清晰简洁的自然语言描述
            - 不要在描述中包含项目或时序库名称
            - 首次生成的查询可能不完全符合要求，可能需要多次尝试

            ## 查询示例

            - "帮我生成 XXX 的PromQL查询语句"
            - "查询每个namespace下的Pod数量"

            Args:
                ctx: MCP上下文，用于访问SLS客户端
                text: 用于生成查询的自然语言文本
                project: SLS项目名称
                metricStore: SLS时序库名称
                regionId: 阿里云区域ID

            Returns:
                生成的PromQL查询语句
            """
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                sls_client_info = providers.get("sls_client", {})
                sls_client: SLSClient = sls_client_info.get("client")
                if not sls_client:
                    raise RuntimeError("SLS client not available in lifespan context")
                request: CallAiToolsRequest = CallAiToolsRequest()
                request.tool_name = "text_to_promql"
                request.region_id = regionId
                params: dict[str, Any] = {
                    "project": project,
                    "metricstore": metricStore,
                    "sys.query": text,
                }
                request.params = params
                runtime: util_models.RuntimeOptions = util_models.RuntimeOptions()
                runtime.read_timeout = 60000
                runtime.connect_timeout = 60000
                tool_response: CallAiToolsResponse = (
                    sls_client.call_ai_tools_with_options(
                        request=request, headers={}, runtime=runtime
                    )
                )
                data = tool_response.body
                if "------answer------\n" in data:
                    data = data.split("------answer------\n")[1]
                return data
            except Exception as e:
                logger.error(f"调用CMS AI工具失败: {e}")
                raise

        @self.server.tool()
        @retry(
            stop=stop_after_attempt(2),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        @handle_tea_exception
        def alibabacloud_prometheus_execute_promql_query(
                ctx: Context,
                project: str = Field(..., description="sls project name"),
                metricStore: str = Field(..., description="sls metric store name"),
                query: str = Field(..., description="query"),
                fromTimestampInSeconds: int = Field(
                    ...,
                    description="from timestamp,unit is second,should be unix timestamp, only number,no other characters",
                ),
                toTimestampInSeconds: int = Field(
                    ...,
                    description="to timestamp,unit is second,should be unix timestamp, only number,no other characters",
                ),
                regionId: str = Field(
                    default=...,
                    description="aliyun region id,region id format like 'xx-xxx',like 'cn-hangzhou'",
                ),
        ) -> dict:
            """执行Prometheus指标查询。

            ## 功能概述

            该工具用于在指定的SLS项目和时序库上执行查询语句，并返回查询结果。查询将在指定的时间范围内执行。
            如果上下文没有提到具体的 SQL 语句，必须优先使用 alibabacloud_prometheus_translate_text_to_promql 工具生成查询语句,无论问题有多简单。
            如果上下文没有提到具体的时间戳，必须优先使用 sls_get_current_time 工具生成时间戳参数，默认为最近15分钟

            ## 使用场景

            - 当需要根据特定条件查询日志数据时
            - 当需要分析特定时间范围内的日志信息时
            - 当需要检索日志中的特定事件或错误时
            - 当需要统计日志数据的聚合信息时


            ## 查询语法

            查询必须使用PromQL有效的查询语法，而非自然语言。

            ## 时间范围

            查询必须指定时间范围：
            - fromTimestampInSeconds: 开始时间戳（秒）
            - toTimestampInSeconds: 结束时间戳（秒）
            默认为最近15分钟，需要调用 sls_get_current_time 工具获取当前时间

            ## 查询示例

            - "帮我查询下 job xxx 的采集状态"
            - "查一下当前有多少个 Pod"

            ## 输出
            查询结果为：xxxxx
            对应的图示：将 image 中的 URL 连接到图示中，并展示在图示中。

            Args:
                ctx: MCP上下文，用于访问CMS客户端
                project: SLS项目名称
                metricStore: SLS日志库名称
                query: PromQL查询语句
                fromTimestampInSeconds: 查询开始时间戳（秒）
                toTimestampInSeconds: 查询结束时间戳（秒）
                regionId: 阿里云区域ID

            Returns:
                查询结果列表，每个元素为一条日志记录
            """
            spls = CMSSPLContainer()
            providers = ctx.request_context.lifespan_context.get("providers", {})
            sls_client_info = providers.get("sls_client", {})
            sls_client: SLSClient = sls_client_info.get("client")
            if not sls_client:
                raise RuntimeError("SLS client not available in lifespan context")
            query = spls.get_spl("raw-promql-template").replace("<PROMQL>", query)
            print(query)

            request: GetLogsRequest = GetLogsRequest(
                query=query,
                from_=fromTimestampInSeconds,
                to=toTimestampInSeconds,
            )
            runtime: util_models.RuntimeOptions = util_models.RuntimeOptions()
            runtime.read_timeout = 60000
            runtime.connect_timeout = 60000
            response: GetLogsResponse = sls_client.get_logs_with_options(
                project, metricStore, request, headers={}, runtime=runtime
            )
            response_body: List[Dict[str, Any]] = response.body

            result = {
                "data": response_body,
                "message": (
                    "success"
                    if response_body
                    else "Not found data by query,you can try to change the query or time range"
                ),
            }
            print(result)
            return result


class CMSSPLContainer:
    def __init__(self):
        self.spls = {}
        self.spls[
            "raw-promql-template"
        ] = r"""
.set "sql.session.velox_support_row_constructor_enabled" = 'true';
.set "sql.session.presto_velox_mix_run_not_check_linked_agg_enabled" = 'true';
.set "sql.session.presto_velox_mix_run_support_complex_type_enabled" = 'true';
.set "sql.session.velox_sanity_limit_enabled" = 'false';
.metricstore with(promql_query='<PROMQL>',range='1m')| extend latest_ts = element_at(__ts__,cardinality(__ts__)), latest_val = element_at(__value__,cardinality(__value__))
|  stats arr_ts = array_agg(__ts__), arr_val = array_agg(__value__), title_agg = array_agg(json_format(cast(__labels__ as json))), anomalies_score_series = array_agg(array[0.0]), anomalies_type_series = array_agg(array['']), cnt = count(*), latest_ts = array_agg(latest_ts), latest_val = array_agg(latest_val)
| extend cluster_res = cluster(arr_val,'kmeans') | extend params = concat('{"n_col": ', cast(cnt as varchar), ',"subplot":true}')
| extend image = series_anomalies_plot(arr_ts, arr_val, anomalies_score_series, anomalies_type_series, title_agg, params)| project title_agg,cnt,latest_ts,latest_val,image
"""

    def get_spl(self, key) -> str:
        return self.spls.get(key, "Key not found")
