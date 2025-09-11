"""ACK Addon Management Handler."""

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
            name="describe_cluster_addons",
            description="Describe available addons for ACK cluster"
        )
        async def describe_cluster_addons(
            cluster_id: str,
            addon_name: Optional[str] = None,
            component_name: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe available addons for cluster.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name filter (optional)
                component_name: Component name filter (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of available addons
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
                # 构建请求参数
                request_dict = {}
                if addon_name:
                    request_dict["addon_name"] = addon_name
                if component_name:
                    request_dict["component_name"] = component_name
                
                request = cs20151215_models.DescribeClusterAddonsRequest(**request_dict)
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                addons_data = _serialize_sdk_object(response.body.addons) if response.body.addons else []
                
                return {
                    "cluster_id": cluster_id,
                    "addons": addons_data,
                    "request_id": getattr(response.body, 'request_id', None),
                    "status": "success"
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
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
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Install addons to cluster.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to install, each addon should contain:
                       - name: Addon name (required)
                       - version: Addon version (optional)
                       - config: Addon configuration (optional)
                       - properties: Addon properties (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Installation result
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
                # 构建 addon 安装参数
                request = cs20151215_models.InstallClusterAddonsRequest(
                    addons=addons
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
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
            addons: List[Dict[str, str]],
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Uninstall addons from cluster.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to uninstall, each addon should contain:
                       - name: Addon name (required)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Uninstallation result
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
                request = cs20151215_models.UnInstallClusterAddonsRequest(
                    addons=addons
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
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
            name="describe_cluster_addon_info",
            description="Describe detailed information of a specific addon"
        )
        async def describe_cluster_addon_info(
            cluster_id: str,
            addon_name: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe detailed information of a specific addon.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Addon detailed information
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
                request = cs20151215_models.DescribeClusterAddonInfoRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_cluster_addon_info_with_options_async(
                    cluster_id, addon_name, request, headers, runtime
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
                logger.error(f"Failed to describe cluster addon info: {e}")
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="modify_cluster_addons",
            description="Modify addons in ACK cluster"
        )
        async def modify_cluster_addons(
            cluster_id: str,
            addons: List[Dict[str, Any]],
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Modify addons in cluster.
            
            Args:
                cluster_id: Target cluster ID
                addons: List of addons to modify, each addon should contain:
                       - name: Addon name (required)
                       - config: Addon configuration (optional)
                       - version: Addon version (optional)
                       - properties: Addon properties (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Modification result
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
                request = cs20151215_models.ModifyClusterAddonsRequest(
                    addons=addons
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.modify_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "modifying",
                    "response": response_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to modify cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }