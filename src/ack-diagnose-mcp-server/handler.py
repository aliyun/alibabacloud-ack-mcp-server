"""ACK Diagnose Handler - Alibaba Cloud Container Service Diagnosis."""

from typing import Dict, Any, Optional, List
from mcp.server.fastmcp import FastMCP
from loguru import logger
from alibabacloud_cs20151215.client import Client as CS20151215Client
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient


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
        self.cs_client = None
        
        # Initialize Alibaba Cloud CS client
        self._init_cs_client()
        
        # Register tools
        self._register_tools()
        
        logger.info("ACK Diagnose Handler initialized")
    
    def _init_cs_client(self):
        """Initialize Alibaba Cloud Container Service client."""
        try:
            # Use credential client for secure authentication
            credential = CredentialClient()
            config = open_api_models.Config(credential=credential)
            
            # Set endpoint based on region
            region = self.settings.get("region_id", "cn-hangzhou")
            config.endpoint = f'cs.{region}.aliyuncs.com'
            
            self.cs_client = CS20151215Client(config)
            logger.info(f"CS client initialized for region: {region}")
        except Exception as e:
            logger.error(f"Failed to initialize CS client: {e}")
            self.cs_client = None
    
    def _register_tools(self):
        """Register cluster diagnosis and inspection related tools."""
        
        # Cluster Diagnosis Tools
        @self.server.tool(
            name="create_cluster_diagnosis",
            description="Create a cluster diagnosis task for ACK cluster"
        )
        async def create_cluster_diagnosis(
            cluster_id: str,
            diagnosis_type: Optional[str] = "all",
            target: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """Create cluster diagnosis task.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_type: Type of diagnosis (all, node, pod, network, etc.)
                target: Target specification for diagnosis
                
            Returns:
                Diagnosis task creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.CreateClusterDiagnosisRequest(
                    type=diagnosis_type,
                    target=target
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.create_cluster_diagnosis_with_options_async(
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
            diagnosis_id: str
        ) -> Dict[str, Any]:
            """Get cluster diagnosis result.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_id: Diagnosis task ID
                
            Returns:
                Diagnosis result
            """
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.GetClusterDiagnosisResultRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.get_cluster_diagnosis_result_with_options_async(
                    cluster_id, diagnosis_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_id": diagnosis_id,
                    "status": response.body.phase,
                    "result": response.body.result,
                    "created_time": response.body.created_time,
                    "finished_time": response.body.finished_time,
                    "progress": response.body.progress,
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
            diagnosis_type: Optional[str] = "all",
            lang: Optional[str] = "zh"
        ) -> Dict[str, Any]:
            """Get cluster diagnosis check items.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_type: Type of diagnosis checks
                lang: Language for check items (zh, en)
                
            Returns:
                Available diagnosis check items
            """
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.GetClusterDiagnosisCheckItemsRequest(
                    type=diagnosis_type,
                    lang=lang
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.get_cluster_diagnosis_check_items_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "check_items": response.body.check_items,
                    "type": diagnosis_type,
                    "lang": lang,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster diagnosis check items: {e}")
                return {
                    "cluster_id": cluster_id,
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
            page_num: Optional[int] = 1,
            page_size: Optional[int] = 10
        ) -> Dict[str, Any]:
            """List cluster inspection reports.
            
            Args:
                cluster_id: Target cluster ID
                page_num: Page number for pagination
                page_size: Page size for pagination
                
            Returns:
                List of inspection reports
            """
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.ListClusterInspectReportsRequest(
                    page_num=page_num,
                    page_size=page_size
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.list_cluster_inspect_reports_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "reports": response.body.reports,
                    "page_num": page_num,
                    "page_size": page_size,
                    "total_count": response.body.total_count,
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
            report_id: str
        ) -> Dict[str, Any]:
            """Get cluster inspection report detail.
            
            Args:
                cluster_id: Target cluster ID
                report_id: Inspection report ID
                
            Returns:
                Detailed inspection report
            """
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.GetClusterInspectReportDetailRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.get_cluster_inspect_report_detail_with_options_async(
                    cluster_id, report_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "report_id": report_id,
                    "report_detail": response.body.report,
                    "status": response.body.status,
                    "created_time": response.body.created_time,
                    "finished_time": response.body.finished_time,
                    "request_id": response.body.request_id
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
            inspect_type: Optional[str] = "all"
        ) -> Dict[str, Any]:
            """Run cluster inspection.
            
            Args:
                cluster_id: Target cluster ID
                inspect_type: Type of inspection (all, security, performance, etc.)
                
            Returns:
                Inspection run result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.RunClusterInspectRequest(
                    type=inspect_type
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.run_cluster_inspect_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "inspect_id": response.body.inspect_id,
                    "status": "started",
                    "type": inspect_type,
                    "created_time": response.body.created_time,
                    "request_id": response.body.request_id
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
            inspect_config: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Create cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                inspect_config: Inspection configuration
                
            Returns:
                Configuration creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.CreateClusterInspectConfigRequest(
                    config=inspect_config
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.create_cluster_inspect_config_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "config_id": response.body.config_id,
                    "status": "created",
                    "request_id": response.body.request_id
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
            config_id: str,
            inspect_config: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Update cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                config_id: Configuration ID
                inspect_config: Updated inspection configuration
                
            Returns:
                Configuration update result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.UpdateClusterInspectConfigRequest(
                    config=inspect_config
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.update_cluster_inspect_config_with_options_async(
                    cluster_id, config_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "config_id": config_id,
                    "status": "updated",
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to update cluster inspect config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "config_id": config_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_inspect_config",
            description="Get cluster inspection configuration"
        )
        async def get_cluster_inspect_config(
            cluster_id: str,
            config_id: str
        ) -> Dict[str, Any]:
            """Get cluster inspection configuration.
            
            Args:
                cluster_id: Target cluster ID
                config_id: Configuration ID
                
            Returns:
                Inspection configuration
            """
            if not self.cs_client:
                return {"error": "CS client not initialized"}
            
            try:
                request = cs20151215_models.GetClusterInspectConfigRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await self.cs_client.get_cluster_inspect_config_with_options_async(
                    cluster_id, config_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "config_id": config_id,
                    "config": response.body.config,
                    "status": response.body.status,
                    "created_time": response.body.created_time,
                    "updated_time": response.body.updated_time,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster inspect config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "config_id": config_id,
                    "error": str(e),
                    "status": "error"
                }