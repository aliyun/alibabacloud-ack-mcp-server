"""ACK Addon Management Handler - Alibaba Cloud Container Service Addon Management."""

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
            cluster_type: Optional[str] = None,
            region: Optional[str] = None,
            cluster_spec: Optional[str] = None,
            cluster_version: Optional[str] = None,
            profile: Optional[str] = None,
            cluster_id: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """List available addons.
            
            Args:
                cluster_type: Cluster type filter
                region: Region filter  
                cluster_spec: Cluster spec filter
                cluster_version: Cluster version filter
                profile: Cluster profile filter
                cluster_id: Specific cluster ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of available addons
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
                # Build request with query parameters
                request_dict = {}
                if cluster_type:
                    request_dict["cluster_type"] = cluster_type
                if region:
                    request_dict["region"] = region
                if cluster_spec:
                    request_dict["cluster_spec"] = cluster_spec
                if cluster_version:
                    request_dict["cluster_version"] = cluster_version
                if profile:
                    request_dict["profile"] = profile
                if cluster_id:
                    request_dict["cluster_id"] = cluster_id
                
                request = cs20151215_models.ListAddonsRequest(**request_dict)
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
                        "region": region,
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
            cluster_id: str,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """List installed addon instances for cluster.
            
            Args:
                cluster_id: Target cluster ID
                ctx: FastMCP context containing lifespan providers
                
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
            cluster_id: str,
            addon_name: str,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Get detailed information of a specific addon instance.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name
                ctx: FastMCP context containing lifespan providers
                
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
            addon_name: str,
            cluster_spec: Optional[str] = None,
            cluster_type: Optional[str] = None,
            cluster_version: Optional[str] = None,
            region: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Describe addon information.
            
            Args:
                addon_name: Addon name
                cluster_spec: Cluster spec filter
                cluster_type: Cluster type filter
                cluster_version: Cluster version filter
                region: Region filter
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Addon information
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
                # Build request with query parameters
                request_dict = {"addon_name": addon_name}
                if cluster_spec:
                    request_dict["cluster_spec"] = cluster_spec
                if cluster_type:
                    request_dict["cluster_type"] = cluster_type
                if cluster_version:
                    request_dict["cluster_version"] = cluster_version
                if region:
                    request_dict["region"] = region
                
                request = cs20151215_models.DescribeAddonRequest(**request_dict)
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
                        "region": region
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
            cluster_id: str,
            addons: List[Dict[str, Any]],
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Install addons to cluster.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to install, each addon should contain:
                       - name: Addon name (required)
                       - version: Addon version (optional)
                       - config: Addon configuration (optional)
                       - disabled: Whether addon is disabled (optional)
                ctx: FastMCP context containing lifespan providers
                
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
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build addon installation parameters
                # Convert addons list to JSON string for body
                request_body = json.dumps({'addons': addons})
                request = cs20151215_models.InstallClusterAddonsRequest()
                
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
            cluster_id: str,
            addons: List[Dict[str, Any]],
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Uninstall addons from cluster.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to uninstall, each addon should contain:
                       - name: Addon name (required)
                       - cleanup_cloud_resources: Whether to cleanup cloud resources (optional)
                ctx: FastMCP context containing lifespan providers
                
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
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Convert addons list to JSON string for body
                request_body = json.dumps({'addons': addons})
                request = cs20151215_models.UnInstallClusterAddonsRequest()
                
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
            cluster_id: str,
            addon_name: str,
            config: Optional[str] = None,
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Modify cluster addon configuration.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name
                config: Addon configuration in JSON string format
                ctx: FastMCP context containing lifespan providers
                
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
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Build request
                request_dict = {}
                if config:
                    request_dict["config"] = config
                
                request = cs20151215_models.ModifyClusterAddonRequest(**request_dict)
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
            cluster_id: str,
            addons: List[Dict[str, Any]],
            ctx: Optional[Context] = None
        ) -> Dict[str, Any]:
            """Upgrade cluster addons.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to upgrade, each addon should contain:
                       - name: Addon name (required)
                       - version: Target version (required)
                       - config: Addon configuration (optional)
                ctx: FastMCP context containing lifespan providers
                
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
                cs_client = cs_client_info.get("client")
                
                if not cs_client:
                    return {"error": "CS client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get CS client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # Convert addons list to JSON string for body
                request_body = json.dumps({'addons': addons})
                request = cs20151215_models.UpgradeClusterAddonsRequest()
                
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