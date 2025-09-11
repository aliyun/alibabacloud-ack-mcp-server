"""ACK NodePool Management Handler."""

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
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "desired_size": desired_size,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "scaling",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
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
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "node_names": node_names,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "removing",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
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