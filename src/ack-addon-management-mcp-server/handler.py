"""ACK Addon Management Handler."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models


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
            name="list_cluster_addons",
            description="List available addons for ACK cluster"
        )
        async def list_cluster_addons(
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """List available addons for cluster.
            
            Args:
                cluster_id: Target cluster ID
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
                request = cs20151215_models.DescribeClusterAddonsRequest()
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "addons": response.body.addons,
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to list cluster addons: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="install_cluster_addon",
            description="Install addon to ACK cluster"
        )
        async def install_cluster_addon(
            cluster_id: str,
            addon_name: str,
            addon_version: Optional[str] = None,
            config: Optional[Dict[str, Any]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Install addon to cluster.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name to install
                addon_version: Addon version (optional)
                config: Addon configuration (optional)
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
                addon_config = {
                    "name": addon_name,
                }
                if addon_version:
                    addon_config["version"] = addon_version
                if config:
                    addon_config["config"] = config
                
                request = cs20151215_models.InstallClusterAddonsRequest(
                    addons=[addon_config]
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.install_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "addon_version": addon_version,
                    "task_id": response.body.task_id,
                    "status": "installing",
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to install cluster addon: {e}")
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="uninstall_cluster_addon",
            description="Uninstall addon from ACK cluster"
        )
        async def uninstall_cluster_addon(
            cluster_id: str,
            addon_name: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Uninstall addon from cluster.
            
            Args:
                cluster_id: Target cluster ID
                addon_name: Addon name to uninstall
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
                    addons=[{"name": addon_name}]
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.un_install_cluster_addons_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "task_id": response.body.task_id,
                    "status": "uninstalling",
                    "request_id": response.body.request_id
                }
                
            except Exception as e:
                logger.error(f"Failed to uninstall cluster addon: {e}")
                return {
                    "cluster_id": cluster_id,
                    "addon_name": addon_name,
                    "error": str(e),
                    "status": "failed"
                }