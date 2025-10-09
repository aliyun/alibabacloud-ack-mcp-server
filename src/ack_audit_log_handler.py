"""ACK Audit Log Handler - Alibaba Cloud Container Service Audit Log Management."""
from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import json
from datetime import datetime, timedelta
from alibabacloud_tea_util import models as util_models

try:
    from .models import (
        QueryAuditLogsInput,
        QueryAuditLogsOutput,
        AuditLogEntry,
        ErrorModel,
        AuditLogErrorCodes,
        GetCurrentTimeOutput
    )
except ImportError:
    from models import (
        QueryAuditLogsInput,
        QueryAuditLogsOutput,
        AuditLogEntry,
        ErrorModel,
        AuditLogErrorCodes,
        GetCurrentTimeOutput
    )


def _get_sls_client(ctx: Context, region_id: str):
    """从 lifespan providers 中获取指定区域的 SLS 客户端（统一入参: region_id, config）。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    factory = providers.get("sls_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("sls_client_factory not available in runtime providers")
    return factory(region_id, config)


def _get_cs_client(ctx: Context, region_id: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = ctx.request_context.lifespan_context
    if isinstance(lifespan_context, dict):
        providers = lifespan_context.get("providers", {})
        config = lifespan_context.get("config", {})
    else:
        providers = getattr(lifespan_context, "providers", {})
        config = getattr(lifespan_context, "config", {}) if hasattr(lifespan_context, "config") else {}

    cs_client_factory = providers.get("cs_client_factory")
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region_id, config)


class ACKAuditLogHandler:
    """Handler for ACK audit log operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK audit log handler.

        Args:
            server: FastMCP server instance
            settings: Configuration settings
        """
        self.cs_client = None
        self.sls_client = None
        self.allow_write = settings.get("allow_write", True) if settings else True
        self.settings = settings or {}
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
        if server is None:
            return
        self.server = server
        # Register tools
        self.server.tool(
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
    - You can use the list_clusters() tool to view available clusters and their IDs.
    - By default, it queries the audit logs for the last 24 hours. The number of returned records is limited to 10 by default."""
        )(self.query_audit_logs)

        self.server.tool(
            name="get_current_time",
            description="获取当前时间，返回 ISO 8601 格式和 Unix 时间戳格式"
        )(self.get_current_time)

        logger.info("ACK Audit Log Handler initialized")

    async def query_audit_logs(self,
                               ctx: Context,
                               cluster_id: str = Field(
                                   ...,
                                   description="The name of the cluster to query audit logs from. if you are not "
                                               "sure, use 'list_clusters' tool to get available clusters."
                               ),
                               namespace: Optional[str] = Field(
                                   None,
                                   description="""(Optional) Match by namespace. 
    Supports exact matching and suffix wildcards:
    - Exact match: "default", "kube-system", "kube-public"
    - Suffix wildcard: "kube*", "app-*" (matches namespaces that start with the specified prefix)"""
                               ),
                               verbs: Optional[str] = Field(
                                   None,
                                   description="""(Optional) Filter by action verbs, multiple values are allowed.
    Can be a JSON array string like '["create", "update"]'.
    Common values:
    - "get": Get a resource
    - "list": List resources
    - "create": Create a resource
    - "update": Update a resource
    - "delete": Delete a resource
    - "patch": Partially update a resource
    - "watch": Watch for changes to a resource"""
                               ),
                               resource_types: Optional[str] = Field(
                                   None,
                                   description="""(Optional) K8s resource type, multiple values are allowed.
    Can be a JSON array string like '["deployments", "pods"]'.
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
    - ISO 8601: "2024-01-01T10:00:00Z"
    - Relative: "30m", "1h", "24h", "7d"
    Defaults to 24h."""
                               ),
                               end_time: Optional[str] = Field(
                                   None,
                                   description="""(Optional) Query end time.
    Formats:
    - ISO 8601: "2024-01-01T10:00:00Z"
    - Relative: "30m", "1h", "24h", "7d"
    Defaults to current time."""
                               ),
                               limit: int = Field(
                                   10,
                                   ge=1, le=100,
                                   description="(Optional) Result limit, defaults to 10. Maximum is 100."
                               )
                               ) -> Dict[str, Any]:
        """Query Kubernetes audit logs."""
        if not cluster_id:
            raise ValueError("cluster_id is required")

        # 预处理参数：将JSON字符串转换为列表
        processed_verbs = self._parse_list_param(verbs)
        processed_resource_types = self._parse_list_param(resource_types)

        return await self.query_audit_log(
            ctx=ctx,
            namespace=namespace,
            verbs=processed_verbs,
            resource_types=processed_resource_types,
            resource_name=resource_name,
            user=user,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            cluster_id=cluster_id
        )

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
            cluster_id: Optional[str] = None
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
            cluster_id=cluster_id
        )

    async def get_current_time(self) -> GetCurrentTimeOutput:
        """获取当前时间

        Returns:
            GetCurrentTimeOutput: 包含当前时间的 ISO 8601 格式和 Unix 时间戳格式
        """
        try:
            from datetime import datetime, timezone

            # 获取当前 UTC 时间
            current_time = datetime.now(timezone.utc)

            # 转换为 ISO 8601 格式
            current_time_iso = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')

            # 转换为 Unix 时间戳（秒级）
            current_time_unix = int(current_time.timestamp())

            return GetCurrentTimeOutput(
                current_time_iso=current_time_iso,
                current_time_unix=current_time_unix,
                timezone="UTC"
            )

        except Exception as e:
            return GetCurrentTimeOutput(
                current_time_iso="",
                current_time_unix=0,
                timezone="UTC",
                error=ErrorModel(
                    error_code="TIME_FETCH_ERROR",
                    error_message=f"Failed to get current time: {str(e)}"
                )
            )

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """标准化参数"""
        if not params.get("start_time"):
            params["start_time"] = "24h"

        # 设置默认限制
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

    def _get_cluster_region(self, cs_client, cluster_id: str) -> str:
        """通过DescribeClusterDetail获取集群的region信息

        Args:
            cs_client: CS客户端实例
            cluster_id: 集群ID

        Returns:
            集群所在的region
        """
        try:
            from alibabacloud_cs20151215 import models as cs_models

            # 调用DescribeClusterDetail API获取集群详情
            detail_response = cs_client.describe_cluster_detail(cluster_id)

            if not detail_response or not detail_response.body:
                raise ValueError(f"Failed to get cluster details for {cluster_id}")

            cluster_info = detail_response.body
            # 获取集群的region信息
            region = getattr(cluster_info, 'region_id', '')

            if not region:
                raise ValueError(f"Could not determine region for cluster {cluster_id}")

            return region

        except Exception as e:
            logger.error(f"Failed to get cluster region for {cluster_id}: {e}")
            raise ValueError(f"Failed to get cluster region for {cluster_id}: {e}")

    def _parse_list_param(self, param: Optional[str]) -> Optional[List[str]]:
        """解析列表参数，将JSON字符串转换为Python列表

        Args:
            param: 可能是JSON字符串或None的参数

        Returns:
            处理后的列表或None
        """
        if param is None:
            return None

        try:
            # 尝试解析JSON字符串
            parsed = json.loads(param)
            if isinstance(parsed, list):
                return parsed
            else:
                # 如果不是列表，包装成列表
                return [str(parsed)]
        except (json.JSONDecodeError, ValueError):
            # 如果JSON解析失败，将字符串作为单个元素
            return [param]

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
            cluster_id: Optional[str] = None
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
            "cluster_id": cluster_id
        }
        if self.cs_client is None:
            cs_client = _get_cs_client(ctx, "CENTER")
            self.cs_client = cs_client
        region_id = self._get_cluster_region(self.cs_client, cluster_id)
        self.sls_client = _get_sls_client(ctx, region_id)

        # Normalize parameters
        normalized_params = self._normalize_params(params)

        try:
            # Query the audit logs using the provider (sync version)
            query = self._build_query(normalized_params)

            # Parse time parameters
            start_time, end_time = self._parse_time_params(normalized_params)

            try:
                if not self.sls_client:
                    raise RuntimeError("SLS client not properly initialized")

                # 一个集群的审计日志 sls project、logstore 需要从OpenAPI中调用后获取 or 能通过配置自定义
                # https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/developer-reference/api-cs-2015-12-15-getclusterauditproject?spm=a2c4g.11186623.0.i5#undefined
                audit_sls_project, audit_sls_logstore = self._get_audit_sls_project_and_logstore(cluster_id)

                # Use real SLS client - 直接调用同步方法
                return self._query_logs(audit_sls_project, audit_sls_logstore, query, start_time, end_time,
                                        normalized_params)

            except Exception as e:
                logger.error(f"Failed to query audit logs: {e}")
                return {
                    "provider_query": query,
                    "entries": [],
                    "total": 0,
                    "params": normalized_params,
                    "error": str(e)
                }

        except Exception as e:
            # Return error message in the expected format
            return {
                "error": str(e),
                "params": normalized_params
            }

    def _parse_single_time(self, time_str: str, default_hours: int = 24) -> datetime:
        """解析时间字符串，支持相对时间和ISO 8601格式"""
        from datetime import datetime, timedelta
        
        if not time_str:
            return datetime.now() - timedelta(hours=default_hours)
            
        # 相对时间格式
        if time_str.endswith('h'):
            return datetime.now() - timedelta(hours=int(time_str[:-1]))
        elif time_str.endswith('d'):
            return datetime.now() - timedelta(days=int(time_str[:-1]))
        elif time_str.endswith('m'):
            return datetime.now() - timedelta(minutes=int(time_str[:-1]))
        elif time_str.endswith('s'):
            return datetime.now() - timedelta(seconds=int(time_str[:-1]))
        elif time_str.endswith('w'):
            return datetime.now() - timedelta(weeks=int(time_str[:-1]))
        else:
            # ISO 8601格式
            try:
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                return datetime.fromisoformat(time_str)
            except ValueError:
                return datetime.now() - timedelta(hours=default_hours)

    def _parse_time_params(self, params: Dict[str, Any]) -> tuple[int, int]:
        """解析时间参数为Unix时间戳"""
        start_time = self._parse_single_time(params.get("start_time", "24h"), default_hours=24)
        end_time = self._parse_single_time(params.get("end_time"), default_hours=0) if params.get("end_time") else datetime.now()
        
        # 确保时间范围合理
        if start_time >= end_time:
            end_time = datetime.now()

        return int(start_time.timestamp()), int(end_time.timestamp())

    def _query_logs(self, project: str, logstore: str, query: str, start_time: int, end_time: int,
                    params: Dict[str, Any]) -> Dict[str, Any]:
        """Query using real SLS client with get_logs API."""
        try:
            from alibabacloud_sls20201230 import models as sls_models

            # 创建GetLogsRequest对象
            request = sls_models.GetLogsRequest(
                from_=start_time,
                to=end_time,
                query=query,  # 查询条件
                offset=0,  # 从第一条开始
                line=params.get("limit", 10),
                reverse=False  # 按时间正序
            )

            # 调用SLS API - 使用get_logs方法
            response = self.sls_client.get_logs(project, logstore, request)
            
            # Parse response - get_logs 返回的是 GetLogsResponse 对象
            entries = []

            # 从response.body获取日志数据（直接是数组）
            try:
                if hasattr(response, 'body') and response.body:
                    # response.body 直接就是日志数组
                    logs_data = response.body if isinstance(response.body, list) else []
                    for log_entry in logs_data:
                        # 解析日志条目，字段都是字符串格式的JSON
                        log_data = {}

                        # 解析各个字段 - 根据真实SLS数据结构，包含所有字段

                        # 解析JSON字符串字段
                        if 'user' in log_entry:
                            try:
                                user_data = json.loads(log_entry['user'])
                                log_data['user'] = user_data
                            except json.JSONDecodeError:
                                log_data['user'] = {"username": log_entry['user']}

                        if 'objectRef' in log_entry:
                            try:
                                object_ref_data = json.loads(log_entry['objectRef'])
                                log_data['objectRef'] = object_ref_data
                            except json.JSONDecodeError:
                                log_data['objectRef'] = {"resource": log_entry['objectRef']}

                        if 'responseStatus' in log_entry:
                            try:
                                response_status_data = json.loads(log_entry['responseStatus'])
                                log_data['responseStatus'] = response_status_data
                            except json.JSONDecodeError:
                                log_data['responseStatus'] = {"code": 0}

                        if 'annotations' in log_entry:
                            try:
                                annotations_data = json.loads(log_entry['annotations'])
                                log_data['annotations'] = annotations_data
                            except json.JSONDecodeError:
                                log_data['annotations'] = log_entry['annotations']

                        if 'sourceIPs' in log_entry:
                            try:
                                source_ips_data = json.loads(log_entry['sourceIPs'])
                                log_data['sourceIPs'] = source_ips_data
                            except json.JSONDecodeError:
                                log_data['sourceIPs'] = [log_entry['sourceIPs']]

                        if 'requestObject' in log_entry:
                            try:
                                request_object_data = json.loads(log_entry['requestObject'])
                                log_data['requestObject'] = request_object_data
                            except json.JSONDecodeError:
                                log_data['requestObject'] = log_entry['requestObject']

                        if 'responseObject' in log_entry:
                            try:
                                response_object_data = json.loads(log_entry['responseObject'])
                                log_data['responseObject'] = response_object_data
                            except json.JSONDecodeError:
                                log_data['responseObject'] = log_entry['responseObject']

                        # 添加所有其他字段
                        log_data['verb'] = log_entry.get('verb', '')
                        log_data['timestamp'] = log_entry.get('requestReceivedTimestamp', '')
                        log_data['kind'] = log_entry.get('kind', '')
                        log_data['apiVersion'] = log_entry.get('apiVersion', '')
                        log_data['auditID'] = log_entry.get('auditID', '')
                        log_data['level'] = log_entry.get('level', '')
                        log_data['requestURI'] = log_entry.get('requestURI', '')
                        log_data['userAgent'] = log_entry.get('userAgent', '')
                        log_data['stage'] = log_entry.get('stage', '')
                        log_data['stageTimestamp'] = log_entry.get('stageTimestamp', '')

                        entries.append(log_data)
            except Exception as e:
                logger.warning(f"Failed to parse response body: {e}")

            return {
                "provider_query": query,
                "entries": entries,
                "total": len(entries),
                "params": params
            }

        except Exception as e:
            logger.error(f"SLS query failed: {e}")
            raise

    def _build_query(self, params: Dict[str, Any]) -> str:
        """Build SLS query string from parameters.

        Args:
            params: Dictionary of query parameters

        Returns:
            Query string for SLS
        """
        query = "*"

        if params.get("user") and params["user"] != "*":
            query += f" and user.username: {params['user']}"

        if params.get("namespace") and params["namespace"] != "*":
            query += f" and objectRef.namespace: {params['namespace']}"

        if params.get("verbs") and len(params["verbs"]) > 0:
            verbs = [f"verb: \"{verb}\"" for verb in params["verbs"]]
            query += f" and ({' or '.join(verbs)})"

        if params.get("resource_types") and len(params["resource_types"]) > 0:
            resource_types = [f"objectRef.resource: \"{rt}\"" for rt in params["resource_types"]]
            query += f" and ({' or '.join(resource_types)})"

        if params.get("resource_name") and params["resource_name"] != "*":
            query += f" and objectRef.name: {params['resource_name']}"

        return query

    def _get_audit_sls_project_and_logstore(self, cluster_id):
        runtime = util_models.RuntimeOptions()
        headers = {}
        try:
            response = self.cs_client.get_cluster_audit_project_with_options(cluster_id, headers, runtime)
            logger.info(f"_get_audit_sls_project_and_logstore response type: {type(response)}")
            if hasattr(response, 'body'):
                if hasattr(response.body, 'sls_project_name'):
                    if response.body.audit_enabled:
                        # get and return
                        return response.body.sls_project_name, f"audit-{cluster_id}"
            # 此集群没有开启审计日志功能
            raise Exception("此集群没有开启审计日志功能")
        except Exception as error:
            logger.error(error)
            raise

