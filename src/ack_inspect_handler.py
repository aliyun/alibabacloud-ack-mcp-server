from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
import asyncio

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
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return factory(region, config)


class InspectHandler:
    """Handler for ACK inspect report operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        if server is None:
            return
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)
        self.server.tool(
            name="query_inspect_report",
            description="即可生成并查询一个ACK集群最近的健康巡检报告"
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
            runtime = util_models.RuntimeOptions()
            headers = {}

            # 1. 即刻创建集群巡检报告
            create_request = cs20151215_models.RunClusterInspectRequest()
            create_response = await cs_client.run_cluster_inspect_with_options_async(
                cluster_id, create_request, headers, runtime
            )
            if not create_response.body or not create_response.body.report_id:
                return {"error": ErrorModel(error_code="ERROR_CREATE_INSPECT_REPORT",
                                    error_message="创建巡检报告失败").model_dump()}

            # 等待1秒钟让报告开始生成
            await asyncio.sleep(1)

            # 2. 先获取巡检报告列表，找到最新的报告
            list_request = cs20151215_models.ListClusterInspectReportsRequest(
                max_results=1  # 只获取最新的一个报告
            )

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

            # 3. 等待巡检报告完成
            result = await self.wait_for_inspect_completion(
                ctx, cluster_id, region_id, report_id, is_result_exception
            )
            return result

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

    async def wait_for_inspect_completion(
            self,
            ctx: Context,
            cluster_id: str,
            region_id: str,
            report_id: str,
            is_result_exception: bool,
            max_wait_time: int = 300,  # 最大等待时间（秒）
            poll_interval: int = 5    # 轮询间隔（秒）
    ) -> QueryInspectReportOutput | Dict[str, Any]:
        """循环获取巡检报告结果，直到巡检结束
        
        Args:
            ctx: FastMCP context
            cluster_id: 集群ID
            region_id: 区域ID
            report_id: 巡检报告ID
            is_result_exception: 是否只返回异常结果
            max_wait_time: 最大等待时间（秒），默认5分钟
            poll_interval: 轮询间隔（秒），默认10秒
            
        Returns:
            巡检报告结果，当状态为completed或failed时返回最终结果
        """
        from datetime import datetime, timedelta
        start_time = datetime.now()
        max_end_time = start_time + timedelta(seconds=max_wait_time)
        
        # 如果是测试环境，使用更短的轮询间隔
        if self.settings.get("test_mode", False):
            poll_interval = 0.1  # 100ms 用于测试
            max_wait_time = 10  # 10秒最大等待时间用于测试
        
        logger.info(f"开始等待巡检报告 {report_id} 完成，最大等待时间: {max_wait_time}秒")
        
        while datetime.now() < max_end_time:
            try:
                # 获取当前巡检状态
                result = await self.get_inspect_report_detail(
                    ctx, cluster_id, region_id, report_id, is_result_exception
                )
                
                # 检查是否有错误
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"获取巡检报告结果时出错: {result['error']}")
                    return result
                
                # 检查状态
                status = result.report_status if hasattr(result, 'report_status') else None
                
                logger.info(f"巡检报告 {report_id} 当前状态: {status}")
                
                # 检查是否完成
                if status == "completed":
                    logger.info(f"巡检报告 {report_id} 已完成")
                    return result
                elif status == "failed":
                    logger.warning(f"巡检报告 {report_id} 失败")
                    return result
                elif status in ["running", "created"]:
                    # 继续等待
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    remaining_time = max_wait_time - elapsed_time
                    logger.info(f"巡检报告 {report_id} 仍在进行中，已等待 {elapsed_time:.1f}秒，剩余时间 {remaining_time:.1f}秒")
                    
                    # 等待指定间隔后继续轮询
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    # 未知状态，继续等待
                    logger.warning(f"巡检报告 {report_id} 状态未知: {status}，继续等待")
                    await asyncio.sleep(poll_interval)
                    continue
                    
            except Exception as e:
                logger.error(f"轮询巡检报告结果时出错: {e}")
                # 如果是网络错误等临时问题，继续重试
                await asyncio.sleep(poll_interval)
                continue
        
        # 超时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        error_message = f"巡检报告 {report_id} 在 {elapsed_time:.1f}秒内未完成，已超时"
        logger.warning(error_message)
        
        return {
            "error": ErrorModel(
                error_code="INSPECT_TIMEOUT",
                error_message=error_message
            ).model_dump()
        }

    async def get_inspect_report_detail(
            self,
            ctx: Context,
            cluster_id: str,
            region_id: str,
            report_id: str,
            is_result_exception: bool
    ) -> QueryInspectReportOutput | Dict[str, Any]:
        """获取巡检报告详情"""
        try:
            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, region_id)
            runtime = util_models.RuntimeOptions()
            headers = {}

            # 获取巡检报告详情
            detail_request = cs20151215_models.GetClusterInspectReportDetailRequest(
                enable_filter=is_result_exception  # 根据参数决定是否只返回异常结果
            )

            detail_response = await cs_client.get_cluster_inspect_report_detail_with_options_async(
                cluster_id, report_id, detail_request, headers, runtime
            )

            if not detail_response.body:
                return {"error": ErrorModel(error_code="NO_DETAIL_RESPONSE",
                                            error_message="无法获取巡检报告详情").model_dump()}

            # 解析响应数据
            body = detail_response.body

            # 构建 summary
            summary_data = getattr(body, 'summary', {})
            summary = InspectSummary(
                errorCount=getattr(summary_data, 'error_count', 0),
                warnCount=getattr(summary_data, 'warn_count', 0),
                normalCount=getattr(summary_data, 'normal_count', 0),
            )

            # 构建 checkItemResults
            check_items = []
            check_item_results = getattr(body, 'check_item_results', []) or []
            for item in check_item_results:
                check_items.append(CheckItemResult(
                    category=getattr(item, 'category', ''),
                    checkItemUid=getattr(item, 'check_item_uid', ''),
                    level=getattr(item, 'level', ''),
                    name=getattr(item, 'name', ''),
                    targetType=getattr(item, 'target_type', ''),
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
            logger.error(f"Failed to get inspect report detail: {e}")
            error_code = "UnknownError"
            if "CLUSTER_NOT_FOUND" in str(e):
                error_code = "CLUSTER_NOT_FOUND"
            elif "NO_RAM_POLICY_AUTH" in str(e):
                error_code = "NO_RAM_POLICY_AUTH"

            return {"error": ErrorModel(error_code=error_code, error_message=str(e)).model_dump()}
