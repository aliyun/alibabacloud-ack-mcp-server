"""
定义所有与阿里云可观测性相关的 MCP 工具。
"""

import time
from typing import Annotated, Any, Dict, List, Optional

from app.config import get_logger
from app.context import app_context
from app.models import ErrorContext
from app.services.context_service import ContextService
from app.services.observability_service import ObservabilityService
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

logger = get_logger()


def register_observability_tools(mcp_server: FastMCP, obs_svc: ObservabilityService):
    """注册所有可观测性相关的工具到 MCP 服务器。"""

    @mcp_server.tool("cms_translate_text_to_promql")
    async def cms_translate_text_to_promql(
        cluster_id: Annotated[str, Field(description="目标集群的ID。")],
        text: Annotated[str, Field(description="用于生成 PromQL 的自然语言文本。")],
    ) -> str:
        """
        将自然语言文本转换为指定集群的 Prometheus PromQL 查询语句。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})
        context_service = ContextService(credentials)
        obs_context = await context_service.get_observability_context(cluster_id)

        if isinstance(obs_context, ErrorContext):
            raise ToolError(
                f"Failed to get observability context: {obs_context.message}"
            )

        logger.info(
            f"Using observability context for project: {obs_context.arms_project}, metric_store: {obs_context.arms_metric_store}"
        )

        final_creds = credentials.copy()
        final_creds["region"] = obs_context.region_id

        return obs_svc.translate_text_to_promql(
            text=text,
            project=obs_context.arms_project,
            metric_store=obs_context.arms_metric_store,
            credentials=final_creds,
        )

    @mcp_server.tool("cms_execute_promql_query")
    async def cms_execute_promql_query(
        cluster_id: Annotated[str, Field(description="目标集群的ID。")],
        query: Annotated[str, Field(description="要执行的 PromQL 查询语句。")],
        from_timestamp: Annotated[
            Optional[int],
            Field(description="查询开始时间戳（秒，Unix Timestamp）。默认为一小时前。"),
        ] = None,
        to_timestamp: Annotated[
            Optional[int],
            Field(description="查询结束时间戳（秒，Unix Timestamp）。默认为当前时间。"),
        ] = None,
    ) -> List[Dict[str, Any]]:
        """
        在指定集群的 ARMS 指标库中执行 PromQL 查询并返回结果。

        Returns:
            一个包含查询结果的字典列表。

        Raises:
            ToolError: 如果获取可观测性上下文或执行查询失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})
        context_service = ContextService(credentials)
        obs_context = await context_service.get_observability_context(cluster_id)

        if isinstance(obs_context, ErrorContext):
            raise ToolError(
                f"Failed to get observability context: {obs_context.message}"
            )

        logger.info(
            f"Executing PromQL query with context for project: {obs_context.arms_project}, metric_store: {obs_context.arms_metric_store}"
        )

        final_creds = credentials.copy()
        final_creds["region"] = obs_context.region_id

        now = int(time.time())
        final_from = from_timestamp if from_timestamp is not None else now - 3600
        final_to = to_timestamp if to_timestamp is not None else now

        try:
            return obs_svc.execute_promql_query(
                project=obs_context.arms_project,
                metric_store=obs_context.arms_metric_store,
                query=query,
                from_timestamp=final_from,
                to_timestamp=final_to,
                credentials=final_creds,
            )
        except Exception as e:
            logger.error(f"Failed to execute PromQL query: {e}", exc_info=True)
            raise ToolError(f"Failed to execute PromQL query: {e}") from e

    @mcp_server.tool("sls_translate_text_to_sql_query")
    async def sls_translate_text_to_sql_query(
        cluster_id: Annotated[str, Field(description="目标集群的ID。")],
        text: Annotated[
            str, Field(description="用于生成 SLS SQL 查询的自然语言文本。")
        ],
        logstore: Annotated[
            Optional[str],
            Field(
                description="可选的日志库名称。如果留空，将自动使用与 cluster_id 关联的默认日志库。除非您需要查询特定的非默认日志库，否则建议不填写此项。"
            ),
        ] = None,
    ) -> str:
        """
        将自然语言文本转换为指定集群日志库的 SLS Log-SQL 查询语句。

        Returns:
            生成的 Log-SQL 查询字符串。

        Raises:
            ToolError: 如果获取可观测性上下文或转换文本失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})
        context_service = ContextService(credentials)
        obs_context = await context_service.get_observability_context(cluster_id)

        if isinstance(obs_context, ErrorContext):
            raise ToolError(
                f"Failed to get observability context: {obs_context.message}"
            )

        final_logstore = logstore or obs_context.sls_log_store
        logger.info(
            f"Using observability context for project: {obs_context.sls_project}, logstore: {final_logstore}"
        )

        final_creds = credentials.copy()
        final_creds["region"] = obs_context.region_id

        try:
            return obs_svc.translate_text_to_sql(
                text=text,
                project=obs_context.sls_project,
                logstore=final_logstore,
                credentials=final_creds,
            )
        except Exception as e:
            logger.error(f"Failed to translate text to SQL: {e}", exc_info=True)
            raise ToolError(f"Failed to translate text to SQL: {e}") from e

    @mcp_server.tool("sls_execute_sql_query")
    async def sls_execute_sql_query(
        cluster_id: Annotated[str, Field(description="目标集群的ID。")],
        query: Annotated[str, Field(description="要执行的 Log-SQL 查询语句。")],
        logstore: Annotated[
            Optional[str],
            Field(
                description="可选的日志库名称。如果留空，将自动使用与 cluster_id 关联的默认日志库。除非您需要查询特定的非默认日志库，否则建议不填写此项。"
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="返回结果的最大数量，范围1-100，默认100。", ge=1, le=100),
        ] = 100,
        from_timestamp: Annotated[
            Optional[int],
            Field(description="查询开始时间戳（秒，Unix Timestamp）。默认为一小时前。"),
        ] = None,
        to_timestamp: Annotated[
            Optional[int],
            Field(description="查询结束时间戳（秒，Unix Timestamp）。默认为当前时间。"),
        ] = None,
    ) -> List[Dict[str, Any]]:
        """
        在指定集群的 SLS 日志库中执行 Log-SQL 查询并返回结果。

        Returns:
            一个包含查询结果的字典列表。

        Raises:
            ToolError: 如果获取可观测性上下文或执行查询失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})
        context_service = ContextService(credentials)
        obs_context = await context_service.get_observability_context(cluster_id)

        if isinstance(obs_context, ErrorContext):
            raise ToolError(
                f"Failed to get observability context: {obs_context.message}"
            )

        final_logstore = logstore or obs_context.sls_log_store
        logger.info(
            f"Executing SQL query with context for project: {obs_context.sls_project}, logstore: {final_logstore}"
        )

        final_creds = credentials.copy()
        final_creds["region"] = obs_context.region_id

        now = int(time.time())
        final_from = from_timestamp if from_timestamp is not None else now - 3600
        final_to = to_timestamp if to_timestamp is not None else now

        try:
            return obs_svc.execute_sql(
                project=obs_context.sls_project,
                logstore=final_logstore,
                query=query,
                from_timestamp=final_from,
                to_timestamp=final_to,
                limit=limit,
                credentials=final_creds,
            )
        except Exception as e:
            logger.error(f"Failed to execute SQL query: {e}", exc_info=True)
            raise ToolError(f"Failed to execute SQL query: {e}") from e

    @mcp_server.tool("sls_diagnose_query")
    async def sls_diagnose_query(
        cluster_id: Annotated[str, Field(description="目标集群的ID。")],
        query: Annotated[str, Field(description="需要诊断的 SLS 查询语句。")],
        error_message: Annotated[str, Field(description="执行查询时返回的错误信息。")],
    ) -> str:
        """
        当 SLS 查询语句在指定集群的日志库中执行失败时，调用此工具进行诊断。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})
        context_service = ContextService(credentials)
        obs_context = await context_service.get_observability_context(cluster_id)

        if isinstance(obs_context, ErrorContext):
            raise ToolError(
                f"Failed to get observability context: {obs_context.message}"
            )

        logger.info(
            f"Diagnosing query with context for project: {obs_context.sls_project}, logstore: {obs_context.sls_log_store}"
        )

        final_creds = credentials.copy()
        final_creds["region"] = obs_context.region_id

        try:
            return obs_svc.diagnose_query(
                query=query,
                error_message=error_message,
                project=obs_context.sls_project,
                logstore=obs_context.sls_log_store,
                credentials=final_creds,
            )
        except Exception as e:
            logger.error(f"Failed to diagnose query: {e}", exc_info=True)
            raise ToolError(f"Failed to diagnose query: {e}") from e
