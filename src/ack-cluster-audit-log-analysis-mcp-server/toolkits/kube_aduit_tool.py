"""alibabacloud ack-mcp-server Security Toolkit implementation."""

from datetime import datetime, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any
from pydantic import Field
from ack_cluster_audit_log_analysis_mcp_server.provider.provider import Provider


class KubeAuditTool:
    """Security tools for querying Kubernetes audit logs."""

    def __init__(self, server: FastMCP = None):
        self.server = server
        self.resource_mapping = {
            "pod": "pods",
            "deployment": "deployments",
            "service": "services",
            "svc": "services",
            "configmap": "configmaps",
            "cm": "configmaps",
            "secret": "secrets",
            "sec": "secrets",
            "role": "roles",
            "rolebinding": "rolebindings",
            "clusterrole": "clusterroles",
            "clusterrolebinding": "clusterrolebindings",
            "node": "nodes",
            "namespace": "namespaces",
            "ns": "namespaces",
            "pv": "persistentvolumes",
            "pvc": "persistentvolumeclaims",
            "sa": "serviceaccounts",
            "deploy": "deployments",
            "rs": "replicasets",
            "ds": "daemonsets",
            "sts": "statefulsets",
            "ing": "ingresses",
        }

        # Providers are initialized in lifespan context, no need for registry

        if server:
            self._register_tools()

    def _normalize_params(self, params: Dict[str, Any], ctx: Context = None) -> Dict[str, Any]:
        """Normalize parameters similar to the Go implementation."""
        # Set default cluster if not provided
        if not params.get("cluster_name"):
            # Get default cluster from context
            if ctx:
                # Get from context using request_context.lifespan_context
                lifespan_context = ctx.request_context.lifespan_context
                
                default_cluster = lifespan_context.get("default_cluster", "")
                params["cluster_name"] = default_cluster
        if params["cluster_name"] == "":
            raise ValueError("cluster_name cannot be empty")

        # Set default time range
        if not params.get("start_time"):
            params["start_time"] = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        if not params.get("end_time"):
            params["end_time"] = datetime.utcnow().isoformat()

        # Set default limit
        if not params.get("limit") or params["limit"] <= 0:
            params["limit"] = 10
        elif params["limit"] > 100:
            params["limit"] = 100

        # Normalize resource types
        resource_types = params.get("resource_types", [])
        if resource_types is None:
            resource_types = []
        if isinstance(resource_types, str):
            resource_types = [resource_types]

        new_resource_types = []
        for rt in resource_types:
            if not rt:
                continue
            rt = rt.lower()
            if rt in self.resource_mapping:
                new_resource_types.append(self.resource_mapping[rt])
            else:
                new_resource_types.append(rt)
        params["resource_types"] = new_resource_types

        return params

    def _parse_time(self, time_str: str) -> datetime:
        """Parse time string, supporting both ISO 8601 and relative time formats."""
        if not time_str:
            return datetime.utcnow()

        # Try ISO 8601 format first
        try:
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except ValueError:
            pass

        # Try relative time format
        if time_str.endswith('w'):
            weeks = int(time_str[:-1])
            return datetime.utcnow() - timedelta(weeks=weeks)
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return datetime.utcnow() - timedelta(days=days)
        else:
            # Parse other duration formats
            try:
                # Handle common duration formats like "1h", "30m", etc.
                if time_str.endswith('h'):
                    hours = int(time_str[:-1])
                    return datetime.utcnow() - timedelta(hours=hours)
                elif time_str.endswith('m'):
                    minutes = int(time_str[:-1])
                    return datetime.utcnow() - timedelta(minutes=minutes)
                elif time_str.endswith('s'):
                    seconds = int(time_str[:-1])
                    return datetime.utcnow() - timedelta(seconds=seconds)
            except ValueError:
                pass

        # Default to current time if parsing fails
        return datetime.utcnow()

    def _get_provider_from_context(self, ctx: Context, cluster_name: str = "default") -> Optional[Provider]:
        """Get provider instance from the request context.
        
        This method retrieves the provider from the lifespan context in the request.
        
        Args:
            ctx: FastMCP Context object
            cluster_name: Name of the cluster to get provider for
            
        Returns:
            Provider instance or None if not found
        """
        try:
            # Get from lifespan context using request_context.lifespan_context
            lifespan_context = ctx.request_context.lifespan_context

            # Get providers from the lifespan context
            providers = lifespan_context.get("providers", {})
            default_cluster = lifespan_context.get("default_cluster", "default")

            # Use default cluster if cluster_name is empty or "default"
            if not cluster_name or cluster_name == "default":
                cluster_name = default_cluster

            # Get the provider for the specified cluster
            provider = providers.get(cluster_name)
            if provider:
                return provider

            # Fallback: try to get any available provider
            if providers:
                return list(providers.values())[0]

            return None
        except Exception as e:
            print(f"Warning: Failed to get provider from context: {e}")
            return None

    async def list_clusters(self, ctx: Context) -> Dict[str, Any]:
        """List all configured clusters in the MCP server.
        
        Args:
            ctx: FastMCP Context object
            
        Returns:
            Dictionary containing cluster information
        """
        try:
            # Get the lifespan context from the FastMCP context
            lifespan_context = ctx.request_context.lifespan_context
            
            # Get configuration from the lifespan context
            providers = lifespan_context.get("providers", {})
            default_cluster = lifespan_context.get("default_cluster", "default")
            
            # Build cluster information
            clusters = []
            for cluster_name, provider in providers.items():
                cluster_info = {
                    "name": cluster_name,
                    "description": f"Cluster {cluster_name}",
                    "alias": [],
                    "disabled": False,
                    "provider": provider.__class__.__name__.replace("Provider", "").lower()
                }
                clusters.append(cluster_info)
            
            return {
                "default_cluster": default_cluster,
                "clusters": clusters
            }
        except Exception as e:
            return {
                "default_cluster": "default",
                "clusters": [],
                "error": str(e)
            }

    def query_audit_log_sync(
            self,
            ctx: Context,
            namespace: Optional[str] = None,
            verbs: Optional[List[str]] = None,
            resource_types: Optional[List[str]] = None,
            resource_name: Optional[str] = None,
            user: Optional[str] = None,
            start_time: str = "24h",
            end_time: Optional[str] = None,
            limit: int = 10,
            cluster_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query Kubernetes audit logs (synchronous version)."""
        # Collect parameters into a dict
        params = {
            "namespace": namespace,
            "verbs": verbs,
            "resource_types": resource_types,
            "resource_name": resource_name,
            "user": user,
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit,
            "cluster_name": cluster_name
        }
        
        # Normalize parameters
        normalized_params = self._normalize_params(params, ctx)
        
        try:
            # Try to get the provider from the context first
            provider = self._get_provider_from_context(ctx, cluster_name)
            
            # If no provider in context, create a default one for demonstration
            if not provider:
                raise ValueError("no provider found")
            
            # Query the audit logs using the provider (sync version)
            result = provider.query_audit_log(normalized_params)
            
            # 直接返回provider的结果，参考AuditLogResult格式
            return result
        except Exception as e:
            # Return error message in the expected format
            return {
                "error": str(e),
                "params": normalized_params
            }

    async def query_audit_log(
            self,
            ctx: Context,
            namespace: Optional[str] = None,
            verbs: Optional[List[str]] = None,
            resource_types: Optional[List[str]] = None,
            resource_name: Optional[str] = None,
            user: Optional[str] = None,
            start_time: str = "24h",
            end_time: Optional[str] = None,
            limit: int = 10,
            cluster_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query Kubernetes audit logs (async version for MCP tools)."""
        # 直接调用同步版本
        return self.query_audit_log_sync(
            ctx=ctx,
            namespace=namespace,
            verbs=verbs,
            resource_types=resource_types,
            resource_name=resource_name,
            user=user,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            cluster_name=cluster_name
        )

    def _register_tools(self):
        """Register security-related tools with the MCP server."""

        @self.server.tool(
            name="query_audit_log",
            description="""Query Kubernetes (k8s) audit logs.

    Function Description:
    - Supports multiple time formats (ISO 8601 and relative time).
    - Supports suffix wildcards for namespace, resource name, and user.
    - Supports multiple values for verbs and resource types.
    - Supports both full names and short names for resource types.
    - Allows specifying the cluster name to query audit logs from multiple clusters.
    - Provides detailed parameter validation and error messages.

    Usage Suggestions:
    - If you are uncertain about the resource type, you can call the list_common_resource_types() tool to view common resource types 
      or ask the user to provide the corresponding one.
    - You can use the list_clusters() tool to view available clusters and their names.
    - By default, it queries the audit logs for the last 24 hours. The number of returned records is limited to 10 by default.
    """
        )
        async def query_audit_log_tool(
                ctx: Context,
                namespace: Optional[str] = Field(
                    None,
                    description="""(Optional) Match by namespace. 
    Supports exact matching and suffix wildcards:
    - Exact match: "default", "kube-system", "kube-public"
    - Suffix wildcard: "kube*", "app-*" (matches namespaces that start with the specified prefix)"""
                ),
                verbs: Optional[List[str]] = Field(
                    None,
                    description="""(Optional) Filter by action verbs, multiple values are allowed.

    Common values:
    - "get": Get a resource
    - "list": List resources
    - "create": Create a resource
    - "update": Update a resource
    - "delete": Delete a resource
    - "patch": Partially update a resource
    - "watch": Watch for changes to a resource"""
                ),
                resource_types: Optional[List[str]] = Field(
                    None,
                    description="""(Optional) K8s resource type, multiple values are allowed.

    Supports full names and short names. Common values:
    - Core: pods(pod), services(svc), configmaps(cm), secrets, nodes, namespaces(ns)
    - App: deployments(deploy), replicasets(rs), daemonsets(ds), statefulsets(sts)
    - Storage: persistentvolumes(pv), persistentvolumeclaims(pvc)
    - Network: ingresses(ing), networkpolicies
    - RBAC: roles, rolebindings, clusterroles, clusterrolebindings"""
                ),
                resource_name: Optional[str] = Field(
                    None,
                    description="""(Optional) Match by resource name. 
    Supports exact matching and suffix wildcards:
    - Exact match: "nginx-deployment", "my-service"
    - Suffix wildcard: "nginx-*", "app-*" (matches resource names that start with the specified prefix)
    """
                ),
                user: Optional[str] = Field(
                    None,
                    description="""(Optional) Match by user name. 
    Supports exact matching and suffix wildcards:
    - Exact match: "system:admin", "kubernetes-admin"
    - Suffix wildcard: "system:*", "kube*" """
                ),
                start_time: str = Field(
                    "24h",
                    description="""(Optional) Query start time. 
    Formats:
    - ISO 8601: "2024-01-01T10:00:00"
    - Relative: "30m", "1h", "24h", "7d"
    Defaults to 24h."""
                ),
                end_time: Optional[str] = Field(
                    None,
                    description="""(Optional) Query end time.
    Formats:
    - ISO 8601: "2024-01-01T10:00:00"
    - Relative: "30m", "1h", "24h", "7d"
    Defaults to current time."""
                ),
                limit: int = Field(
                    10,
                    ge=1, le=100,
                    description="(Optional) Result limit, defaults to 10. Maximum is 100."
                ),
                cluster_name: Optional[str] = Field(
                    None,
                    description="(Optional) The name of the cluster to query audit logs from."
                )
        ) -> Dict[str, Any]:
            """Query Kubernetes audit logs."""
            return await self.query_audit_log(
                ctx=ctx,
                namespace=namespace,
                verbs=verbs,
                resource_types=resource_types,
                resource_name=resource_name,
                user=user,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                cluster_name=cluster_name
            )

        @self.server.tool(
            name="list_clusters",
            description="List all configured clusters in the MCP server."
        )
        async def list_clusters_tool(ctx: Context) -> Dict[str, Any]:
            """List all configured clusters in the MCP server.
            
            Returns information about all available clusters including their names,
            descriptions, providers, and status.
            """
            return await self.list_clusters(ctx=ctx)

