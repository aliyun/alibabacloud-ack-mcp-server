"""ACK Addon Management Handler - Alibaba Cloud Container Service Addon Management."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_cs20151215.client import Client as CS20151215Client
from pydantic import Field


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


class ACKAddonManagementHandler:
    """Handler for ACK addon management operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK addon management handler.
        
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
        
        logger.info("ACK Addon Management Handler initialized")
    
    def _register_tools(self):
        """Register addon management related tools."""
        
        @self.server.tool(
            name="list_addons",
            description="List available addons for ACK cluster"
        )
        async def list_addons(
            ctx: Context,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            region_id: Optional[str] = Field(None, description="Region filter (optional)"),
            cluster_type: Optional[str] = Field(None, description="Cluster type filter (optional)"),
            profile: Optional[str] = Field(None, description="Cluster profile filter (optional)"),
            cluster_spec: Optional[str] = Field(None, description="Cluster spec filter (optional)"),
            cluster_version: Optional[str] = Field(None, description="Cluster version filter (optional)"),
            cluster_id: Optional[str] = Field(None, description="Cluster ID filter (optional)"),
        ) -> Dict[str, Any]:
            """List available addons.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                region_id: Region filter (optional)
                cluster_type: Cluster type filter (optional)
                profile: Cluster profile filter (optional)
                cluster_spec: Cluster spec filter (optional)
                cluster_version: Cluster version filter (optional)
                cluster_id: Specific cluster ID (optional)
                
            Returns:
                List of available addons
            """
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request with query parameters
                request = cs20151215_models.ListAddonsRequest()
                if region_id:
                    request.region_id = region_id
                if cluster_type:
                    request.cluster_type = cluster_type
                if profile:
                    request.profile = profile
                if cluster_spec:
                    request.cluster_spec = cluster_spec
                if cluster_version:
                    request.cluster_version = cluster_version
                if cluster_id:
                    request.cluster_id = cluster_id
               
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.list_addons_with_options_async(
                    request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                addons_data = _serialize_sdk_object(response.body.addons) if response.body and response.body.addons else []
                
                return {
                    "addons": addons_data,
                    "request_id": getattr(response.body, 'request_id', None) if response.body else None,
                    "query_params": {
                        "cluster_type": cluster_type,
                        "region": region_id,
                        "cluster_spec": cluster_spec,
                        "cluster_version": cluster_version,
                        "profile": profile,
                        "cluster_id": cluster_id
                    },
                    "status": "success"
                }
                
            except Exception as e:
                logger.error(f"Failed to list addons: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="list_cluster_addon_instances",
            description="List installed addon instances for ACK cluster"
        )
        async def list_cluster_addon_instances(
            ctx: Context,
            cluster_id: str,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """List installed addon instances for cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                
            Returns:
                List of installed addon instances
            """
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
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
                
                response = await cs_client.list_cluster_addon_instances_with_options_async(
                    cluster_id, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                addons_data = _serialize_sdk_object(response.body.addons) if response.body and response.body.addons else []
                
                return {
                    "cluster_id": cluster_id,
                    "addons": addons_data,
                    "request_id": getattr(response.body, 'request_id', None) if response.body else None,
                    "status": "success"
                }
                
            except Exception as e:
                logger.error(f"Failed to list cluster addon instances: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="get_cluster_addon_instance",
            description="Get detailed information of a specific addon instance"
        )
        async def get_cluster_addon_instance(
            ctx: Context,
            cluster_id: str,
            addon_name: str,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Get detailed information of a specific addon instance.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                addon_name: Addon name
                
            Returns:
                Addon detailed information
            """
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
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
                
                response = await cs_client.get_cluster_addon_instance_with_options_async(
                    cluster_id, addon_name, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                addon_info_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "addon_info": addon_info_data,
                    "request_id": getattr(response, 'request_id', None),
                    "status": "success"
                }
                
            except Exception as e:
                logger.error(f"Failed to get cluster addon instance: {e}")
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_addon",
            description="Describe addon information"
        )
        async def describe_addon(
            ctx: Context,
            addon_name: str,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            region_id: Optional[str] = Field(None),
            cluster_type: Optional[str] = Field(None),
            profile: Optional[str] = Field(None),
            cluster_spec: Optional[str] = Field(None),
            cluster_version: Optional[str] = Field(None),
            cluster_id: Optional[str] = Field(None),
            version: Optional[str] = None,
        ) -> Dict[str, Any]:
            """Describe addon information.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                addon_name: Addon name
                cluster_spec: Cluster spec filter
                cluster_type: Cluster type filter
                cluster_version: Cluster version filter
                region: Region filter
                
            Returns:
                Addon information
            """
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request with query parameters
                request = cs20151215_models.DescribeAddonRequest()
                if cluster_id:
                    request.cluster_id = cluster_id
                if cluster_spec:
                    request.cluster_spec = cluster_spec
                if cluster_type:
                    request.cluster_type = cluster_type
                if cluster_version:
                    request.cluster_version = cluster_version
                if profile:
                    request.profile = profile
                if region_id:
                    request.region_id = region_id
                if version:
                    request.version = version
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_addon_with_options_async(
                    addon_name, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                addon_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "addon_name": addon_name,
                    "addon": addon_data,
                    "request_id": getattr(response, 'request_id', None),
                    "query_params": {
                        "cluster_spec": cluster_spec,
                        "cluster_type": cluster_type,
                        "cluster_version": cluster_version,
                        "region_id": region_id,
                        "profile": profile,
                        "cluster_id": cluster_id,
                        "version": version
                    },
                    "status": "success"
                }
                
            except Exception as e:
                logger.error(f"Failed to describe addon: {e}")
                return {
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="install_cluster_addons",
            description="Install addons to ACK cluster"
        )
        async def install_cluster_addons(
            ctx: Context,
            cluster_id: str,
            addons: List[Dict[str, Any]],
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Install addons to cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                addons: List of addons to install, each addon should contain:
                       - name: Addon name (required)
                       - version: Addon version (optional)
                       - config: Addon configuration (optional)
                
            Returns:
                Installation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.InstallClusterAddonsRequest()
                if addons:
                    body: List[cs20151215_models.InstallClusterAddonsRequestBody] = []
                    for _, el in enumerate(addons):
                        body.append(cs20151215_models.InstallClusterAddonsRequestBody().from_map(el))
                    request.body = body
                
                runtime = util_models.RuntimeOptions()
                headers = {'Content-Type': 'application/json'}
                
                # Use the async method with JSON body
                response = await cs_client.install_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "installing",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to install cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="uninstall_cluster_addons",
            description="Uninstall addons from ACK cluster"
        )
        async def uninstall_cluster_addons(
            ctx: Context,
            cluster_id: str,
            addons: List[Dict[str, Any]],
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Uninstall addons from cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                addons: List of addons to uninstall, each addon should contain:
                       - name: Addon name (required)
                       - cleanup_cloud_resources: Whether to cleanup cloud resources (optional)
                
            Returns:
                Uninstallation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.UnInstallClusterAddonsRequest()
                if addons:
                    body: List[cs20151215_models.UnInstallClusterAddonsRequestAddons] = []
                    for _, el in enumerate(addons):
                        body.append(cs20151215_models.UnInstallClusterAddonsRequestAddons().from_map(el))
                request.body = body
            
                runtime = util_models.RuntimeOptions()
                headers = {'Content-Type': 'application/json'}
                
                response = await cs_client.un_install_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "uninstalling",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to uninstall cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="modify_cluster_addon",
            description="Modify cluster addon configuration"
        )
        async def modify_cluster_addon(
            ctx: Context,
            cluster_id: str,
            addon_name: str,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            config: Optional[str] = None,
        ) -> Dict[str, Any]:
            """Modify cluster addon configuration.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                addon_name: Addon name
                config: Addon configuration in JSON string format
                
            Returns:
                Modification result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.ModifyClusterAddonRequest()
                if config:
                    request.config = config

                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.modify_cluster_addon_with_options_async(
                    cluster_id, addon_name, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "request_id": getattr(response, 'request_id', None),
                    "status": "modified",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to modify cluster addon: {e}")
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="upgrade_cluster_addons",
            description="Upgrade cluster addons"
        )
        async def upgrade_cluster_addons(
            ctx: Context,
            cluster_id: str,
            addons: List[Dict[str, Any]],
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Upgrade cluster addons.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                addons: List of addons to upgrade, each addon should contain:
                       - component_name: Addon name (required)
                       - next_version: Target version (required)
                       - version: Current version (optional)
                       - config: Addon configuration (optional)
                       - policy: Upgrade policy, overwrite or canary (optional)
                
            Returns:
                Upgrade result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # Get CS client from lifespan context
            if ctx is None:
                return {"error": "Context is required"}
                
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                cs_client_info = providers.get("cs_client", {})
                cs_client: CS20151215Client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                request = cs20151215_models.UpgradeClusterAddonsRequest()                    
                if addons:
                    body: List[cs20151215_models.UpgradeClusterAddonsRequestBody] = []
                    for _, el in enumerate(addons):
                        body.append(cs20151215_models.UpgradeClusterAddonsRequestBody().from_map(el))
                    request.body = body
                
                runtime = util_models.RuntimeOptions()
                headers = {'Content-Type': 'application/json'}
                
                response = await cs_client.upgrade_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "upgrading",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to upgrade cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }