"""ACK Cluster Management Handler."""

from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models


class ACKClusterManagementHandler:
    """Handler for ACK cluster management operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK cluster management handler.
        
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
        
        logger.info("ACK Cluster Management Handler initialized")
    
    def _register_tools(self):
        """Register cluster management related tools."""
        
        @self.server.tool(
            name="describe_task_info",
            description="Query ACK cluster task status and information"
        )
        async def describe_task_info(
            task_id: str,
            cluster_id: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe ACK cluster task information.
            
            Args:
                task_id: Task ID to query
                cluster_id: Cluster ID (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Task information
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
                request = cs20151215_models.DescribeTaskInfoRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_task_info_with_options_async(
                    task_id, request, headers, runtime
                )
                
                return {
                    "task_id": task_id,
                    "cluster_id": cluster_id,
                    "status": response.body.task_detail.state,
                    "created_time": response.body.task_detail.created,
                    "updated_time": response.body.task_detail.updated,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to describe task info: {e}")
                return {
                    "task_id": task_id,
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="create_cluster_diagnosis",
            description="Create cluster diagnosis task for ACK cluster"
        )
        async def create_cluster_diagnosis(
            cluster_id: str,
            diagnosis_type: str = "basic",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create cluster diagnosis task.
            
            Args:
                cluster_id: Target cluster ID
                diagnosis_type: Type of diagnosis to perform
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Diagnosis task information
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
                    type=diagnosis_type
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_diagnosis_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_type": diagnosis_type,
                    "diagnosis_id": response.body.diagnosis_id,
                    "status": "created",
                    "created_time": response.body.created_time,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster diagnosis: {e}")
                return {
                    "cluster_id": cluster_id,
                    "diagnosis_type": diagnosis_type,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="get_cluster_diagnosis_result",
            description="Get cluster diagnosis task result"
        )
        async def get_cluster_diagnosis_result(
            task_id: str,
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster diagnosis result.
            
            Args:
                task_id: Diagnosis task ID
                cluster_id: Cluster ID
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
                    cluster_id, task_id, request, headers, runtime
                )
                
                return {
                    "task_id": task_id,
                    "cluster_id": cluster_id,
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
                    "task_id": task_id,
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }