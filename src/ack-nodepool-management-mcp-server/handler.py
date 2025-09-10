"""ACK NodePool Management Handler."""

from typing import Dict, Any, Optional, List
from mcp.server.fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models


class ACKNodePoolManagementHandler:
    """Handler for ACK node pool management operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK node pool management handler.
        
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
        
        logger.info("ACK NodePool Management Handler initialized")
    
    def _register_tools(self):
        """Register node pool management related tools."""
        
        @self.server.tool(
            name="scale_nodepool",
            description="Scale ACK cluster node pool"
        )
        async def scale_nodepool(
            cluster_id: str,
            nodepool_id: str,
            desired_size: int,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Scale node pool in ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to scale
                desired_size: Desired number of nodes
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Scale operation result
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
                request = cs20151215_models.ScaleClusterNodePoolRequest(
                    count=desired_size
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.scale_cluster_node_pool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "desired_size": desired_size,
                    "task_id": response.body.task_id,
                    "status": "scaling",
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to scale node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "desired_size": desired_size,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="remove_nodepool_nodes",
            description="Remove nodes from ACK cluster node pool"
        )
        async def remove_nodepool_nodes(
            cluster_id: str,
            nodepool_id: str,
            node_names: List[str],
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Remove specific nodes from node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID
                node_names: List of node names to remove
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Remove operation result
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
                request = cs20151215_models.RemoveClusterNodesRequest(
                    drain_node=True,
                    nodes=node_names
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.remove_cluster_nodes_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "node_names": node_names,
                    "task_id": response.body.task_id,
                    "status": "removing",
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to remove nodes: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "node_names": node_names,
                    "error": str(e),
                    "status": "failed"
                }