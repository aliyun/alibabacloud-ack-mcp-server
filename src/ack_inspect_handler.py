from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models

try:
    from .models import (
        ErrorModel,
        QueryInspectReportInput,
        QueryInspectReportOutput,
        InspectSummary,
        CheckItemResult,
    )
except ImportError:
    from models import (
        ErrorModel,
        QueryInspectReportInput,
        QueryInspectReportOutput,
        InspectSummary,
        CheckItemResult,
    )


def _serialize_sdk_object(obj):
    """序列化阿里云SDK对象为可JSON序列化的字典."""
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [_serialize_sdk_object(item) for item in obj]

    if isinstance(obj, dict):
        return {key: _serialize_sdk_object(value) for key, value in obj.items()}

    try:
        if hasattr(obj, 'to_map'):
            return obj.to_map()

        if hasattr(obj, '__dict__'):
            return _serialize_sdk_object(obj.__dict__)

        return str(obj)
    except Exception:
        return str(obj)


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    providers = getattr(ctx.request_context, "lifespan_context", {}).get("providers", {})
    factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return factory(region)


class InspectHandler:
    """Handler for ACK inspect report operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)
        self.server.tool(
            name="query_inspect_report",
            description="查询一个ACK集群最近的健康巡检报告"
        )(self.query_inspect_report)
        logger.info("ACK Inspect Handler initialized")

    async def query_inspect_report(
            self,
            ctx: Context,
            cluster_id: str = Field(..., description="需要查询的prometheus所在的集群clusterId"),
            region_id: str = Field(..., description="集群所在的regionId"),
            is_result_exception: bool = Field(True, description="是否只返回异常的结果，默认为true"),
    ) -> QueryInspectReportOutput | Dict[str, Any]:
        """查询一个ACK集群最近的巡检报告"""
        try:
            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, region_id)

            # 1. 先获取巡检报告列表，找到最新的报告
            list_request = cs20151215_models.ListClusterInspectReportsRequest(
                max_results=1  # 只获取最新的一个报告
            )
            runtime = util_models.RuntimeOptions()
            headers = {}

            list_response = await cs_client.list_cluster_inspect_reports_with_options_async(
                cluster_id, list_request, headers, runtime
            )

            if not list_response.body or not list_response.body.reports:
                return {"error": ErrorModel(error_code="NO_INSPECT_REPORT",
                                            error_message="当前没有已生成的巡检报告").model_dump()}

            # 获取最新的报告ID
            latest_report = list_response.body.reports[0]
            report_id = getattr(latest_report, 'report_id', None)
            if not report_id:
                return {"error": ErrorModel(error_code="NO_REPORT_ID", error_message="无法获取巡检报告ID").model_dump()}

            # 2. 获取巡检报告详情
            detail_request = cs20151215_models.GetClusterInspectReportDetailRequest(
                enable_filter=is_result_exception  # 根据参数决定是否只返回异常结果
            )

            detail_response = await cs_client.get_cluster_inspect_report_detail_with_options_async(
                cluster_id, report_id, detail_request, headers, runtime
            )

            if not detail_response.body:
                return {"error": ErrorModel(error_code="NO_DETAIL_RESPONSE",
                                            error_message="无法获取巡检报告详情").model_dump()}

            # 3. 解析响应数据
            body = detail_response.body

            # 构建 summary
            summary_data = getattr(body, 'summary', {})
            summary = InspectSummary(
                errorCount=getattr(summary_data, 'errorCount', 0),
                warnCount=getattr(summary_data, 'warnCount', 0),
                normalCount=getattr(summary_data, 'normalCount', 0),
                adviceCount=getattr(summary_data, 'adviceCount', 0),
                unknownCount=getattr(summary_data, 'unknownCount', 0),
            )

            # 构建 checkItemResults
            check_items = []
            check_item_results = getattr(body, 'checkItemResults', []) or []
            for item in check_item_results:
                check_items.append(CheckItemResult(
                    category=getattr(item, 'category', ''),
                    name=getattr(item, 'name', ''),
                    targetType=getattr(item, 'targetType', ''),
                    targets=getattr(item, 'targets', []) or [],
                    description=getattr(item, 'description', ''),
                    fix=getattr(item, 'fix', ''),
                ))

            return QueryInspectReportOutput(
                report_status=getattr(body, 'status', None),
                report_finish_time=getattr(body, 'endTime', None),
                summary=summary,
                checkItemResults=check_items,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to query inspect report: {e}")
            error_code = "UnknownError"
            if "CLUSTER_NOT_FOUND" in str(e):
                error_code = "CLUSTER_NOT_FOUND"
            elif "NO_RAM_POLICY_AUTH" in str(e):
                error_code = "NO_RAM_POLICY_AUTH"
            elif "NO_INSPECT_REPORT" in str(e):
                error_code = "NO_INSPECT_REPORT"

            return {"error": ErrorModel(error_code=error_code, error_message=str(e)).model_dump()}
