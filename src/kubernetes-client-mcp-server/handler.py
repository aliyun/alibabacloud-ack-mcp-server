"""Kubernetes Client Handler."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
import yaml
from kubernetes.client.rest import ApiException


class KubernetesClientHandler:
    """Handler for Kubernetes client operations."""
    
    def __init__(self, server: FastMCP, allow_write: bool = False, settings: Optional[Dict[str, Any]] = None):
        """Initialize the Kubernetes client handler.
        
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
        
        logger.info("Kubernetes Client Handler initialized")
    
    def _register_tools(self):
        """Register Kubernetes client related tools."""
        
        @self.server.tool(
            name="k8s_resource_get_yaml",
            description="Get Kubernetes resource definition in YAML format"
        )
        async def k8s_resource_get_yaml(
            resource_type: str,
            resource_name: str,
            namespace: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get resource YAML definition.
            
            Args:
                resource_type: Type of Kubernetes resource (e.g., pod, service, deployment)
                resource_name: Name of the resource
                namespace: Namespace (optional for cluster-scoped resources)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Resource YAML definition
            """
            # Get K8s client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                k8s_client_info = providers.get("k8s_client", {})
                k8s_client = k8s_client_info.get("client")
                
                if not k8s_client:
                    return {"error": "K8s client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get K8s client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                # 根据资源类型选择合适的 API 客户端
                if resource_type.lower() in ['pod', 'service', 'configmap', 'secret', 'namespace']:
                    api_client = k8s_client['core_v1']
                    if resource_type.lower() == 'pod':
                        if namespace:
                            resource = api_client.read_namespaced_pod(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for pod resources"}
                    elif resource_type.lower() == 'service':
                        if namespace:
                            resource = api_client.read_namespaced_service(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for service resources"}
                    # 添加更多资源类型...
                elif resource_type.lower() in ['deployment', 'replicaset', 'daemonset', 'statefulset']:
                    api_client = k8s_client['apps_v1']
                    if resource_type.lower() == 'deployment':
                        if namespace:
                            resource = api_client.read_namespaced_deployment(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for deployment resources"}
                    # 添加更多资源类型...
                else:
                    return {"error": f"Unsupported resource type: {resource_type}"}
                
                # 转换为 YAML 格式
                yaml_content = yaml.dump(resource.to_dict(), default_flow_style=False)
                
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "yaml": yaml_content
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to get resource YAML: {e}")
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="k8s_resource_list",
            description="List Kubernetes resources"
        )
        async def k8s_resource_list(
            resource_type: str,
            namespace: Optional[str] = None,
            label_selector: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """List Kubernetes resources.
            
            Args:
                resource_type: Type of Kubernetes resource
                namespace: Namespace filter (optional)
                label_selector: Label selector filter (optional)
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of resources
            """
            # Get K8s client from lifespan context
            try:
                providers = ctx.request_context.lifespan_context.get("providers", {})
                k8s_client_info = providers.get("k8s_client", {})
                k8s_client = k8s_client_info.get("client")
                
                if not k8s_client:
                    return {"error": "K8s client not available in lifespan context"}
            except Exception as e:
                logger.error(f"Failed to get K8s client from context: {e}")
                return {"error": "Failed to access lifespan context"}
            
            try:
                resources = []
                
                # 根据资源类型选择合适的 API 客户端
                if resource_type.lower() in ['pod', 'service', 'configmap', 'secret']:
                    api_client = k8s_client['core_v1']
                    if resource_type.lower() == 'pod':
                        if namespace:
                            result = api_client.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
                        else:
                            result = api_client.list_pod_for_all_namespaces(label_selector=label_selector)
                    elif resource_type.lower() == 'service':
                        if namespace:
                            result = api_client.list_namespaced_service(namespace=namespace, label_selector=label_selector)
                        else:
                            result = api_client.list_service_for_all_namespaces(label_selector=label_selector)
                    # 添加更多资源类型...
                elif resource_type.lower() in ['deployment', 'replicaset', 'daemonset', 'statefulset']:
                    api_client = k8s_client['apps_v1']
                    if resource_type.lower() == 'deployment':
                        if namespace:
                            result = api_client.list_namespaced_deployment(namespace=namespace, label_selector=label_selector)
                        else:
                            result = api_client.list_deployment_for_all_namespaces(label_selector=label_selector)
                    # 添加更多资源类型...
                elif resource_type.lower() == 'namespace':
                    api_client = k8s_client['core_v1']
                    result = api_client.list_namespace(label_selector=label_selector)
                else:
                    return {"error": f"Unsupported resource type: {resource_type}"}
                
                # 提取资源信息
                for item in result.items:
                    resource_info = {
                        "name": item.metadata.name,
                        "namespace": getattr(item.metadata, 'namespace', None),
                        "created_time": item.metadata.creation_timestamp,
                        "labels": item.metadata.labels or {},
                        "annotations": item.metadata.annotations or {}
                    }
                    
                    # 添加特定资源类型的额外信息
                    if hasattr(item, 'status'):
                        resource_info['status'] = getattr(item.status, 'phase', 'Unknown')
                    
                    resources.append(resource_info)
                
                return {
                    "resource_type": resource_type,
                    "namespace": namespace,
                    "label_selector": label_selector,
                    "resources": resources,
                    "count": len(resources)
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "resource_type": resource_type,
                    "namespace": namespace,
                    "label_selector": label_selector,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to list resources: {e}")
                return {
                    "resource_type": resource_type,
                    "namespace": namespace,
                    "label_selector": label_selector,
                    "error": str(e),
                    "status": "error"
                }
        
        @self.server.tool(
            name="k8s_resource_create",
            description="Create Kubernetes resource from YAML"
        )
        async def k8s_resource_create(
            yaml_content: str,
            namespace: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Create Kubernetes resource.
            
            Args:
                yaml_content: YAML content of the resource to create
                namespace: Target namespace (optional)
                
            Returns:
                Creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # TODO: Implement resource creation logic
            return {
                "yaml_content": yaml_content[:100] + "..." if len(yaml_content) > 100 else yaml_content,
                "namespace": namespace,
                "status": "created",
                "message": "Resource creation functionality to be implemented"
            }
        
        @self.server.tool(
            name="k8s_resource_delete",
            description="Delete Kubernetes resource"
        )
        async def k8s_resource_delete(
            resource_type: str,
            resource_name: str,
            namespace: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Delete Kubernetes resource.
            
            Args:
                resource_type: Type of Kubernetes resource
                resource_name: Name of the resource to delete
                namespace: Namespace (optional for cluster-scoped resources)
                
            Returns:
                Deletion result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # TODO: Implement resource deletion logic
            return {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "namespace": namespace,
                "status": "deleted",
                "message": "Resource deletion functionality to be implemented"
            }
        
        @self.server.tool(
            name="k8s_resource_patch",
            description="Patch Kubernetes resource"
        )
        async def k8s_resource_patch(
            resource_type: str,
            resource_name: str,
            patch_data: Dict[str, Any],
            namespace: Optional[str] = None,
            patch_type: str = "strategic",
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Patch Kubernetes resource.
            
            Args:
                resource_type: Type of Kubernetes resource
                resource_name: Name of the resource to patch
                patch_data: Patch data
                namespace: Namespace (optional for cluster-scoped resources)
                patch_type: Type of patch (strategic, merge, json)
                
            Returns:
                Patch result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
            # TODO: Implement resource patching logic
            return {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "patch_data": patch_data,
                "namespace": namespace,
                "patch_type": patch_type,
                "status": "patched",
                "message": "Resource patching functionality to be implemented"
            }
        
        @self.server.tool(
            name="k8s_pod_logs",
            description="Get logs from Kubernetes pod"
        )
        async def k8s_pod_logs(
            pod_name: str,
            namespace: str,
            container: Optional[str] = None,
            lines: int = 100,
            follow: bool = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get pod logs.
            
            Args:
                pod_name: Name of the pod
                namespace: Pod namespace
                container: Container name (optional for single-container pods)
                lines: Number of lines to retrieve
                follow: Whether to follow logs
                
            Returns:
                Pod logs
            """
            # TODO: Implement pod logs retrieval logic
            return {
                "pod_name": pod_name,
                "namespace": namespace,
                "container": container,
                "lines": lines,
                "logs": "Pod logs functionality to be implemented",
                "message": "Pod logs retrieval functionality to be implemented"
            }
        
        @self.server.tool(
            name="k8s_events_get",
            description="Get Kubernetes events"
        )
        async def k8s_events_get(
            namespace: Optional[str] = None,
            resource_name: Optional[str] = None,
            resource_type: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get Kubernetes events.
            
            Args:
                namespace: Namespace filter (optional)
                resource_name: Resource name filter (optional)
                resource_type: Resource type filter (optional)
                
            Returns:
                List of events
            """
            # TODO: Implement events retrieval logic
            return {
                "namespace": namespace,
                "resource_name": resource_name,
                "resource_type": resource_type,
                "events": [],
                "message": "Events retrieval functionality to be implemented"
            }
        
        @self.server.tool(
            name="k8s_resource_describe",
            description="Describe Kubernetes resource with detailed information"
        )
        async def k8s_resource_describe(
            resource_type: str,
            resource_name: str,
            namespace: Optional[str] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Describe Kubernetes resource.
            
            Args:
                resource_type: Type of Kubernetes resource
                resource_name: Name of the resource
                namespace: Namespace (optional for cluster-scoped resources)
                
            Returns:
                Detailed resource description
            """
            # TODO: Implement resource description logic
            return {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "namespace": namespace,
                "description": "Resource description functionality to be implemented",
                "message": "Resource description functionality to be implemented"
            }