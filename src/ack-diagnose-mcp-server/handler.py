"""ACK Diagnose Handler - Alibaba Cloud Container Service Diagnosis."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
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


class ACKDiagnoseHandler:
    """Handler for ACK cluster diagnosis and inspection operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK diagnose handler.
        
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
        
        logger.info("ACK Diagnose Handler initialized")
    
    def _register_tools(self):
        """Register cluster diagnosis and inspection related tools."""
        
        # Cluster Diagnosis Tools
        @self.server.tool(
            name="create_cluster_diagnosis",
            description="Create a cluster diagnosis task for ACK cluster"
        )
        async def create_cluster_diagnosis(
            cluster_id: str,
            diagnosis_type: Optional[str] = "cluster",
            target: Optional[Dict[str, Any]] = None,
            ctx: Context = None,
        ) -> Dict[str, Any]:
            """Create cluster diagnosis task.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_type: Type of diagnosis (node, ingress, cluster, memory, pod, service, network)
                target: Target specification for diagnosis
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Diagnosis task creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.CreateClusterDiagnosisRequest(
                    type=diagnosis_type,
                    target=target
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_diagnosis_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": getattr(response.body, 'diagnosis_id', None) if response.body else None,
                    "status": "created",
                    "type": diagnosis_type,
                    "created_time": getattr(response.body, 'created_time', None) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster diagnosis: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_diagnosis_result",
            description="Get cluster diagnosis result"
        )
        async def get_cluster_diagnosis_result(
            cluster_id: str,
            diagnosis_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster diagnosis result.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_id: Diagnosis task ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Diagnosis result
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterDiagnosisResultRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_diagnosis_result_with_options_async(
                    cluster_id, diagnosis_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "status": getattr(response.body, 'status', None) if response.body else None,  # 诊断状态：0/1/2
                    "code": getattr(response.body, 'code', None) if response.body else None,      # 诊断结果代码：0成功/1失败
                    "message": getattr(response.body, 'message', None) if response.body else None, # 诊断状态信息
                    "result": _serialize_sdk_object(getattr(response.body, 'result', None)) if response.body else None,   # 诊断结果
                    "created": getattr(response.body, 'created', None) if response.body else None, # 诊断发起时间
                    "finished": getattr(response.body, 'finished', None) if response.body else None, # 诊断完成时间
                    "target": _serialize_sdk_object(getattr(response.body, 'target', None)) if response.body else None,   # 诊断对象
                    "type": getattr(response.body, 'type', None) if response.body else None,       # 诊断类型
                    "response": response_data,
                    "request_id": getattr(response.body, 'request_id', None) if response.body else None
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster diagnosis result: {e}")
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="get_cluster_diagnosis_check_items",
            description="Get cluster diagnosis check items"
        )
        async def get_cluster_diagnosis_check_items(
            cluster_id: str,
            diagnosis_id: str,
            language: Optional[str] = "zh_CN",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster diagnosis check items.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_id: Diagnosis ID
                language: Language for check items (zh_CN, en)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Available diagnosis check items
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterDiagnosisCheckItemsRequest(
                    language=language
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_diagnosis_check_items_with_options_async(
                    cluster_id, diagnosis_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "language": language,
                    "check_items": _serialize_sdk_object(getattr(response.body, 'check_items', None)) if response.body else [],
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster diagnosis check items: {e}")
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "language": language,
                    "error": str(e),
                    "status": "error"
                }
        
        # Cluster Inspection Tools
        @self.server.tool(
            name="list_cluster_inspect_reports",
            description="Get cluster inspection reports list"
        )
        async def list_cluster_inspect_reports(
            cluster_id: str,
            next_token: Optional[str] = None,
            max_results: Optional[int] = 20,
            ctx: Context = None,
        ) -> Dict[str, Any]:
            """List cluster inspection reports.
            
            Args:
                cluster_id: Target cluster ID
                next_token: Pagination token for next page
                max_results: Maximum number of results to return (max 50)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of inspection reports
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.ListClusterInspectReportsRequest(
                    next_token=next_token,
                    max_results=max_results
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.list_cluster_inspect_reports_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "reports": response.body.reports,
                    "next_token": response.body.next_token,
                    "max_results": max_results,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to list cluster inspect reports: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="get_cluster_inspection_result",
            description="Get cluster inspection result"
        )
        async def get_cluster_inspection_result(
            cluster_id: str,
            inspection_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster inspection result.
            
            Args:
                cluster_id: Target cluster ID
                inspection_id: Inspection task ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Inspection result
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterInspectionResultRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_inspection_result_with_options_async(
                    cluster_id, inspection_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "status": getattr(response.body, 'status', None) if response.body else None,
                    "code": getattr(response.body, 'code', None) if response.body else None,
                    "message": getattr(response.body, 'message', None) if response.body else None,
                    "result": _serialize_sdk_object(getattr(response.body, 'result', None)) if response.body else None,
                    "created": getattr(response.body, 'created', None) if response.body else None,
                    "finished": getattr(response.body, 'finished', None) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster inspection result: {e}")
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="get_cluster_inspection_check_items",
            description="Get cluster inspection check items"
        )
        async def get_cluster_inspection_check_items(
            cluster_id: str,
            inspection_id: str,
            language: Optional[str] = "zh_CN",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster inspection check items.
            
            Args:
                cluster_id: Target cluster ID
                inspection_id: Inspection ID
                language: Language for check items (zh_CN, en)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Available inspection check items
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterInspectionCheckItemsRequest(
                    language=language
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_inspection_check_items_with_options_async(
                    cluster_id, inspection_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "language": language,
                    "check_items": _serialize_sdk_object(getattr(response.body, 'check_items', None)) if response.body else [],
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster inspection check items: {e}")
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": inspection_id,
                    "language": language,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="create_cluster_inspection",
            description="Create a cluster inspection task for ACK cluster"
        )
        async def create_cluster_inspection(
            cluster_id: str,
            inspection_type: Optional[str] = "cluster",
            target: Optional[Dict[str, Any]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create cluster inspection task.
            
            Args:
                cluster_id: Target cluster ID
                inspection_type: Type of inspection (node, ingress, cluster, memory, pod, service, network)
                target: Target specification for inspection
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Inspection task creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.CreateClusterInspectionRequest(
                    type=inspection_type,
                    target=target
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_inspection_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "inspection_id": getattr(response.body, 'inspection_id', None) if response.body else None,
                    "status": "created",
                    "type": inspection_type,
                    "created_time": getattr(response.body, 'created_time', None) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster inspection: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_inspect_report_detail",
            description="Get cluster inspection report detail"
        )
        async def get_cluster_inspect_report_detail(
            cluster_id: str,
            report_id: str,
            language: Optional[str] = "zh_CN",
            category: Optional[str] = None,
            target_type: Optional[str] = None,
            level: Optional[str] = None,
            enable_filter: Optional[bool] = False,
            next_token: Optional[str] = None,
            max_results: Optional[int] = 20,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster inspection report detail.
            
            Args:
                cluster_id: Target cluster ID
                report_id: Inspection report ID
                language: Query language (zh_CN, en_US)
                category: Inspection category (security, performance, stability, limitation, cost)
                target_type: Target type filter
                level: Level filter (advice, warning, error, critical)
                enable_filter: Only return abnormal items when True
                next_token: Pagination token
                max_results: Maximum results per page (max 50)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Detailed inspection report
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterInspectReportDetailRequest(
                    language=language,
                    category=category,
                    target_type=target_type,
                    level=level,
                    enable_filter=enable_filter,
                    next_token=next_token,
                    max_results=max_results
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_inspect_report_detail_with_options_async(
                    cluster_id, report_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "report_id": report_id,
                    "request_id": response.body.request_id,
                    "next_token": response.body.next_token,
                    "start_time": response.body.start_time,
                    "end_time": response.body.end_time,
                    "status": response.body.status,
                    "summary": response.body.summary,
                    "check_item_results": response.body.check_item_results
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster inspect report detail: {e}")
                return {
                    "cluster_id": cluster_id,
                    "report_id": report_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="run_cluster_inspect",
            description="Run cluster inspection to create inspection report"
        )
        async def run_cluster_inspect(
            cluster_id: str,
            client_token: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Run cluster inspection.
            
            Args:
                cluster_id: Target cluster ID
                client_token: Idempotent token (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Inspection run result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.RunClusterInspectRequest(
                    client_token=client_token
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.run_cluster_inspect_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "report_id": response.body.report_id,    # 巡检报告 ID
                    "task_id": response.body.task_id,        # 巡检任务 ID
                    "request_id": response.body.request_id,  # 请求 ID
                    "status": "started"
                }
                
            except Exception as e:
                logger.error(f"Failed to run cluster inspect: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_diagnosis_report",
            description="Get cluster diagnosis report"
        )
        async def get_cluster_diagnosis_report(
            cluster_id: str,
            diagnosis_id: str,
            report_type: Optional[str] = "summary",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster diagnosis report.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_id: Diagnosis task ID
                report_type: Type of report (summary, detail, pdf)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Diagnosis report
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.GetClusterDiagnosisReportRequest(
                    report_type=report_type
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_diagnosis_report_with_options_async(
                    cluster_id, diagnosis_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "report_type": report_type,
                    "report": _serialize_sdk_object(getattr(response.body, 'report', None)) if response.body else None,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster diagnosis report: {e}")
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "report_type": report_type,
                    "error": str(e),
                    "status": "error"
                }
        
        # Cluster Inspection Configuration Tools
        @self.server.tool(
            name="create_cluster_inspect_config",
            description="Create cluster inspection configuration"
        )
        async def create_cluster_inspect_config(
            cluster_id: str,
            enabled: bool,
            recurrence: str,
            disabled_check_items: Optional[List[str]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                enabled: Whether to enable inspection
                recurrence: Inspection schedule using RFC5545 syntax (e.g., "FREQ=DAILY;BYHOUR=10;BYMINUTE=15")
                disabled_check_items: List of disabled check items
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Configuration creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.CreateClusterInspectConfigRequest(
                    enabled=enabled,
                    recurrence=recurrence,
                    disabled_check_items=disabled_check_items or []
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_inspect_config_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "status": "created"
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster inspect config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="update_cluster_inspect_config",
            description="Update cluster inspection configuration"
        )
        async def update_cluster_inspect_config(
            cluster_id: str,
            enabled: Optional[bool] = None,
            schedule_time: Optional[str] = None,
            disabled_check_items: Optional[List[str]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Update cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                enabled: Whether to enable inspection
                schedule_time: Inspection schedule using RFC5545 syntax
                disabled_check_items: List of disabled check items
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Configuration update result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.UpdateClusterInspectConfigRequest(
                    enabled=enabled,
                    schedule_time=schedule_time,
                    disabled_check_items=disabled_check_items
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.update_cluster_inspect_config_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "status": "updated"
                }
                
            except Exception as e:
                logger.error(f"Failed to update cluster inspect config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_inspect_config",
            description="Get cluster inspection configuration"
        )
        async def get_cluster_inspect_config(
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Inspection configuration
            """
            # Get CS client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.get_cluster_inspect_config_with_options_async(
                    cluster_id, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "enabled": response.body.enabled,
                    "recurrence": response.body.recurrence,
                    "disabled_check_items": response.body.disabled_check_items
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster inspect config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }