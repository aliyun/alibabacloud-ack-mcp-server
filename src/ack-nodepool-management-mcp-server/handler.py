"""ACK NodePool Management Handler."""

from alibabacloud_tea_util.models import RuntimeOptions
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_cs20151215.client import Client as CS20151215Client
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


def _safe_get_response_body(response):
    """安全获取响应对象的body属性."""
    return getattr(response, 'body', None) if response else None


def _safe_get_body_attr(response, attr_name, default=None):
    """安全获取响应body中的指定属性."""
    body = _safe_get_response_body(response)
    return getattr(body, attr_name, default) if body else default


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
            name="describe_cluster_node_pools",
            description="List and query ACK cluster node pools"
        )
        async def describe_cluster_node_pools(
            cluster_id: str,
            nodepool_name: Optional[str] = None,
            container_runtime: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """List node pools in ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_name: Optional node pool name filter
                container_runtime: Optional container runtime filter (e.g., containerd, docker)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of node pools
            """
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client:CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request for describe operation
                request = cs20151215_models.DescribeClusterNodePoolsRequest()
                if nodepool_name:
                    request.nodepool_name = nodepool_name
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                # For GET requests with query parameters, we need to handle them properly
                # According to SDK patterns, nodepool_name should be passed as a query parameter
                # We'll construct the URL with query parameters if needed
                
                response = await cs_client.describe_cluster_node_pools_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_body = _safe_get_response_body(response)
                nodepools_data = _serialize_sdk_object(getattr(response_body, 'nodepools', None)) if response_body and hasattr(response_body, 'nodepools') else []
                
                # Apply client-side filtering if nodepool_name or runtime is specified
                # Since the API doesn't seem to support server-side filtering via query params
                if nodepools_data and isinstance(nodepools_data, list):
                    if nodepool_name:
                        nodepools_data = [
                            pool for pool in nodepools_data 
                            if isinstance(pool, dict) and pool.get('name') == nodepool_name
                        ]
                    
                    if container_runtime:
                        # Filter by container runtime if specified
                        # Check in various possible locations where runtime info might be stored
                        filtered_pools = []
                        for pool in nodepools_data:
                            if isinstance(pool, dict):
                                # Check multiple possible locations for runtime information
                                pool_runtime = None
                                
                                # Check in nodepool_info.runtime
                                nodepool_info = pool.get('nodepool_info', {})
                                if isinstance(nodepool_info, dict):
                                    pool_runtime = nodepool_info.get('runtime')
                                
                                # Check in scaling_group or other locations if not found
                                if not pool_runtime:
                                    scaling_group = pool.get('scaling_group', {})
                                    if isinstance(scaling_group, dict):
                                        pool_runtime = scaling_group.get('runtime')
                                
                                # If runtime matches or no runtime info is available (include it)
                                if not pool_runtime or pool_runtime == container_runtime:
                                    filtered_pools.append(pool)
                        
                        nodepools_data = filtered_pools
                
                return {
                    "cluster_id": cluster_id,
                    "nodepools": nodepools_data,
                    "nodepool_name_filter": nodepool_name,
                    "runtime_filter": container_runtime,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster node pools: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="scale_nodepool",
            description="Scale ACK cluster node pool"
        )
        async def scale_nodepool(
            cluster_id: str,
            nodepool_id: str,
            desired_size: int,
            ctx: Optional[Context] = None
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
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
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
                response_data = _serialize_sdk_object(_safe_get_response_body(response)) or {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "desired_size": desired_size,
                    "task_id": _safe_get_body_attr(response, 'task_id'),
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
            instance_ids: List[str],
            release_node: Optional[bool] = True,
            drain_node: Optional[bool] = True,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Remove specific nodes from node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID
                instance_ids: List of ECS instance IDs to remove
                release_node: Whether to release ECS instances
                drain_node: Whether to drain pods before removal
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Remove operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.RemoveNodePoolNodesRequest(
                    instance_ids=instance_ids,
                    release_node=release_node if release_node is not None else True,
                    drain_node=drain_node if drain_node is not None else True
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.remove_node_pool_nodes_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(_safe_get_response_body(response)) or {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "instance_ids": instance_ids,
                    "task_id": _safe_get_body_attr(response, 'task_id'),
                    "status": "removing",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to remove nodes: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "instance_ids": instance_ids,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="describe_cluster_node_pool_detail",
            description="Get detailed information of a specific node pool"
        )
        async def describe_cluster_node_pool_detail(
            cluster_id: str,
            nodepool_id: str,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Get node pool detailed information.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Target node pool ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Detailed node pool information
            """
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_cluster_node_pool_detail_with_options_async(
                    cluster_id, nodepool_id, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                nodepool_info_data = _serialize_sdk_object(_safe_get_response_body(response))
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "nodepool_info": nodepool_info_data
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster node pool detail: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="create_cluster_node_pool",
            description="Create a new node pool in ACK cluster"
        )
        async def create_cluster_node_pool(
            cluster_id: str,
            nodepool_name: str,
            instance_types: List[str],
            vswitch_ids: List[str],
            desired_size: int,
            max_size: Optional[int] = None,
            min_size: Optional[int] = None,
            enable_auto_scaling: Optional[bool] = True,
            system_disk_category: Optional[str] = "cloud_efficiency",
            system_disk_size: Optional[int] = 120,
            instance_charge_type: Optional[str] = "PostPaid",
            key_pair: Optional[str] = None,
            login_password: Optional[str] = None,
            security_group_id: Optional[str] = None,
            image_type: Optional[str] = None,
            runtime_name: Optional[str] = "containerd",
            runtime_version: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Create a new node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_name: Name of the new node pool
                instance_types: List of ECS instance types
                vswitch_ids: List of VSwitch IDs
                desired_size: Desired number of nodes
                max_size: Maximum number of nodes for auto scaling
                min_size: Minimum number of nodes for auto scaling
                enable_auto_scaling: Enable auto scaling
                system_disk_category: System disk category
                system_disk_size: System disk size in GB
                instance_charge_type: Instance charge type (PostPaid/PrePaid)
                key_pair: SSH key pair name
                login_password: Login password
                security_group_id: Security group ID
                image_type: Operating system image type
                runtime_name: Container runtime name
                runtime_version: Container runtime version
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Node pool creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request with proper SDK model objects
                # Set nodepool_info
                nodepool_info = cs20151215_models.CreateClusterNodePoolRequestNodepoolInfo(
                    name=nodepool_name,
                    type="ess"
                )
                
                # Set scaling_group with required parameters
                scaling_group = cs20151215_models.CreateClusterNodePoolRequestScalingGroup(
                    instance_types=instance_types,
                    vswitch_ids=vswitch_ids,
                    desired_size=desired_size,
                    system_disk_category=system_disk_category or "cloud_efficiency",
                    system_disk_size=system_disk_size or 120,
                    instance_charge_type=instance_charge_type or "PostPaid"
                )
                
                # Set optional scaling_group parameters
                if key_pair:
                    scaling_group.key_pair = key_pair
                if login_password:
                    scaling_group.login_password = login_password
                if security_group_id:
                    scaling_group.security_group_id = security_group_id
                if image_type:
                    scaling_group.image_type = image_type
                
                # Set auto_scaling
                auto_scaling = cs20151215_models.CreateClusterNodePoolRequestAutoScaling(
                    enable=enable_auto_scaling if enable_auto_scaling is not None else True
                )
                
                if enable_auto_scaling:
                    auto_scaling.max_instances = max_size or desired_size * 2
                    auto_scaling.min_instances = min_size or 0
                    auto_scaling.type = "cpu"
                
                # Build the main request
                request = cs20151215_models.CreateClusterNodePoolRequest(
                    nodepool_info=nodepool_info,
                    scaling_group=scaling_group,
                    auto_scaling=auto_scaling
                )
                
                # Set kubernetes_config if specified (using setattr to avoid type issues)
                kubernetes_config = cs20151215_models.CreateClusterNodePoolRequestKubernetesConfig()
                if runtime_name:
                    kubernetes_config.runtime=runtime_name
                    if runtime_version:
                        kubernetes_config.runtime_version = runtime_version
                
                # Set kubernetes_config as attribute
                request.kubernetes_config = kubernetes_config
                
                runtime: RuntimeOptions = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_node_pool_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": getattr(getattr(response, 'body', None), 'nodepool_id', None) if hasattr(response, 'body') and getattr(response, 'body', None) else None,
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "creating",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="delete_cluster_nodepool",
            description="Delete a node pool from ACK cluster"
        )
        async def delete_cluster_nodepool(
            cluster_id: str,
            nodepool_id: str,
            force: Optional[bool] = False,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Delete a node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Target node pool ID
                force: Force delete even if nodes exist
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Deletion result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request
                request = cs20151215_models.DeleteClusterNodepoolRequest(
                    force=force if force is not None else False
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.delete_cluster_nodepool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "request_id": getattr(response, 'request_id', None),
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "deleting",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to delete cluster node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="modify_cluster_node_pool",
            description="Modify node pool configuration"
        )
        async def modify_cluster_node_pool(
            cluster_id: str,
            nodepool_id: str,
            nodepool_name: Optional[str] = None,
            desired_size: Optional[int] = None,
            max_size: Optional[int] = None,
            min_size: Optional[int] = None,
            enable_auto_scaling: Optional[bool] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Modify node pool configuration.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Target node pool ID
                nodepool_name: New node pool name
                desired_size: New desired number of nodes
                max_size: New maximum number of nodes for auto scaling
                min_size: New minimum number of nodes for auto scaling
                enable_auto_scaling: Enable/disable auto scaling
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Modification result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Create empty request object
                request = cs20151215_models.ModifyClusterNodePoolRequest()
                
                # Set nodepool_info if nodepool_name is provided
                if nodepool_name is not None:
                    nodepool_info = cs20151215_models.ModifyClusterNodePoolRequestNodepoolInfo(
                        name=nodepool_name
                    )
                    request.nodepool_info = nodepool_info
                
                # Set scaling_group if desired_size is provided
                if desired_size is not None:
                    scaling_group = cs20151215_models.ModifyClusterNodePoolRequestScalingGroup(
                        desired_size=desired_size
                    )
                    request.scaling_group = scaling_group
                
                # Set auto_scaling if any auto scaling parameters are provided
                if enable_auto_scaling is not None or max_size is not None or min_size is not None:
                    auto_scaling = cs20151215_models.ModifyClusterNodePoolRequestAutoScaling()
                    
                    if enable_auto_scaling is not None:
                        auto_scaling.enable = enable_auto_scaling
                    
                    if enable_auto_scaling and max_size is not None:
                        auto_scaling.max_instances = max_size
                    
                    if enable_auto_scaling and min_size is not None:
                        auto_scaling.min_instances = min_size
                    
                    request.auto_scaling = auto_scaling
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.modify_cluster_node_pool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "request_id": getattr(response, 'request_id', None),
                    "status": "modified",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to modify cluster node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        #TODO(): not finished
        # @self.server.tool(
        #     name="modify_nodepool_node_config",
        #     description="Modify node pool node configuration"
        # )
        # async def modify_nodepool_node_config(
        #     cluster_id: str,
        #     nodepool_id: str,
        #     # Kubelet configuration parameters
        #     cpu_manager_policy: Optional[str] = None,
        #     feature_gates: Optional[str] = None,
        #     kube_reserved: Optional[str] = None,
        #     system_reserved: Optional[str] = None,
        #     eviction_hard: Optional[str] = None,
        #     # OS configuration parameters
        #     sysctl: Optional[dict] = None,
        #     # Rolling policy parameters
        #     max_parallelism: Optional[int] = None,
        #     ctx: Optional[Context] = None
        # ) -> Dict[str, Any]:
        #     """Modify node pool node configuration.
            
        #     Args:
        #         cluster_id: Target cluster ID
        #         nodepool_id: Target node pool ID
        #         cpu_manager_policy: Kubelet CPU manager policy
        #         feature_gates: Kubelet feature gates
        #         kube_reserved: Kubernetes reserved resources
        #         system_reserved: System reserved resources
        #         eviction_hard: Eviction hard limits
        #         sysctl: OS sysctl configuration
        #         max_parallelism: Rolling update max parallelism
        #         ctx: FastMCP context containing lifespan providers
                
        #     Returns:
        #         Modification result
        #     """
            
            # if not self.allow_write:
            #     return {"error": "Write operations are disabled"}
            
            # # Get CS client from lifespan context
            # try:
            #     if ctx is None:
            #         return {"error": "Context is required"}
            #     providers = ctx.request_context.lifespan_context.get("providers", {})
            #     cs_client_info = providers.get("cs_client", {})
            #     cs_client: CS20151215Client = cs_client_info.get("client")
                
            #     if not cs_client:
            #         return {"error": "CS client not available in lifespan context"}
            # except Exception as e:
            #     logger.error(f"Failed to get CS client from context: {e}")
            #     return {"error": "Failed to access lifespan context"}
            
            # try:
            #     # Create empty request object
            #     request = cs20151215_models.ModifyNodePoolNodeConfigRequest()
                
            #     # Build kubelet_config if any kubelet parameters are provided
            #     if any([cpu_manager_policy, feature_gates, kube_reserved, system_reserved, eviction_hard]):
            #         kubelet_config = cs20151215_models.KubeletConfig()
            #         if cpu_manager_policy:
            #             kubelet_config.cpu_manager_policy = cpu_manager_policy
            #         if feature_gates:
            #             kubelet_config.feature_gates = feature_gates
            #         if kube_reserved:
            #             kubelet_config.kube_reserved = kube_reserved
            #         if system_reserved:
            #             kubelet_config.system_reserved = system_reserved
            #         if eviction_hard:
            #             kubelet_config.eviction_hard = eviction_hard
            #         request.kubelet_config = kubelet_config
                
            #     # Build os_config if sysctl is provided
            #     if sysctl:
            #         os_config = cs20151215_models.ModifyNodePoolNodeConfigRequestOsConfig()
            #         os_config.sysctl = sysctl
            #         request.os_config = os_config
                
            #     # Build rolling_policy if max_parallelism is provided
            #     if max_parallelism:
            #         rolling_policy = cs20151215_models.ModifyNodePoolNodeConfigRequestRollingPolicy()
            #         rolling_policy.max_parallelism = max_parallelism
            #         request.rolling_policy = rolling_policy
                
            #     runtime = util_models.RuntimeOptions()
            #     headers = {}
                
            #     response = await cs_client.modify_node_pool_node_config_with_options_async(
            #         cluster_id, nodepool_id, request, headers, runtime
            #     )
                
            #     # 序列化SDK响应对象为可JSON序列化的数据
            #     response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
            #     return {
            #         "cluster_id": cluster_id,
            #         "nodepool_id": nodepool_id,
            #         "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
            #         "request_id": getattr(response, 'request_id', None),
            #         "status": "configuring",
            #         "response": response_data
            #     }
                
            # except Exception as e:
            #     logger.error(f"Failed to modify node pool node config: {e}")
            #     return {
            #         "cluster_id": cluster_id,
            #         "nodepool_id": nodepool_id,
            #         "error": str(e),
            #         "status": "failed"
            #     }
        
        @self.server.tool(
            name="upgrade_cluster_nodepool",
            description="Upgrade node pool Kubernetes version"
        )
        async def upgrade_cluster_nodepool(
            cluster_id: str,
            nodepool_id: str,
            kubernetes_version: str,
            image_id: Optional[str] = None,
            # Rolling policy parameters
            max_unavailable: Optional[int] = None,
            batch_size: Optional[int] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Upgrade node pool Kubernetes version.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Target node pool ID
                kubernetes_version: Target Kubernetes version
                image_id: Custom image ID (optional)
                max_unavailable: Max unavailable nodes during upgrade
                batch_size: Batch size for rolling upgrade
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Upgrade result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Create request object with required parameter
                request = cs20151215_models.UpgradeClusterNodepoolRequest(
                    kubernetes_version=kubernetes_version
                )
                
                # Set optional parameters
                if image_id:
                    request.image_id = image_id
                
                # Build rolling policy if any rolling parameters are provided
                if max_unavailable is not None or batch_size is not None:
                    rolling_policy = {}
                    if max_unavailable is not None:
                        rolling_policy["max_unavailable"] = max_unavailable
                    if batch_size is not None:
                        rolling_policy["batch_size"] = batch_size
                    # Note: Set as attribute since rolling_policy structure needs to match SDK expectations
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.upgrade_cluster_nodepool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "kubernetes_version": kubernetes_version,
                    "request_id": getattr(response, 'request_id', None),
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "upgrading",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to upgrade cluster nodepool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="describe_nodepool_vuls",
            description="Query node pool security vulnerabilities"
        )
        async def describe_nodepool_vuls(
            cluster_id: str,
            nodepool_id: str,
            necessity: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Query node pool security vulnerabilities.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to query
                necessity: Vulnerability necessity level (asap,later,nntf)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Vulnerability information
            """
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request for describe operation
                request = cs20151215_models.DescribeNodePoolVulsRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                # Add query parameters if specified
                if necessity:
                    headers["necessity"] = necessity
                
                response = await cs_client.describe_node_pool_vuls_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                vul_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "necessity_filter": necessity,
                    "vulnerability_info": vul_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe node pool vulnerabilities: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "error"
                }

        @self.server.tool(
            name="fix_nodepool_vuls",
            description="Fix node pool security vulnerabilities"
        )
        async def fix_nodepool_vuls(
            cluster_id: str,
            nodepool_id: str,
            vuls: Optional[List[str]] = None,
            nodes: Optional[List[str]] = None,
            max_parallelism: Optional[int] = 1,
            auto_restart: Optional[bool] = True,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Fix node pool security vulnerabilities.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to fix
                vuls: List of vulnerability names to fix
                nodes: List of node names to fix (default: all nodes)
                max_parallelism: Max parallel fixing nodes
                auto_restart: Whether to allow node restart
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Fix operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are not allowed"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.FixNodePoolVulsRequest()
                
                # Set request parameters
                if vuls:
                    request.vuls = vuls
                if nodes:
                    request.nodes = nodes
                
                # Set rollout policy
                rollout_policy = cs20151215_models.FixNodePoolVulsRequestRolloutPolicy(
                    max_parallelism=max_parallelism or 1
                )
                # Note: auto_restart attribute not available in SDK model
                request.rollout_policy = rollout_policy
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.fix_node_pool_vuls_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "fixing",
                    "vuls_count": len(vuls) if vuls else None,
                    "nodes_count": len(nodes) if nodes else None,
                    "max_parallelism": max_parallelism,
                    "auto_restart": auto_restart,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to fix node pool vulnerabilities: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="repair_cluster_node_pool",
            description="Repair cluster node pool nodes"
        )
        async def repair_cluster_node_pool(
            cluster_id: str,
            nodepool_id: str,
            nodes: Optional[List[str]] = None,
            # Repair operation parameters
            operation_type: Optional[str] = None,
            auto_restart: Optional[bool] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Repair cluster node pool nodes.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to repair
                nodes: List of node names to repair
                operation_type: Type of repair operation
                auto_restart: Whether to auto restart nodes
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Repair operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are not allowed"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.RepairClusterNodePoolRequest()
                
                # Set request parameters
                if nodes:
                    request.nodes = nodes
                # Note: operations attribute not available in SDK model
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.repair_cluster_node_pool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "repairing",
                    "nodes_count": len(nodes) if nodes else None,
                    "operation_type": operation_type,
                    "auto_restart": auto_restart,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to repair cluster node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="sync_cluster_node_pool",
            description="Sync cluster node pool configuration"
        )
        async def sync_cluster_node_pool(
            cluster_id: str,
            nodepool_id: str,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Sync cluster node pool configuration.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to sync
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Sync operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are not allowed"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.sync_cluster_node_pool_with_options_async(
                    cluster_id, headers, runtime
                )
                
                # Serialize SDK response object
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "status": "syncing",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to sync cluster node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="attach_instances_to_node_pool",
            description="Attach existing instances to node pool"
        )
        async def attach_instances_to_node_pool(
            cluster_id: str,
            nodepool_id: str,
            instances: List[str],
            password: Optional[str] = None,
            format_disk: Optional[bool] = False,
            keep_instance_name: Optional[bool] = True,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Attach existing instances to node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Node pool ID to attach instances to
                instances: List of ECS instance IDs to attach
                password: SSH login password for instances
                format_disk: Whether to format data disk for containers
                keep_instance_name: Whether to keep original instance names
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Attach operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are not allowed"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.AttachInstancesToNodePoolRequest(
                    instances=instances,
                    format_disk=format_disk if format_disk is not None else False,
                    keep_instance_name=keep_instance_name if keep_instance_name is not None else True
                )
                
                if password:
                    request.password = password
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.attach_instances_to_node_pool_with_options_async(
                    cluster_id, nodepool_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "task_id": getattr(getattr(response, 'body', None), 'task_id', None) if getattr(response, 'body', None) else None,
                    "status": "attaching",
                    "instances_count": len(instances),
                    "instances": instances,
                    "format_disk": format_disk,
                    "keep_instance_name": keep_instance_name,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to attach instances to node pool: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "instances": instances,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="create_autoscaling_config",
            description="Create autoscaling configuration for cluster"
        )
        async def create_autoscaling_config(
            cluster_id: str,
            cool_down_duration: Optional[str] = None,
            unneeded_duration: Optional[str] = None,
            utilize_utilization_threshold: Optional[str] = None,
            gpu_utilization_threshold: Optional[str] = None,
            scan_interval: Optional[str] = None,
            scale_down_enabled: Optional[bool] = True,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Create autoscaling configuration for cluster.
            
            Args:
                cluster_id: Target cluster ID
                cool_down_duration: Cool down duration
                unneeded_duration: Unneeded duration
                utilize_utilization_threshold: CPU utilization threshold
                gpu_utilization_threshold: GPU utilization threshold
                scan_interval: Scan interval
                scale_down_enabled: Whether scale down is enabled
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Create operation result
            """
            if not self.allow_write:
                return {"error": "Write operations are not allowed"}
            
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.CreateAutoscalingConfigRequest()
                
                # Set optional parameters
                if cool_down_duration:
                    request.cool_down_duration = cool_down_duration
                if unneeded_duration:
                    request.unneeded_duration = unneeded_duration
                # Note: utilize_utilization_threshold attribute not available in SDK model
                if gpu_utilization_threshold:
                    request.gpu_utilization_threshold = gpu_utilization_threshold
                if scan_interval:
                    request.scan_interval = scan_interval
                if scale_down_enabled is not None:
                    request.scale_down_enabled = scale_down_enabled
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_autoscaling_config_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                response_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "status": "created",
                    "cool_down_duration": cool_down_duration,
                    "unneeded_duration": unneeded_duration,
                    "utilize_utilization_threshold": utilize_utilization_threshold,
                    "gpu_utilization_threshold": gpu_utilization_threshold,
                    "scan_interval": scan_interval,
                    "scale_down_enabled": scale_down_enabled,
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to create autoscaling config: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }

        @self.server.tool(
            name="describe_cluster_attach_scripts",
            description="Get scripts for attaching existing nodes to cluster node pool"
        )
        async def describe_cluster_attach_scripts(
            cluster_id: str,
            nodepool_id: Optional[str] = None,
            format_disk: Optional[bool] = False,
            keep_instance_name: Optional[bool] = True,
            arch: Optional[str] = None,
            options: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Get scripts for attaching existing nodes to cluster node pool.
            
            Args:
                cluster_id: Target cluster ID
                nodepool_id: Optional node pool ID
                format_disk: Whether to format data disk
                keep_instance_name: Whether to keep instance names
                arch: Instance architecture
                options: Additional options
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Attach scripts information
            """
            # Get CS client from lifespan context
            try:
                if ctx is None:
                    return {"error": "Context is required"}
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request for describe operation
                request = cs20151215_models.DescribeClusterAttachScriptsRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                # Build query parameters
                query_params = {}
                if nodepool_id:
                    query_params["nodepool_id"] = nodepool_id
                if format_disk is not None:
                    query_params["format_disk"] = str(format_disk).lower()
                if keep_instance_name is not None:
                    query_params["keep_instance_name"] = str(keep_instance_name).lower()
                if arch:
                    query_params["arch"] = arch
                if options:
                    query_params["options"] = options
                
                response = await cs_client.describe_cluster_attach_scripts_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # Serialize SDK response object
                scripts_data = _serialize_sdk_object(getattr(response, 'body', None)) if getattr(response, 'body', None) else {}
                
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "format_disk": format_disk,
                    "keep_instance_name": keep_instance_name,
                    "arch": arch,
                    "options": options,
                    "scripts_info": scripts_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster attach scripts: {e}")
                return {
                    "cluster_id": cluster_id,
                    "nodepool_id": nodepool_id,
                    "error": str(e),
                    "status": "error"
                }