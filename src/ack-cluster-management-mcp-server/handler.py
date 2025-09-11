"""ACK Cluster Management Handler - Alibaba Cloud Container Service Cluster Management."""

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
            name="describe_clusters",
            description="List and query ACK clusters"
        )
        async def describe_clusters(
            cluster_name: Optional[str] = None,
            cluster_type: Optional[str] = None,
            cluster_spec: Optional[str] = None,
            profile: Optional[str] = None,
            region_id: Optional[str] = None,
            cluster_id: Optional[str] = None,
            page_size: Optional[int] = 10,
            page_number: Optional[int] = 1,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """List ACK clusters.
            
            Args:
                cluster_name: Cluster name filter
                cluster_type: Cluster type (Kubernetes, ManagedKubernetes, ExternalKubernetes)
                cluster_spec: Cluster spec (ack.pro.small, ack.standard)
                profile: Cluster profile (Default, Edge, Serverless, Lingjun)
                region_id: Region ID filter
                cluster_id: Specific cluster ID
                page_size: Page size (max 100)
                page_number: Page number
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of clusters
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
                # Build request with query parameters
                request = cs20151215_models.DescribeClustersV1Request(
                    name=cluster_name,
                    cluster_type=cluster_type,
                    cluster_spec=cluster_spec,
                    profile=profile,
                    region_id=region_id,
                    cluster_id=cluster_id,
                    page_size=min(page_size, 100) if page_size else 10,
                    page_number=page_number or 1
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_clusters_v1with_options_async(
                    request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                clusters_data = _serialize_sdk_object(response.body.clusters) if response.body.clusters else []
                page_info_data = _serialize_sdk_object(response.body.page_info) if response.body.page_info else {}
                
                return {
                    "clusters": clusters_data,
                    "page_info": page_info_data,
                    "request_id": getattr(response.body, 'request_id', None),
                    "query_params": {
                        "name": cluster_name,
                        "cluster_type": cluster_type,
                        "cluster_spec": cluster_spec,
                        "profile": profile,
                        "region_id": region_id,
                        "cluster_id": cluster_id,
                        "page_size": min(page_size, 100) if page_size else 10,
                        "page_number": page_number or 1
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to describe clusters: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_cluster_detail",
            description="Get detailed information of a specific ACK cluster"
        )
        async def describe_cluster_detail(
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster detailed information.
            
            Args:
                cluster_id: Target cluster ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Detailed cluster information
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
                
                response = await cs_client.describe_cluster_detail_with_options_async(
                    cluster_id, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                cluster_info_data = _serialize_sdk_object(response.body)
                
                return {
                    "cluster_id": cluster_id,
                    "cluster_info": cluster_info_data
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster detail: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="modify_cluster",
            description="Modify ACK cluster configuration"
        )
        async def modify_cluster(
            cluster_id: str,
            cluster_name: Optional[str] = None,
            deletion_protection: Optional[bool] = None,
            instance_deletion_protection: Optional[bool] = None,
            resource_group_id: Optional[str] = None,
            api_server_eip: Optional[bool] = None,
            api_server_eip_id: Optional[str] = None,
            ingress_domain_rebinding: Optional[bool] = None,
            ingress_loadbalancer_id: Optional[str] = None,
            enable_rrsa: Optional[bool] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Modify cluster configuration.
            
            Args:
                cluster_id: Target cluster ID
                cluster_name: New cluster name
                deletion_protection: Enable cluster deletion protection
                instance_deletion_protection: Enable instance deletion protection
                resource_group_id: Resource group ID
                api_server_eip: Bind EIP to API Server
                api_server_eip_id: EIP instance ID for API Server
                ingress_domain_rebinding: Rebind ingress test domain
                ingress_loadbalancer_id: Ingress LoadBalancer ID
                enable_rrsa: Enable RRSA functionality
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
                # Build request body with only non-None parameters
                request_body = {}
                if cluster_name is not None:
                    request_body["name"] = cluster_name
                if deletion_protection is not None:
                    request_body["deletion_protection"] = deletion_protection
                if instance_deletion_protection is not None:
                    request_body["instance_deletion_protection"] = instance_deletion_protection
                if resource_group_id is not None:
                    request_body["resource_group_id"] = resource_group_id
                if api_server_eip is not None:
                    request_body["api_server_eip"] = api_server_eip
                if api_server_eip_id is not None:
                    request_body["api_server_eip_id"] = api_server_eip_id
                if ingress_domain_rebinding is not None:
                    request_body["ingress_domain_rebinding"] = ingress_domain_rebinding
                if ingress_loadbalancer_id is not None:
                    request_body["ingress_loadbalancer_id"] = ingress_loadbalancer_id
                if enable_rrsa is not None:
                    request_body["enable_rrsa"] = enable_rrsa
                
                request = cs20151215_models.ModifyClusterRequest(
                    **request_body
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.modify_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": getattr(response, 'request_id', None),
                    "status": "modified",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to modify cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_task_info",
            description="Get task information"
        )
        async def describe_task_info(
            task_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get task information.
            
            Args:
                task_id: Task ID
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
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_task_info_with_options_async(
                    task_id, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                task_info_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "task_id": task_id,
                    "task_info": task_info_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe task info: {e}")
                return {
                    "task_id": task_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="create_cluster",
            description="Create a new ACK cluster"
        )
        async def create_cluster(
            name: str,
            region_id: str,
            cluster_type: str,
            kubernetes_version: str,
            cluster_spec: str,
            vpc_id: Optional[str] = None,
            vswitch_ids: Optional[List[str]] = None,
            container_cidr: Optional[str] = None,
            service_cidr: Optional[str] = None,
            master_instance_types: Optional[List[str]] = None,
            worker_instance_types: Optional[List[str]] = None,
            num_of_nodes: Optional[int] = None,
            login_password: Optional[str] = None,
            key_pair: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create a new ACK cluster.
            
            Args:
                name: Cluster name
                region_id: Region ID
                cluster_type: Cluster type (ManagedKubernetes, Kubernetes)
                kubernetes_version: Kubernetes version
                cluster_spec: Cluster spec
                vpc_id: VPC ID
                vswitch_ids: VSwitch IDs
                container_cidr: Container CIDR
                service_cidr: Service CIDR
                master_instance_types: Master instance types
                worker_instance_types: Worker instance types
                num_of_nodes: Number of worker nodes
                login_password: Login password
                key_pair: Key pair name
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Cluster creation result
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
                # Build request
                request_dict = {
                    "name": name,
                    "region_id": region_id,
                    "cluster_type": cluster_type,
                    "kubernetes_version": kubernetes_version,
                    "cluster_spec": cluster_spec
                }
                
                if vpc_id:
                    request_dict["vpc_id"] = vpc_id
                if vswitch_ids:
                    request_dict["vswitch_ids"] = vswitch_ids
                if container_cidr:
                    request_dict["container_cidr"] = container_cidr
                if service_cidr:
                    request_dict["service_cidr"] = service_cidr
                if master_instance_types:
                    request_dict["master_instance_types"] = master_instance_types
                if worker_instance_types:
                    request_dict["worker_instance_types"] = worker_instance_types
                if num_of_nodes is not None:
                    request_dict["num_of_nodes"] = num_of_nodes
                if login_password:
                    request_dict["login_password"] = login_password
                if key_pair:
                    request_dict["key_pair"] = key_pair
                
                request = cs20151215_models.CreateClusterRequest(**request_dict)
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_with_options_async(
                    request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": getattr(response.body, 'cluster_id', None) if response.body else None,
                    "request_id": getattr(response, 'request_id', None),
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "created",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="delete_cluster",
            description="Delete an ACK cluster"
        )
        async def delete_cluster(
            cluster_id: str,
            retain_all_resources: Optional[bool] = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Delete an ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                retain_all_resources: Whether to retain all resources
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Cluster deletion result
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
                # Build request
                request = cs20151215_models.DeleteClusterRequest(
                    retain_all_resources=retain_all_resources
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.delete_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": getattr(response, 'request_id', None),
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "deleting",
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to delete cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="upgrade_cluster",
            description="Upgrade an ACK cluster"
        )
        async def upgrade_cluster(
            cluster_id: str,
            next_version: str,
            master_only: Optional[bool] = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Upgrade an ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                next_version: Target Kubernetes version
                master_only: Whether to upgrade master only
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Cluster upgrade result
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
                # Build request
                request = cs20151215_models.UpgradeClusterRequest(
                    next_version=next_version,
                    master_only=master_only
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.upgrade_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                response_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": getattr(response, 'request_id', None),
                    "task_id": getattr(response.body, 'task_id', None) if response.body else None,
                    "status": "upgrading",
                    "next_version": next_version,
                    "master_only": master_only,
                    "response": response_data
                }
                
            except Exception as e:
                logger.error(f"Failed to upgrade cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_cluster_logs",
            description="Get cluster logs"
        )
        async def describe_cluster_logs(
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get cluster logs.
            
            Args:
                cluster_id: Target cluster ID
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Cluster logs
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
                
                response = await cs_client.describe_cluster_logs_with_options_async(
                    cluster_id, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                logs_data = _serialize_sdk_object(response.body) if response.body else []
                
                return {
                    "cluster_id": cluster_id,
                    "logs": logs_data,
                    "count": len(logs_data) if logs_data else 0,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe cluster logs: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_user_quota",
            description="Get user quota information"
        )
        async def describe_user_quota(
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get user quota information.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                User quota information
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
                
                response = await cs_client.describe_user_quota_with_options_async(
                    headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                quota_data = _serialize_sdk_object(response.body) if response.body else {}
                
                return {
                    "quota_info": quota_data,
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe user quota: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_kubernetes_version_metadata",
            description="Get Kubernetes version metadata"
        )
        async def describe_kubernetes_version_metadata(
            region: Optional[str] = None,
            cluster_type: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get Kubernetes version metadata.
            
            Args:
                region: Region ID
                cluster_type: Cluster type
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Kubernetes version metadata
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
                # Build request with query parameters
                request = cs20151215_models.DescribeKubernetesVersionMetadataRequest(
                    region=region,
                    cluster_type=cluster_type
                )
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_kubernetes_version_metadata_with_options_async(
                    request, headers, runtime
                )
                
                # 序列化SDK响应对象为可JSON序列化的数据
                versions_data = _serialize_sdk_object(response.body) if response.body else []
                
                return {
                    "versions": versions_data,
                    "query_params": {
                        "region": region,
                        "cluster_type": cluster_type
                    },
                    "request_id": getattr(response, 'request_id', None)
                }
                
            except Exception as e:
                logger.error(f"Failed to describe Kubernetes version metadata: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
