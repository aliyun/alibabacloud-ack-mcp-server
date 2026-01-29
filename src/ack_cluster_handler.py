"""
ACK Cluster Handler Module

This module provides management and query functionality for Alibaba Cloud Container Service (ACK) clusters,
including cluster listing, node pool management, node queries, and task tracking operations.
"""

from enum import Enum
from typing import Annotated, Dict, Any, Optional, List
from datetime import datetime, timezone
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from pydantic import Field
import json
import time
import re
from models import (
    ListClustersOutput,
    ClusterInfo,
    ErrorModel,
    ClusterErrorCodes,
    ListClusterNodepoolsOutput,
    ListClusterNodesOutput,
    ListClusterTasksOutput,
    ExecutionLog,
    enable_execution_log_ctx,
)
from ack_cluster_helpers import (
    filter_nodepool,
    filter_node,
    filter_task,
    parse_time_range,
    task_matches_filters,
    extract_page_info,
)


def _serialize_sdk_object(obj):
    """序列化阿里云 SDK 对象为可 JSON 的字典。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize_sdk_object(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize_sdk_object(v) for k, v in obj.items()}
    try:
        if hasattr(obj, "to_map"):
            return obj.to_map()
        if hasattr(obj, "__dict__"):
            return _serialize_sdk_object(obj.__dict__)
    except Exception:
        pass
    return str(obj)


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    cs_client_factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region, config)


async def _get_cluster_region(ctx: Context, cluster_id: str) -> str:
    """通过 DescribeClusterDetail 获取集群的 region_id。"""
    cs_client = _get_cs_client(ctx, "CENTER")
    detail_response = await cs_client.describe_cluster_detail_async(cluster_id)
    if not detail_response or not detail_response.body:
        raise ValueError(f"Failed to get cluster details for {cluster_id}")
    region = getattr(detail_response.body, "region_id", "") or ""
    if not region:
        raise ValueError(f"Could not determine region for cluster {cluster_id}")
    return region


class ClusterNodeState(Enum):
    ALL = "all"
    RUNNING = "running"
    REMOVING = "removing"
    INITIAL = "initial"
    FAILED = "failed"


class ClusterTaskState(Enum):
    # ALL = "all"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    RESUMING = "resuming"
    CANCELLING = "cancelling"
    CANCELED = "canceled"
    SUCCESS = "success"
    FAIL = "fail"
    FAILED = "failed"


class ClusterTaskType(Enum):
    NODEPOOL_CREATE = "nodepool_create"
    NODEPOOL_DELETE = "nodepool_delete"
    NODEPOOL_UPDATE = "nodepool_update"
    NODEPOOL_SCALEOUT = "nodepool_scaleout"
    NODEPOOL_SCALEIN = "nodepool_scalein"
    NODEPOOL_NODE_ATTACH = "nodepool_node_attach"
    NODEPOOL_NODE_REMOVE = "nodepool_node_remove"
    NODEPOOL_UPGRADE = "nodepool_upgrade"
    NODEPOOL_CVE_FIX = "nodepool_cve_fix"
    NODEPOOL_NODE_OS_CONFIG_ROLLOUT = "nodepool_node_os_config_rollout"
    NODEPOOL_NODE_KUBELET_CONFIG_ROLLOUT = "nodepool_node_kubelet_config_rollout"
    NODEPOOL_NODE_CONTAINERD_CONFIG_ROLLOUT = "nodepool_node_containerd_config_rollout"


# ACK cluster_id 规范：以 c 开头，后跟小写字母、数字，长度 33
_CLUSTER_ID_PATTERN = re.compile(r"^c[a-z0-9]{32}$")

# ACK nodepool_id 规范：以 np 开头，后跟小写字母、数字，长度通常为 32-40
_NODEPOOL_ID_PATTERN = re.compile(r"^np[a-z0-9]{32}$")

# list_cluster_tasks 的 task_type 可选值说明
_CLUSTER_TASK_TYPE_DESC = f"任务类型: {",".join(str(i.value) for i in list(ClusterTaskType))}"


# the state of the cluster node

_NODE_STATE_DESCRIPTIONS = {
    "all": "不按照运行状态进行过滤，查询所有状态的节点。",
    "running": "正在运行的集群节点。",
    "removing": "正在删除的集群节点。",
    "initial": "正在初始化的集群节点。",
    "failed": "创建失败的集群节点。",
}
_CLUSTER_NODE_STATE_DESC = f"集群节点状态，按照集群节点运行状态进行过滤，默认值 all。取值：{_NODE_STATE_DESCRIPTIONS}"


_CLUSTER_TASK_STATE_DESC = f"任务状态筛选，取值：{",".join(str(i.value) for i in list(ClusterTaskState))}"


def _cs_runtime_headers() -> tuple:
    """CS 请求通用的 runtime 与 headers。"""
    return util_models.RuntimeOptions(), {}


async def _fetch_nodepool_detail(
    client: Any, cluster_id: str, nodepool_id: str, serialize: Any
) -> List[Dict[str, Any]]:
    """调用 DescribeClusterNodePoolDetail，返回单条详情列表（0 或 1 项）。"""
    runtime, headers = _cs_runtime_headers()
    response = await client.describe_cluster_node_pool_detail_with_options_async(
        cluster_id, nodepool_id, headers, runtime
    )
    detail = serialize(response.body) if response.body else {}
    return [detail] if detail else []


async def _fetch_nodepools_list(client: Any, cluster_id: str, serialize: Any) -> List[Dict[str, Any]]:
    """调用 DescribeClusterNodePools，返回节点池列表（未分页、未过滤字段）。"""
    runtime, headers = _cs_runtime_headers()
    request = cs20151215_models.DescribeClusterNodePoolsRequest()
    response = await client.describe_cluster_node_pools_with_options_async(cluster_id, request, headers, runtime)
    raw = serialize(response.body.nodepools) if (response.body and response.body.nodepools) else []
    return raw if isinstance(raw, list) else []


async def _fetch_nodes_page(
    client: Any,
    cluster_id: str,
    page_number: int,
    page_size: int,
    nodepool_id: Optional[str],
    serialize: Any,
    *,
    instance_ids: Optional[List[str]] = None,
    node_names: Optional[List[str]] = None,
    state: Optional[ClusterNodeState] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """调用 DescribeClusterNodes 一页，返回 (nodes, page_info_dict)。支持 instance_ids 过滤。"""
    runtime, headers = _cs_runtime_headers()
    req_kw: Dict[str, Any] = {
        "page_number": page_number,
        "page_size": page_size,
        "nodepool_id": nodepool_id,
    }
    if state:
        req_kw["state"] = state.value
    if instance_ids:
        # API 接受逗号分隔；部分 SDK 需字符串，部分接受 list
        req_kw["instance_ids"] = ",".join(str(i) for i in instance_ids)
    request = cs20151215_models.DescribeClusterNodesRequest(**req_kw)
    response = await client.describe_cluster_nodes_with_options_async(cluster_id, request, headers, runtime)
    nodes = serialize(response.body.nodes) if (response.body and response.body.nodes) else []
    nodes = nodes if isinstance(nodes, list) else []
    if instance_ids:
        ids = {str(i) for i in instance_ids}
        nodes = [n for n in nodes if (v := (n.get("instance_id") or n.get("instanceId"))) is not None and str(v) in ids]
    if node_names:
        names = {str(i) for i in node_names}
        nodes = [n for n in nodes if (v := (n.get("node_name") or n.get("nodeName"))) is not None and str(v) in names]
    page_info = extract_page_info(response.body, serialize)
    return nodes, page_info


async def _fetch_tasks_page(
    client: Any,
    cluster_id: str,
    page_number: int,
    page_size: int,
    serialize: Any,
    *,
    state: Optional[ClusterTaskState] = None,
    task_type: Optional[ClusterTaskType] = None,
    target_id: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """调用 DescribeClusterTasks 一页（call_api 风格），返回 (tasks, page_info_dict)。支持 state、type、target_id；默认带 detail=true。"""
    runtime, _ = _cs_runtime_headers()
    query: Dict[str, str] = {
        "page_number": str(page_number),
        "page_size": str(page_size),
        "detail": "true",
    }
    if state:
        query["state"] = state.value
    if task_type:
        query["type"] = task_type.value
    if target_id:
        query["target_id"] = target_id

    params = open_api_models.Params(
        action="DescribeClusterTasks",
        version="2015-12-15",
        protocol="HTTPS",
        method="GET",
        auth_type="AK",
        style="ROA",
        pathname=f"/clusters/{cluster_id}/tasks",
        req_body_type="json",
        body_type="json",
    )
    request = open_api_models.OpenApiRequest(query=query)
    resp = await client.call_api_async(params, request, runtime)
    body = resp.get("body")
    body = body if isinstance(body, dict) else {}
    raw = body.get("tasks") or body.get("Tasks") or []
    tasks = serialize(raw) if raw else []
    return tasks, extract_page_info(body, serialize)


async def _map_instance_id_to_node_name(
    client: Any,
    cluster_id: str,
    instance_id: str,
    serialize: Any,
) -> Optional[str]:
    """通过 list_cluster_nodes 将 instance_id 映射为 node_name。

    Args:
        client: CS 客户端
        cluster_id: 集群ID
        instance_id: 实例ID
        serialize: 序列化函数

    Returns:
        如果找到匹配的节点，返回 node_name；否则返回 None
    """
    try:
        nodes, _ = await _fetch_nodes_page(
            client,
            cluster_id,
            1,
            100,
            None,
            serialize,
            instance_ids=[instance_id],
        )
        if nodes:
            # 找到匹配的节点，获取 node_name
            for node in nodes:
                node_instance_id = node.get("instance_id")
                if node_instance_id and str(node_instance_id) == str(instance_id):
                    node_name = node.get("node_name")
                    if node_name:
                        logger.debug(f"Mapped instance_id {instance_id} to node_name {node_name}")
                        return node_name
    except Exception as e:
        logger.warning(f"Failed to map instance_id {instance_id} to node_name: {e}")
    return None


def parse_master_url(master_url: str) -> dict:
    """从 master_url JSON 解析 api_server_endpoint、intranet_api_server_endpoint。"""
    out = {"api_server_endpoint": "", "intranet_api_server_endpoint": ""}
    if not master_url:
        return out
    try:
        d = json.loads(master_url)
        if isinstance(d, dict):
            out["api_server_endpoint"] = d.get("api_server_endpoint") or ""
            out["intranet_api_server_endpoint"] = d.get("intranet_api_server_endpoint") or ""
    except json.JSONDecodeError as e:
        logger.debug(f"parse_master_url JSON error: {e}")
    return out


def _parse_cluster_info(d: Dict[str, Any]) -> Optional[ClusterInfo]:
    """从 DescribeClustersV1 单条解析为 ClusterInfo，必填缺失时返回 None。"""
    try:
        name = d.get("name") or d.get("cluster_name") or ""
        cid = d.get("cluster_id") or d.get("clusterId") or ""
        state = d.get("state") or d.get("cluster_state") or d.get("status") or ""
        ctype = d.get("cluster_type") or d.get("clusterType") or ""
        if not all((name, cid, state, ctype)):
            logger.warning(f"Skipping cluster with missing required fields: {d}")
            return None
        return ClusterInfo(
            cluster_name=name,
            cluster_id=cid,
            state=state,
            cluster_type=ctype,
            region_id=d.get("region_id"),
            current_version=d.get("current_version"),
            vpc_id=d.get("vpc_id"),
            vswitch_ids=d.get("vswitch_ids"),
            resource_group_id=d.get("resource_group_id"),
            security_group_id=d.get("security_group_id"),
            proxy_mode=d.get("proxy_mode"),
            tags=d.get("tags"),
            container_cidr=d.get("container_cidr"),
            service_cidr=d.get("service_cidr"),
            api_server_endpoints=parse_master_url(d.get("master_url", "")),
        )
    except Exception as e:
        logger.warning(f"Failed to parse cluster data: {e}")
        return None


class ACKClusterHandler:
    """
    ACK (Alibaba Cloud Container Service for Kubernetes) Cluster Management Handler

    Provides query functions for clusters, node pools, nodes, and tasks with support for pagination and filtering.
    All methods include execution log recording and error handling mechanisms.
    """

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """
        Initialize the ACK cluster handler

        Args:
            enable_execution_log: Whether to enable execution log recording
        """
        self.settings = settings or {}
        # Per-handler ExecutionLog output toggle

        # 是否可写变更配置
        self.allow_write = self.settings.get("allow_write", False)

        # Per-handler toggle
        self.enable_execution_log = self.settings.get("enable_execution_log", False)

        if server is None:
            return
        self.server = server
        # Register tools
        self.server.tool(name="list_clusters", description="获取所有region下所有ACK集群列表，默认返回最多10个集群")(
            self.list_clusters
        )
        self.server.tool(
            name="list_cluster_nodepools", description="查询ACK集群的节点池列表，默认返回10个节点池，支持分页查询。"
        )(self.list_cluster_nodepools)
        self.server.tool(
            name="list_cluster_nodes",
            description="查询ACK集群的节点列表，支持 instance_ids 指定实例；默认分页。可先查 node_name 再与 list_cluster_tasks 的 node_name、instance_id 并集过滤配合。",
        )(self.list_cluster_nodes)
        self.server.tool(
            name="list_cluster_tasks",
            description="查询ACK集群的任务列表，支持分页（page_number、page_size）、instance_id（会自动映射为 node_name）、节点池、时间、状态与类型；默认带 detail，最近30分钟。",
        )(self.list_cluster_tasks)

        logger.info("ACK Addon Management Handler initialized")

    async def list_clusters(
        self,
        ctx: Context,
        page_size: Annotated[int, Field(description="查询每个region集群列表的分页页码")] = 10,
        page_num: Annotated[int, Field(description="查询每个region集群列表的分页页码")] = 1,
    ) -> ListClustersOutput:
        """
        Retrieve all ACK clusters from all regions, returning up to 10 clusters by default.

        Args:
            ctx: FastMCP context containing lifespan providers
            page_size: Number of clusters to return per page, default is 10
            page_num: Page number for pagination, default is 1

        Returns:
            ListClustersOutput: Contains cluster list and execution log

        Raises:
            Exception: Raised when retrieving clusters fails
        """

        # Initialize execution log
        enable_execution_log_ctx.set(self.enable_execution_log)
        now = datetime.now(timezone.utc)
        start_ms = now.timestamp() * 1000
        execution_log = ExecutionLog(
            tool_call_id=f"list_clusters_{start_ms}",
            start_time=now.isoformat(),
        )

        try:
            cs_client = _get_cs_client(ctx, "CENTER")

            # 构建请求
            actual_page_size = min(page_size or 10, 500)
            actual_page_num = page_num or 1

            request = cs20151215_models.DescribeClustersV1Request(
                page_size=actual_page_size,
                page_number=actual_page_num,
            )
            runtime, headers = util_models.RuntimeOptions(), {}

            # 调用 API
            api_start = int(time.time() * 1000)
            execution_log.messages.append("Calling DescribeClusters API")

            try:
                response = await cs_client.describe_clusters_v1with_options_async(request, headers, runtime)
                api_duration = int(time.time() * 1000) - api_start

                execution_log.api_calls.append(
                    {
                        "api": "DescribeClustersV1",
                        "region": "CENTER",
                        "request_params": {"page_size": actual_page_size, "page_number": actual_page_num},
                        "duration_ms": api_duration,
                        "status": "success",
                    }
                )
                execution_log.messages.append(f"API call succeeded in {api_duration}ms")
            except Exception as api_error:
                api_duration = int(time.time() * 1000) - api_start
                execution_log.api_calls.append(
                    {
                        "api": "DescribeClustersV1",
                        "region": "CENTER",
                        "request_params": {"page_size": actual_page_size, "page_number": actual_page_num},
                        "duration_ms": api_duration,
                        "status": "failed",
                        "error": str(api_error),
                    }
                )
                execution_log.messages.append(f"API call failed after {api_duration}ms: {str(api_error)}")
                raise api_error

            # 处理响应
            request_id = (
                response.headers.get("x-acs-request-id", "N/A")
                if hasattr(response, "headers") and response.headers
                else "N/A"
            )
            execution_log.messages.append(f"Processing API response, requestId: {request_id}")
            clusters_data = (
                _serialize_sdk_object(response.body.clusters) if response.body and response.body.clusters else []
            )
            execution_log.messages.append(f"Retrieved {len(clusters_data)} raw cluster records")

            clusters = []
            skipped_count = 0

            for cluster_data in clusters_data:
                cluster_info = _parse_cluster_info(cluster_data)
                if not cluster_info:
                    execution_log.warnings.append(f"Failed to parse cluster data: {cluster_data}")
                    skipped_count += 1
                    continue
                clusters.append(cluster_info)

            if skipped_count > 0:
                execution_log.warnings.append(f"Skipped {skipped_count} clusters with missing required fields")

            execution_log.messages.append(f"Successfully list {len(clusters)} clusters")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)

            return ListClustersOutput(count=len(clusters), clusters=clusters, execution_log=execution_log)

        except Exception as e:
            logger.error(f"Failed to list clusters: {e}")
            error_message = str(e)
            error_code = ClusterErrorCodes.NO_RAM_POLICY_AUTH

            # 根据错误信息判断具体的错误码
            if "region" in error_message.lower() or "region_id" in error_message.lower():
                error_code = ClusterErrorCodes.MISS_REGION_ID

            execution_log.error = error_message
            execution_log.messages.append(f"Operation failed: {error_message}")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)
            execution_log.metadata = {"error_code": error_code, "failure_stage": "list_clusters_operation"}

            return ListClustersOutput(
                count=0,
                error=ErrorModel(error_code=error_code, error_message=error_message),
                clusters=[],
                execution_log=execution_log,
            )

    async def list_cluster_nodepools(
        self,
        ctx: Context,
        cluster_id: Annotated[str, Field(description="集群ID，必填", pattern=_CLUSTER_ID_PATTERN)],
        nodepool_id: Annotated[
            Optional[str], Field(description="节点池ID，可选；只返回该节点池下的节点", pattern=_NODEPOOL_ID_PATTERN)
        ] = None,
        page_number: Annotated[
            int, Field(description="查询集群内节点池分页参数，默认1；仅在不指定 nodepool_id 时生效")
        ] = 1,
        page_size: Annotated[
            int, Field(description="查询集群内节点池分页参数，默认10；仅在不指定 nodepool_id 时生效")
        ] = 10,
    ) -> ListClusterNodepoolsOutput:
        """
        Query cluster node pools: uses DescribeClusterNodePoolDetail when nodepool_id is specified;
        otherwise uses DescribeClusterNodePools with pagination.

        Args:
            ctx: FastMCP context containing lifespan providers
            cluster_id: Unique identifier for the cluster
            nodepool_id: Optional, returns only this specific node pool
            page_number: Page number for pagination, default is 1
            page_size: Number of results per page, default is 10, maximum 100

        Returns:
            ListClusterNodepoolsOutput: Contains node pool list and execution log

        Raises:
            Exception: Raised when retrieving cluster node pools fails
        """

        enable_execution_log_ctx.set(self.enable_execution_log)
        now = datetime.now(timezone.utc)
        start_ms = now.timestamp() * 1000
        execution_log = ExecutionLog(
            tool_call_id=f"list_cluster_nodepools_{start_ms}",
            start_time=now.isoformat(),
        )
        try:
            region_id = await _get_cluster_region(ctx, cluster_id)
            cs = _get_cs_client(ctx, region_id)

            if nodepool_id:
                raw = await _fetch_nodepool_detail(cs, cluster_id, nodepool_id, _serialize_sdk_object)
                items = [filter_nodepool(x) for x in raw]
                return ListClusterNodepoolsOutput(
                    count=len(items), total_count=len(items), nodepools=items, page_number=1, page_size=1
                )

            all_raw = await _fetch_nodepools_list(cs, cluster_id, _serialize_sdk_object)
            total_count = len(all_raw)
            ps = max(1, int(page_size or 10))
            pn = max(1, int(page_number or 1))
            start = (pn - 1) * ps
            page = all_raw[start : start + ps]
            items = [filter_nodepool(x) for x in page]

            execution_log.messages.append(f"Successfully list {len(items)} nodepools")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)

            return ListClusterNodepoolsOutput(
                count=len(items),
                total_count=total_count,
                nodepools=items,
                page_number=pn,
                page_size=ps,
                execution_log=execution_log,
            )
        except Exception as e:
            logger.error(f"Failed to list cluster nodepools: {e}")
            execution_log.messages.append(f"Failed list cluster nodepools, error: {e}")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)
            execution_log.error = str(e)
            return ListClusterNodepoolsOutput(
                count=0,
                error=ErrorModel(error_code="ListClusterNodePoolsError", error_message=str(e)),
                execution_log=execution_log,
            )

    async def list_cluster_nodes(
        self,
        ctx: Context,
        cluster_id: Annotated[str, Field(description="集群ID，必填", pattern=_CLUSTER_ID_PATTERN)],
        nodepool_id: Annotated[
            Optional[str], Field(description="节点池ID，可选；只返回该节点池下的节点", pattern=_NODEPOOL_ID_PATTERN)
        ] = None,
        instance_ids: Annotated[
            list[str],
            Field(
                description="实例ID列表，只返回这些实例的节点；与 node_names 参数互斥；可先查得 node_name 再与 list_cluster_tasks 的 node_name、instance_id 并集过滤配合使用"
            ),
        ] = [],
        node_names: Annotated[
            list[str], Field(description="节点名称列表，只返回这些名称的节点；与 instance_ids 参数互斥")
        ] = [],
        state: Annotated[Optional[ClusterNodeState], Field(description=_CLUSTER_NODE_STATE_DESC)] = None,
        page_number: Annotated[int, Field(description="页码，默认1")] = 1,
        page_size: Annotated[int, Field(description="每页数量，默认10", le=100, ge=1)] = 10,
    ) -> ListClusterNodesOutput:
        """
        Query cluster node list (DescribeClusterNodes), supports instance_ids; paginated by default.

        Args:
            ctx: FastMCP context containing lifespan providers
            cluster_id: Unique identifier for the cluster
            instance_ids: Optional, only return nodes for these instance IDs
            node_names: Optional, only return nodes with these names (mutually exclusive with instance_ids)
            nodepool_id: Optional, only return nodes from this node pool
            state: Optional, filter by node state
            page_number: Page number for pagination, default is 1
            page_size: Number of results per page, default is 10, maximum 100

        Returns:
            ListClusterNodesOutput: Contains node list and execution log

        Raises:
            Exception: Raised when querying cluster nodes fails
        """

        enable_execution_log_ctx.set(self.enable_execution_log)
        now = datetime.now(timezone.utc)
        start_ms = now.timestamp() * 1000
        execution_log = ExecutionLog(
            tool_call_id=f"list_cluster_nodes_{start_ms}",
            start_time=now.isoformat(),
        )
        try:
            region_id = await _get_cluster_region(ctx, cluster_id)
            cs = _get_cs_client(ctx, region_id)

            nodes, page_info = await _fetch_nodes_page(
                cs,
                cluster_id,
                page_number,
                page_size,
                nodepool_id,
                _serialize_sdk_object,
                instance_ids=instance_ids,
                node_names=node_names,
                state=state,
            )
            items = [filter_node(n) for n in nodes]
            pi = page_info or {}
            total = pi.get("total_count") or pi.get("total") or len(items)

            execution_log.messages.append(f"Successfully list {len(items)} nodes")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)

            return ListClusterNodesOutput(
                count=len(items),
                total_count=total if isinstance(total, int) else None,
                nodes=items,
                page_number=page_number,
                page_size=page_size,
                execution_log=execution_log,
            )
        except Exception as e:
            logger.error(f"list_cluster_nodes failed: {e}")
            execution_log.messages.append(f"Failed list cluster nodes: {e}")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)
            execution_log.error = str(e)
            return ListClusterNodesOutput(
                count=0,
                nodes=[],
                error=ErrorModel(error_code="ListClusterNodesError", error_message=str(e)),
                execution_log=execution_log,
            )

    async def list_cluster_tasks(
        self,
        ctx: Context,
        cluster_id: Annotated[str, Field(description="集群ID，必填", pattern=_CLUSTER_ID_PATTERN)],
        nodepool_id: Annotated[
            Optional[str], Field(description="节点池ID，可选；只返回该节点池下的节点", pattern=_NODEPOOL_ID_PATTERN)
        ] = None,
        instance_id: Annotated[Optional[str], Field(description="实例ID，可选")] = None,
        state: Annotated[
            Optional[ClusterTaskState],
            Field(description=_CLUSTER_TASK_STATE_DESC),
        ] = None,
        task_type: Annotated[Optional[ClusterTaskType], Field(description=_CLUSTER_TASK_TYPE_DESC)] = None,
        page_number: Annotated[int, Field(description="页码")] = 1,
        page_size: Annotated[int, Field(description="每页数量")] = 10,
        start_time: Annotated[
            Optional[str], Field(description="开始时间, 支持 ISO8601格式 或 相对时间如 3m, 1h")
        ] = None,
        end_time: Annotated[Optional[str], Field(description="结束时间, 支持 ISO8601格式")] = None,
    ) -> ListClusterTasksOutput:
        """
        Query cluster task list (DescribeClusterTasks). Supports pagination, state, task_type;
        if instance_id is provided, automatically maps to node_name for filtering;
        includes details by default; filtered by nodepool_id, time, and instance_id.
        Fetch both FAIL and FAILED task states when querying for failed tasks.

        Args:
            ctx: FastMCP context containing lifespan providers
            cluster_id: Unique identifier for the cluster
            end_time: Optional, end time for filtering (ISO8601 format)
            instance_id: Optional, filter by specific instance ID
            nodepool_id: Optional, filter by specific node pool
            page_number: Page number for pagination
            page_size: Number of results per page
            start_time: Optional, start time for filtering (ISO8601 or relative time)
            state: Optional, filter by task state
            task_type: Optional, filter by task type

        Returns:
            ListClusterTasksOutput: Contains task list and execution log

        Raises:
            Exception: Raised when querying cluster tasks fails
        """

        enable_execution_log_ctx.set(self.enable_execution_log)
        now = datetime.now(timezone.utc)
        start_ms = now.timestamp() * 1000
        execution_log = ExecutionLog(
            tool_call_id=f"list_cluster_tasks_{start_ms}",
            start_time=now.isoformat(),
        )
        try:
            region_id = await _get_cluster_region(ctx, cluster_id)
            cs = _get_cs_client(ctx, region_id)
            start_sec, end_sec = parse_time_range(start_time, end_time)
            tasks, page_info = await _fetch_tasks_page(
                cs,
                cluster_id,
                page_number,
                page_size,
                _serialize_sdk_object,
                state=state,
                task_type=task_type,
                target_id=nodepool_id,
            )
            fail_state = (
                ClusterTaskState.FAIL
                if state == ClusterTaskState.FAILED
                else ClusterTaskState.FAILED if state == ClusterTaskState.FAIL else None
            )
            if fail_state:
                fail_tasks, fail_page_info = await _fetch_tasks_page(
                    cs,
                    cluster_id,
                    page_number,
                    page_size,
                    _serialize_sdk_object,
                    state=fail_state,
                    task_type=task_type,
                    target_id=nodepool_id,
                )
                tasks += fail_tasks
                page_info |= fail_page_info

            # 如果提供了 instance_id，通过 list_cluster_nodes 映射为 node_name
            node_name = None
            if instance_id:
                node_name = await _map_instance_id_to_node_name(cs, cluster_id, instance_id, _serialize_sdk_object)

            collected = [
                filter_task(t) for t in tasks if task_matches_filters(t, start_sec, end_sec, instance_id, node_name)
            ]
            lp = page_info or {}

            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)

            # 如果过滤后没有任务，但 total_count > 0 且从API获取到了任务，
            # 说明任务不匹配过滤条件，返回错误提示
            if len(collected) == 0 and len(tasks) > 0:
                execution_log.messages.append("No tasks match the specified filters")
                return ListClusterTasksOutput(
                    count=0,
                    tasks=[],
                    total_count=lp.get("total_count") if lp.get("total_count") else 0,
                    page_number=lp.get("page_number") or page_number,
                    page_size=lp.get("page_size") or page_size,
                    execution_log=execution_log,
                )

            execution_log.messages.append(f"Successfully list {len(collected)} tasks")

            return ListClusterTasksOutput(
                count=len(collected),
                tasks=collected,
                total_count=lp.get("total_count") if lp.get("total_count") else 0,
                page_number=lp.get("page_number") or page_number,
                page_size=lp.get("page_size") or page_size,
                execution_log=execution_log,
            )
        except Exception as e:
            logger.error(f"list_cluster_tasks failed: {e}")
            execution_log.messages.append(f"Failed list cluster tasks: {e}")
            now = datetime.now(timezone.utc)
            end_ms = now.timestamp() * 1000
            execution_log.end_time = now.isoformat()
            execution_log.duration_ms = int(end_ms - start_ms)
            execution_log.error = str(e)
            return ListClusterTasksOutput(
                count=0,
                tasks=[],
                error=ErrorModel(error_code="ListClusterTasksError", error_message=str(e)),
                execution_log=execution_log,
            )
