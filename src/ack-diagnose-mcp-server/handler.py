"""ACK Diagnose Handler - Alibaba Cloud Container Service Diagnosis."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models


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
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": response.body.diagnosis_id,
                    "status": "created",
                    "type": diagnosis_type,
                    "created_time": response.body.created_time,
                    "request_id": response.body.request_id
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
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "status": response.body.status,  # 诊断状态：0/1/2
                    "code": response.body.code,      # 诊断结果代码：0成功/1失败
                    "message": response.body.message, # 诊断状态信息
                    "result": response.body.result,   # 诊断结果
                    "created": response.body.created, # 诊断发起时间
                    "finished": response.body.finished, # 诊断完成时间
                    "target": response.body.target,   # 诊断对象
                    "type": response.body.type,       # 诊断类型
                    "request_id": response.body.request_id
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
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "request_id": response.body.request_id,
                    "code": response.body.code,
                    "is_success": response.body.is_success,
                    "check_items": response.body.check_items,
                    "language": language
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster diagnosis check items: {e}")
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
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