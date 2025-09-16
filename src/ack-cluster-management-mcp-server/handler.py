"""ACK Cluster Management Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_cs20151215.client import Client as CS20151215Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient
import json
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
        
        DEFAULT_REGIONS = [
            "cn-hangzhou", "cn-shanghai", "cn-beijing", "cn-shenzhen", "cn-zhangjiakou", "cn-huhehaote",
            "cn-chengdu", "cn-hongkong", "ap-southeast-1", "ap-southeast-3", "ap-southeast-5",
            "ap-south-1", "ap-northeast-1", "eu-central-1", "eu-west-1", "us-west-1", "us-east-1",
        ]
        
        def _build_cs_client_for_region(base_config: Dict[str, Any], region: str) -> CS20151215Client:
            credential_client = CredentialClient()
            cs_config = open_api_models.Config(credential=credential_client)
            cs_config.access_key_id = base_config.get("access_key_id")
            cs_config.access_key_secret = base_config.get("access_key_secret")
            cs_config.region_id = region
            cs_config.endpoint = f"cs.{region}.aliyuncs.com"
            return CS20151215Client(cs_config)
        
        @self.server.tool(
            name="describe_clusters",
            description="List and query ACK clusters"
        )
        async def describe_clusters(
            ctx: Context,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            cluster_name: Optional[str] = Field(None, description="Cluster name filter"),
            cluster_type: Optional[str] = Field(None, description="Cluster type (Kubernetes, ManagedKubernetes, ExternalKubernetes)"),
            cluster_spec: Optional[str] = Field(None, description="Cluster spec (ack.pro.small, ack.standard)"),
            profile: Optional[str] = Field(None, description="Cluster profile (Default, Edge, Serverless, Lingjun)"),
            region_id: Optional[str] = Field(None, description="Region ID filter"),
            cluster_id: Optional[str] = Field(None, description="Specific cluster ID"),
            page_size: Optional[int] = Field(10, description="Page size (max 100), if not set is default 10."),
            page_number: Optional[int] = Field(1, description="Page number, if not set is default 1."),
        ) -> Dict[str, Any]:
            """List ACK clusters.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_name: Cluster name filter
                cluster_type: Cluster type (Kubernetes, ManagedKubernetes, ExternalKubernetes)
                cluster_spec: Cluster spec (ack.pro.small, ack.standard)
                profile: Cluster profile (Default, Edge, Serverless, Lingjun)
                region_id: Region ID filter
                cluster_id: Specific cluster ID
                page_size: Page size (max 100), if not set is default 10.
                page_number: Page number
                
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
            name="describe_clusters_brief",
            description="Quick list brief all clusters and output. default page_size 500."
        )
        async def describe_clusters_brief(
            ctx: Context,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            regions: Optional[List[str]] = Field(None, description="Region list to query; defaults to common regions"),
            page_size: Optional[int] = Field(500, description="Page size, default 500"),
        ) -> Dict[str, Any]:
            """List clusters with brief fields across regions.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                regions: Region list to query; defaults to common regions
                page_size: Page size, default 500
            
            Returns:
                Brief cluster list with fields: name, cluster_id, state, region_id, node_count, cluster_type
            """
            # Get base config for AK
            try:
                lifespan_config = ctx.request_context.lifespan_context.get("config", {})
            except Exception as e:
                logger.error(f"Failed to get lifespan config: {e}")
                return {"error": "Failed to access lifespan context"}
            
            target_regions = regions or DEFAULT_REGIONS
            brief_list: List[Dict[str, Any]] = []
            errors: List[Dict[str, Any]] = []
            
            for region in target_regions:
                try:
                    cs_client = _build_cs_client_for_region(lifespan_config, region)
                    request = cs20151215_models.DescribeClustersV1Request(
                        page_size=min(page_size or 500, 500),
                        page_number=1,
                        region_id=region,
                    )
                    runtime = util_models.RuntimeOptions()
                    headers = {}
                    response = await cs_client.describe_clusters_v1with_options_async(request, headers, runtime)
                    clusters = _serialize_sdk_object(response.body.clusters) if response.body and response.body.clusters else []
                    for c in clusters:
                        # 兼容 SDK 字段命名
                        brief_list.append({
                            "name": c.get("name") or c.get("cluster_name"),
                            "cluster_id": c.get("cluster_id") or c.get("clusterId"),
                            "state": c.get("state") or c.get("cluster_state") or c.get("status"),
                            "region_id": c.get("region_id") or region,
                            "node_count": c.get("node_count") or c.get("current_node_count") or c.get("size"),
                            "cluster_type": c.get("cluster_type") or c.get("clusterType"),
                        })
                except Exception as e:
                    logger.warning(f"describe_clusters_brief failed for region {region}: {e}")
                    errors.append({"region": region, "error": str(e)})
                    continue
            
            return {
                "clusters": brief_list,
                "count": len(brief_list),
                "regions": target_regions,
                "errors": errors or None,
            }
        
        @self.server.tool(
            name="describe_cluster_detail",
            description="Get detailed information of a specific ACK cluster"
        )
        async def describe_cluster_detail(
            ctx: Context,
            cluster_id: str = Field(..., description="Target cluster ID"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Get cluster detailed information.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                
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
            ctx: Context,
            cluster_id: str = Field(..., description="Target cluster ID"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            cluster_name: Optional[str] = Field(None, description="New cluster name"),
            deletion_protection: Optional[bool] = Field(None, description="Enable cluster deletion protection"),
            instance_deletion_protection: Optional[bool] = Field(None, description="Enable instance deletion protection"),
            resource_group_id: Optional[str] = Field(None, description="Resource group ID"),
            api_server_eip: Optional[bool] = Field(None, description="Bind EIP to API Server"),
            api_server_eip_id: Optional[str] = Field(None, description="EIP instance ID for API Server"),
            ingress_domain_rebinding: Optional[bool] = Field(None, description="Rebind ingress test domain"),
            ingress_loadbalancer_id: Optional[str] = Field(None, description="Ingress LoadBalancer ID"),
            enable_rrsa: Optional[bool] = Field(None, description="Enable RRSA functionality"),
        ) -> Dict[str, Any]:
            """Modify cluster configuration.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
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
            ctx: Context,
            task_id: str = Field(..., description="Task ID"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Get task information.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                task_id: Task ID
                
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
            ctx: Context,
            name: str = Field(..., description="Cluster name"),
            region_id: str = Field(..., description="Region ID"),
            cluster_type: str = Field(..., description="Cluster type (ManagedKubernetes, Kubernetes)"),
            kubernetes_version: str = Field(..., description="Kubernetes version"),
            cluster_spec: str = Field(..., description="Cluster spec"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            vpc_id: Optional[str] = Field(None, description="VPC ID"),
            vswitch_ids: Optional[List[str]] = Field(None, description="VSwitch IDs"),
            container_cidr: Optional[str] = Field(None, description="Container CIDR"),
            service_cidr: Optional[str] = Field(None, description="Service CIDR"),
            master_instance_types: Optional[List[str]] = Field(None, description="Master instance types"),
            worker_instance_types: Optional[List[str]] = Field(None, description="Worker instance types"),
            num_of_nodes: Optional[int] = Field(None, description="Number of worker nodes"),
            login_password: Optional[str] = Field(None, description="Login password"),
            key_pair: Optional[str] = Field(None, description="Key pair name"),
        ) -> Dict[str, Any]:
            """Create a new ACK cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
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
            ctx: Context,
            cluster_id: str = Field(..., description="Target cluster ID"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            retain_all_resources: Optional[bool] = Field(False, description="Whether to retain all resources"),
        ) -> Dict[str, Any]:
            """Delete an ACK cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                retain_all_resources: Whether to retain all resources
                
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
            ctx: Context,
            cluster_id: str = Field(..., description="Target cluster ID"),
            next_version: str = Field(..., description="Target Kubernetes version"),
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            master_only: Optional[bool] = Field(False, description="Upgrade master only"),
        ) -> Dict[str, Any]:
            """Upgrade an ACK cluster.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                next_version: Target Kubernetes version
                master_only: Whether to upgrade master only
                
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
            ctx: Context,
            cluster_id: str,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Get cluster logs.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                cluster_id: Target cluster ID
                
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
            ctx: Context,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
        ) -> Dict[str, Any]:
            """Get user quota information.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                
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
            ctx: Context,
            resource_type: str = Field(
                ..., description='Type of resource to get metrics for (cluster, node, pod, namespace, )'
            ),
            region: Optional[str] = Field(None),
            cluster_type: Optional[str] = Field(None),
        ) -> Dict[str, Any]:
            """Get Kubernetes version metadata.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                resource_type: Type of resource to get metrics for (cluster, node, pod, namespace, )
                region: Region ID
                cluster_type: Cluster type
                
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
