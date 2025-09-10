"""ACK Cluster Management Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Dict, Any, Optional, List
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
                
                return {
                    "clusters": response.body.clusters,
                    "page_info": response.body.page_info,
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
                
                return {
                    "cluster_id": cluster_id,
                    "cluster_info": {
                        "cluster_id": response.body.cluster_id,
                        "name": response.body.name,
                        "cluster_type": response.body.cluster_type,
                        "cluster_spec": response.body.cluster_spec,
                        "profile": response.body.profile,
                        "state": response.body.state,
                        "size": response.body.size,
                        "region_id": response.body.region_id,
                        "zone_id": response.body.zone_id,
                        "vpc_id": response.body.vpc_id,
                        "vswitch_ids": response.body.vswitch_ids,
                        "current_version": response.body.current_version,
                        "init_version": response.body.init_version,
                        "next_version": response.body.next_version,
                        "created": response.body.created,
                        "updated": response.body.updated,
                        "deletion_protection": response.body.deletion_protection,
                        "resource_group_id": response.body.resource_group_id,
                        "security_group_id": response.body.security_group_id,
                        "container_cidr": response.body.container_cidr,
                        "service_cidr": response.body.service_cidr,
                        "proxy_mode": response.body.proxy_mode,
                        "network_mode": response.body.network_mode,
                        "private_zone": response.body.private_zone,
                        "master_url": response.body.master_url,
                        "tags": response.body.tags,
                        "maintenance_window": response.body.maintenance_window,
                        "operation_policy": response.body.operation_policy
                    }
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
                    request_body["cluster_name"] = cluster_name
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
                
                request = cs20151215_models.ModifyClusterRequest(**request_body)
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.modify_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "status": "modified",
                    "modifications": request_body
                }
                
            except Exception as e:
                logger.error(f"Failed to modify cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="describe_task_info",
            description="Query ACK cluster task status and information"
        )
        async def describe_task_info(
            task_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe ACK cluster task information.
            
            Args:
                task_id: Task ID to query
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
                
                return {
                    "task_id": task_id,
                    "cluster_id": response.body.cluster_id,
                    "task_type": response.body.task_type,
                    "state": response.body.state,
                    "created": response.body.created,
                    "updated": response.body.updated,
                    "current_stage": response.body.current_stage,
                    "target": response.body.target,
                    "parameters": response.body.parameters,
                    "stages": response.body.stages,
                    "events": response.body.events,
                    "task_result": response.body.task_result,
                    "error": response.body.error
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
            kubernetes_version: Optional[str] = None,
            cluster_spec: Optional[str] = None,
            vpc_id: Optional[str] = None,
            service_cidr: Optional[str] = "172.21.0.0/20",
            container_cidr: Optional[str] = None,
            timezone: Optional[str] = "Asia/Shanghai",
            endpoint_public_access: Optional[bool] = False,
            snat_entry: Optional[bool] = True,
            ssh_flags: Optional[bool] = False,
            is_enterprise_security_group: Optional[bool] = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create ACK cluster.
            
            Args:
                name: Cluster name
                region_id: Region ID
                cluster_type: Cluster type (Kubernetes, ManagedKubernetes, ExternalKubernetes)
                kubernetes_version: Kubernetes version
                cluster_spec: Cluster specification (ack.pro.small, ack.standard)
                vpc_id: VPC ID
                service_cidr: Service network CIDR
                container_cidr: Container network CIDR
                timezone: Timezone
                endpoint_public_access: Enable public API access
                snat_entry: Enable SNAT
                ssh_flags: Enable SSH access
                is_enterprise_security_group: Use enterprise security group
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
                # Build request body
                request_body = {
                    "name": name,
                    "region_id": region_id,
                    "cluster_type": cluster_type,
                    "service_cidr": service_cidr,
                    "timezone": timezone,
                    "endpoint_public_access": endpoint_public_access,
                    "snat_entry": snat_entry,
                    "ssh_flags": ssh_flags,
                    "is_enterprise_security_group": is_enterprise_security_group
                }
                
                if kubernetes_version:
                    request_body["kubernetes_version"] = kubernetes_version
                if cluster_spec:
                    request_body["cluster_spec"] = cluster_spec
                if vpc_id:
                    request_body["vpcid"] = vpc_id
                if container_cidr:
                    request_body["container_cidr"] = container_cidr
                
                request = cs20151215_models.CreateClusterRequest(**request_body)
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.create_cluster_with_options_async(
                    request, headers, runtime
                )
                
                return {
                    "cluster_id": response.body.cluster_id,
                    "request_id": response.body.request_id,
                    "task_id": response.body.task_id,
                    "status": "created",
                    "name": name,
                    "region_id": region_id,
                    "cluster_type": cluster_type
                }
                
            except Exception as e:
                logger.error(f"Failed to create cluster: {e}")
                return {
                    "name": name,
                    "region_id": region_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="delete_cluster",
            description="Delete an ACK cluster"
        )
        async def delete_cluster(
            cluster_id: str,
            retain_all_resources: Optional[bool] = False,
            retain_resources: Optional[List[str]] = None,
            delete_options: Optional[List[Dict[str, str]]] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Delete ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                retain_all_resources: Retain all resources
                retain_resources: List of resource IDs to retain
                delete_options: Delete options for specific resource types
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
                # Build request body
                request_body = {
                    "retain_all_resources": retain_all_resources
                }
                
                if retain_resources:
                    request_body["retain_resources"] = retain_resources
                if delete_options:
                    request_body["delete_options"] = delete_options
                
                request = cs20151215_models.DeleteClusterRequest(**request_body)
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.delete_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "task_id": response.body.task_id,
                    "status": "deleting"
                }
                
            except Exception as e:
                logger.error(f"Failed to delete cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="upgrade_cluster",
            description="Upgrade ACK cluster version"
        )
        async def upgrade_cluster(
            cluster_id: str,
            next_version: Optional[str] = None,
            master_only: Optional[bool] = True,
            max_parallelism: Optional[int] = 3,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Upgrade ACK cluster.
            
            Args:
                cluster_id: Target cluster ID
                next_version: Target version to upgrade to
                master_only: Only upgrade control plane
                max_parallelism: Max parallel nodes for worker upgrade
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
                # Build request body
                request_body = {
                    "master_only": master_only
                }
                
                if next_version:
                    request_body["next_version"] = next_version
                if not master_only:
                    request_body["rolling_policy"] = {
                        "max_parallelism": max_parallelism
                    }
                
                request = cs20151215_models.UpgradeClusterRequest(**request_body)
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.upgrade_cluster_with_options_async(
                    cluster_id, request, headers, runtime
                )
                
                return {
                    "cluster_id": cluster_id,
                    "request_id": response.body.request_id,
                    "task_id": response.body.task_id,
                    "status": "upgrading",
                    "next_version": next_version,
                    "master_only": master_only
                }
                
            except Exception as e:
                logger.error(f"Failed to upgrade cluster: {e}")
                return {
                    "cluster_id": cluster_id,
                    "error": str(e),
                    "status": "failed"
                }
        
        @self.server.tool(
            name="describe_cluster_logs",
            description="Query ACK cluster logs"
        )
        async def describe_cluster_logs(
            cluster_id: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe cluster logs.
            
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
                
                return {
                    "cluster_id": cluster_id,
                    "logs": response.body,
                    "count": len(response.body) if response.body else 0
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
            description="Query user cluster quotas"
        )
        async def describe_user_quota(
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe user quota.
            
            Args:
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                User quotas
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
                
                return {
                    "cluster_quota": response.body.cluster_quota,
                    "node_quota": response.body.node_quota,
                    "cluster_nodepool_quota": response.body.cluster_nodepool_quota,
                    "amk_cluster_quota": response.body.amk_cluster_quota,
                    "ask_cluster_quota": response.body.ask_cluster_quota,
                    "quotas": response.body.quotas,
                    "edge_improved_nodepool_quota": response.body.edge_improved_nodepool_quota
                }
                
            except Exception as e:
                logger.error(f"Failed to describe user quota: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="describe_kubernetes_version_metadata",
            description="Query Kubernetes version metadata"
        )
        async def describe_kubernetes_version_metadata(
            region: Optional[str] = None,
            cluster_type: Optional[str] = None,
            kubernetes_version: Optional[str] = None,
            profile: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe Kubernetes version metadata.
            
            Args:
                region: Region filter
                cluster_type: Cluster type filter
                kubernetes_version: Specific version filter
                profile: Profile filter
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
                # Build query parameters
                query_params = {}
                if region:
                    query_params["Region"] = region
                if cluster_type:
                    query_params["ClusterType"] = cluster_type
                if kubernetes_version:
                    query_params["KubernetesVersion"] = kubernetes_version
                if profile:
                    query_params["Profile"] = profile
                
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                response = await cs_client.describe_kubernetes_version_metadata_with_options_async(
                    headers, runtime
                )
                
                return {
                    "versions": response.body,
                    "query_params": query_params
                }
                
            except Exception as e:
                logger.error(f"Failed to describe Kubernetes version metadata: {e}")
                return {
                    "error": str(e),
                    "status": "error"
                }