"""Kubernetes Client Handler."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
import yaml
from kubernetes.client.rest import ApiException
import json


def _serialize_sdk_object(obj):
    """序列化Kubernetes SDK对象为可JSON序列化的字典."""
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
        # 对于Kubernetes SDK对象，通常有to_dict()方法
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        
        # 对于其他对象，尝试获取其__dict__属性
        if hasattr(obj, '__dict__'):
            return _serialize_sdk_object(obj.__dict__)
        
        # 尝试转换为字符串
        return str(obj)
    except Exception:
        # 如果都失败了，返回字符串表示
        return str(obj)


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
                resource_dict = _serialize_sdk_object(resource)
                yaml_content = yaml.dump(resource_dict, default_flow_style=False)
                
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
                if hasattr(result, 'items'):
                    for item in result.items:
                        resource_info = {
                            "name": getattr(item.metadata, 'name', None),
                            "namespace": getattr(item.metadata, 'namespace', None),
                            "created_time": getattr(item.metadata, 'creation_timestamp', None),
                            "labels": _serialize_sdk_object(getattr(item.metadata, 'labels', None)) or {},
                            "annotations": _serialize_sdk_object(getattr(item.metadata, 'annotations', None)) or {}
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
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Creation result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
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
                # 解析YAML内容
                resource_data = yaml.safe_load(yaml_content)
                resource_kind = resource_data.get('kind', '').lower()
                
                # 根据资源类型选择合适的 API 客户端
                if resource_kind in ['pod', 'service', 'configmap', 'secret']:
                    api_client = k8s_client['core_v1']
                    if resource_kind == 'pod':
                        if namespace:
                            result = api_client.create_namespaced_pod(namespace=namespace, body=resource_data)
                        else:
                            return {"error": "Namespace is required for pod resources"}
                    elif resource_kind == 'service':
                        if namespace:
                            result = api_client.create_namespaced_service(namespace=namespace, body=resource_data)
                        else:
                            return {"error": "Namespace is required for service resources"}
                    # 添加更多资源类型...
                elif resource_kind in ['deployment', 'replicaset', 'daemonset', 'statefulset']:
                    api_client = k8s_client['apps_v1']
                    if resource_kind == 'deployment':
                        if namespace:
                            result = api_client.create_namespaced_deployment(namespace=namespace, body=resource_data)
                        else:
                            return {"error": "Namespace is required for deployment resources"}
                    # 添加更多资源类型...
                else:
                    return {"error": f"Unsupported resource type: {resource_kind}"}
                
                # 序列化创建结果
                result_data = _serialize_sdk_object(result)
                
                return {
                    "yaml_content": yaml_content[:100] + "..." if len(yaml_content) > 100 else yaml_content,
                    "namespace": namespace,
                    "result": result_data,
                    "status": "created"
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "yaml_content": yaml_content[:100] + "..." if len(yaml_content) > 100 else yaml_content,
                    "namespace": namespace,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to create resource: {e}")
                return {
                    "yaml_content": yaml_content[:100] + "..." if len(yaml_content) > 100 else yaml_content,
                    "namespace": namespace,
                    "error": str(e),
                    "status": "error"
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
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Deletion result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
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
                if resource_type.lower() in ['pod', 'service', 'configmap', 'secret']:
                    api_client = k8s_client['core_v1']
                    if resource_type.lower() == 'pod':
                        if namespace:
                            result = api_client.delete_namespaced_pod(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for pod resources"}
                    elif resource_type.lower() == 'service':
                        if namespace:
                            result = api_client.delete_namespaced_service(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for service resources"}
                    # 添加更多资源类型...
                elif resource_type.lower() in ['deployment', 'replicaset', 'daemonset', 'statefulset']:
                    api_client = k8s_client['apps_v1']
                    if resource_type.lower() == 'deployment':
                        if namespace:
                            result = api_client.delete_namespaced_deployment(name=resource_name, namespace=namespace)
                        else:
                            return {"error": "Namespace is required for deployment resources"}
                    # 添加更多资源类型...
                elif resource_type.lower() == 'namespace':
                    api_client = k8s_client['core_v1']
                    result = api_client.delete_namespace(name=resource_name)
                else:
                    return {"error": f"Unsupported resource type: {resource_type}"}
                
                # 序列化删除结果
                result_data = _serialize_sdk_object(result)
                
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "result": result_data,
                    "status": "deleted"
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
                logger.error(f"Failed to delete resource: {e}")
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "namespace": namespace,
                    "error": str(e),
                    "status": "error"
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
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Patch result
            """
            if not self.allow_write:
                return {"error": "Write operations are disabled"}
            
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
                # 根据补丁类型选择合适的补丁选项
                if patch_type == "merge":
                    patch_options = {"content_type": "application/merge-patch+json"}
                elif patch_type == "json":
                    patch_options = {"content_type": "application/json-patch+json"}
                else:  # strategic
                    patch_options = {"content_type": "application/strategic-merge-patch+json"}
                
                # 根据资源类型选择合适的 API 客户端
                if resource_type.lower() in ['pod', 'service', 'configmap', 'secret']:
                    api_client = k8s_client['core_v1']
                    if resource_type.lower() == 'pod':
                        if namespace:
                            result = api_client.patch_namespaced_pod(
                                name=resource_name, namespace=namespace, body=patch_data, **patch_options
                            )
                        else:
                            return {"error": "Namespace is required for pod resources"}
                    elif resource_type.lower() == 'service':
                        if namespace:
                            result = api_client.patch_namespaced_service(
                                name=resource_name, namespace=namespace, body=patch_data, **patch_options
                            )
                        else:
                            return {"error": "Namespace is required for service resources"}
                    # 添加更多资源类型...
                elif resource_type.lower() in ['deployment', 'replicaset', 'daemonset', 'statefulset']:
                    api_client = k8s_client['apps_v1']
                    if resource_type.lower() == 'deployment':
                        if namespace:
                            result = api_client.patch_namespaced_deployment(
                                name=resource_name, namespace=namespace, body=patch_data, **patch_options
                            )
                        else:
                            return {"error": "Namespace is required for deployment resources"}
                    # 添加更多资源类型...
                else:
                    return {"error": f"Unsupported resource type: {resource_type}"}
                
                # 序列化补丁结果
                result_data = _serialize_sdk_object(result)
                
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "patch_data": patch_data,
                    "namespace": namespace,
                    "patch_type": patch_type,
                    "result": result_data,
                    "status": "patched"
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "patch_data": patch_data,
                    "namespace": namespace,
                    "patch_type": patch_type,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to patch resource: {e}")
                return {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "patch_data": patch_data,
                    "namespace": namespace,
                    "patch_type": patch_type,
                    "error": str(e),
                    "status": "error"
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
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                Pod logs
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
                api_client = k8s_client['core_v1']
                
                # 获取日志
                if container:
                    logs = api_client.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container,
                        tail_lines=lines,
                        follow=follow
                    )
                else:
                    logs = api_client.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        tail_lines=lines,
                        follow=follow
                    )
                
                return {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "container": container,
                    "lines": lines,
                    "logs": logs
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "container": container,
                    "lines": lines,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to get pod logs: {e}")
                return {
                    "pod_name": pod_name,
                    "namespace": namespace,
                    "container": container,
                    "lines": lines,
                    "error": str(e),
                    "status": "error"
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
                ctx: FastMCP context containing lifespan providers
                
            Returns:
                List of events
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
                api_client = k8s_client['core_v1']
                
                # 构建事件查询参数
                field_selector = None
                if resource_name and resource_type:
                    field_selector = f"involvedObject.name={resource_name},involvedObject.kind={resource_type}"
                elif resource_name:
                    field_selector = f"involvedObject.name={resource_name}"
                
                # 获取事件
                if namespace:
                    events = api_client.list_namespaced_event(
                        namespace=namespace,
                        field_selector=field_selector
                    )
                else:
                    events = api_client.list_event_for_all_namespaces(
                        field_selector=field_selector
                    )
                
                # 序列化事件数据
                events_data = []
                if hasattr(events, 'items'):
                    for event in events.items:
                        event_info = {
                            "name": getattr(event.metadata, 'name', None),
                            "namespace": getattr(event.metadata, 'namespace', None),
                            "reason": getattr(event, 'reason', None),
                            "message": getattr(event, 'message', None),
                            "source": _serialize_sdk_object(getattr(event, 'source', None)),
                            "first_timestamp": getattr(event, 'first_timestamp', None),
                            "last_timestamp": getattr(event, 'last_timestamp', None),
                            "count": getattr(event, 'count', None),
                            "type": getattr(event, 'type', None),
                            "involved_object": _serialize_sdk_object(getattr(event, 'involved_object', None))
                        }
                        events_data.append(event_info)
                
                return {
                    "namespace": namespace,
                    "resource_name": resource_name,
                    "resource_type": resource_type,
                    "events": events_data,
                    "count": len(events_data)
                }
                
            except ApiException as e:
                logger.error(f"Kubernetes API error: {e}")
                return {
                    "namespace": namespace,
                    "resource_name": resource_name,
                    "resource_type": resource_type,
                    "error": f"Kubernetes API error: {e.reason}",
                    "status": "error"
                }
            except Exception as e:
                logger.error(f"Failed to get events: {e}")
                return {
                    "namespace": namespace,
                    "resource_name": resource_name,
                    "resource_type": resource_type,
                    "error": str(e),
                    "status": "error"
                }