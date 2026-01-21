"""ACK Cluster Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Annotated, Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
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
    parse_task_time,
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


# ACK cluster_id 规范：以 c 开头，后跟小写字母、数字，长度 33
_CLUSTER_ID_RE = re.compile(r"^c[a-z0-9]{32}$")

# ACK nodepool_id 规范：以 np 开头，后跟小写字母、数字，长度通常为 32-40
_NODEPOOL_ID_RE = re.compile(r"^np[a-z0-9]{32}$")

# list_cluster_tasks 的 task_type 可选值说明
_TASK_TYPE_DESC = (
    "任务类型：nodepool_create, nodepool_delete, nodepool_update, nodepool_scaleout, "
    "nodepool_scalein, nodepool_node_attach, nodepool_node_remove, nodepool_upgrade, "
    "nodepool_cve_fix, nodepool_node_os_config_rollout, nodepool_node_kubelet_config_rollout, "
    "nodepool_node_containerd_config_rollout"
)


def validate_cluster_id(cluster_id: str) -> None:
    """校验 cluster_id 是否符合 ACK 规范，不符合则抛出 ValueError。"""
    if not cluster_id or not isinstance(cluster_id, str):
        raise ValueError("cluster_id is required and must be a non-empty string")
    c = cluster_id.strip()
    if not _CLUSTER_ID_RE.match(c):
        raise ValueError(
            "cluster_id must start with 'c' and contain only lowercase letters, digits"
            "(e.g. c23421cfa74454bc8b37163fd19af****)"
        )


def validate_nodepool_id(nodepool_id: str) -> None:
    """校验 nodepool_id 是否符合 ACK 规范，不符合则抛出 ValueError。"""
    if not nodepool_id or not isinstance(nodepool_id, str):
        raise ValueError("nodepool_id must be a non-empty string")
    np = nodepool_id.strip()
    if not _NODEPOOL_ID_RE.match(np):
        raise ValueError(
            "nodepool_id must start with 'np' and contain only lowercase letters and digits "
            "(e.g. np25b6714936a241ddb34c5d714bxxxxxx)"
        )


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
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """调用 DescribeClusterNodes 一页，返回 (nodes, page_info_dict)。支持 instance_ids 过滤。"""
    runtime, headers = _cs_runtime_headers()
    req_kw: Dict[str, Any] = {
        "page_number": page_number,
        "page_size": min(page_size, 100),
        "nodepool_id": nodepool_id,
    }
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
    page_info = extract_page_info(response.body, serialize)
    return nodes, page_info


async def _fetch_tasks_page(
    client: Any,
    cluster_id: str,
    page_number: int,
    page_size: int,
    serialize: Any,
    *,
    state: Optional[str] = None,
    task_type: Optional[str] = None,
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
        query["state"] = state
    if task_type:
        query["type"] = task_type
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
    """Handler for ACK addon management operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK addon management handler.

        Args:
            server: FastMCP server instance
            allow_write: Whether to allow write operations
            settings: Configuration settings
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
        """获取一个region下所有ACK集群列表

        Args:
            ctx: FastMCP context containing lifespan providers
            page_size: 查询每个region集群列表的一页大小，默认500
            page_num: 查询每个region集群列表的分页页码，默认1

        Returns:
           ListClustersOutput: 包含集群列表和错误信息的输出
        """
        # Set per-request context from handler setting
        enable_execution_log_ctx.set(self.enable_execution_log)

        # Initialize execution log
        execution_log = ExecutionLog(
            tool_call_id=f"list_clusters_{int(time.time() * 1000)}", start_time=datetime.utcnow().isoformat() + "Z"
        )
        start_ms = int(time.time() * 1000)

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
                    execution_log.warnings.append(f"Failed to parse cluster data: {cluster_data}, error: {e}")
                    skipped_count += 1
                    continue
                clusters.append(cluster_info)

            if skipped_count > 0:
                execution_log.warnings.append(f"Skipped {skipped_count} clusters with missing required fields")

            execution_log.messages.append(f"Successfully list {len(clusters)} clusters")
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms

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
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms
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
        cluster_id: str = Field(..., description="集群ID，必填"),
        nodepool_id: Optional[str] = Field(
            None, description="节点池ID，可选；若填写则使用 DescribeClusterNodePoolDetail 查询该节点池详情"
        ),
        page_size: Optional[int] = Field(
            10, description="查询集群内节点池分页参数，默认10；仅在不指定 nodepool_id 时生效"
        ),
        page_num: Optional[int] = Field(
            1, description="查询集群内节点池分页参数，默认1；仅在不指定 nodepool_id 时生效"
        ),
    ) -> ListClusterNodepoolsOutput:
        """查询集群节点池：指定 nodepool_id 时用 DescribeClusterNodePoolDetail；否则用 DescribeClusterNodePools 并分页。"""
        try:
            validate_cluster_id(cluster_id)
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
            pn = max(1, int(page_num or 1))
            start = (pn - 1) * ps
            page = all_raw[start : start + ps]
            items = [filter_nodepool(x) for x in page]
            return ListClusterNodepoolsOutput(
                count=len(items), total_count=total_count, nodepools=items, page_number=pn, page_size=ps
            )
        except Exception as e:
            logger.error(f"Failed to list clusters: {e}")
            return ListClustersOutput(
                count=0,
                clusters=[],
                error=ErrorModel(error_code="ListClustersError", error_message=str(e)),
            )

    async def list_cluster_nodes(
        self,
        ctx: Context,
        cluster_id: str = Field(..., description="集群ID，必填"),
        nodepool_id: Optional[str] = Field(None, description="节点池ID，可选；只返回该节点池下的节点"),
        instance_ids: Optional[List[str]] = Field(
            None,
            description="实例ID列表，只返回这些实例的节点；可先查得 node_name 再与 list_cluster_tasks 的 node_name、instance_id 并集过滤配合使用",
        ),
        page_number: Optional[int] = Field(1, description="页码，默认1"),
        page_size: Optional[int] = Field(20, description="每页数量，默认20"),
    ) -> ListClusterNodesOutput:
        """查询集群节点列表（DescribeClusterNodes），支持 instance_ids；默认分页。"""
        try:
            validate_cluster_id(cluster_id)
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
            )
            items = [filter_node(n) for n in nodes]
            pi = page_info or {}
            total = pi.get("total_count") or pi.get("total") or len(items)
            return ListClusterNodesOutput(
                count=len(items),
                total_count=total if isinstance(total, int) else None,
                nodes=items,
                page_number=page_number,
                page_size=page_size,
            )
        except Exception as e:
            logger.error(f"list_cluster_nodes failed: {e}")
            return ListClusterNodesOutput(
                count=0,
                nodes=[],
                error=ErrorModel(error_code="ListClusterNodesError", error_message=str(e)),
            )

    async def list_cluster_tasks(
        self,
        ctx: Context,
        cluster_id: str = Field(..., description="集群ID，必填"),
        nodepool_id: Optional[str] = Field(None, description="节点池ID，可选；只返回与该节点池相关的任务"),
        instance_id: Optional[str] = Field(None, description="实例ID，可选；"),
        state: Optional[str] = Field(
            None, description="任务状态筛选，支持: running、success、fail、initial、paused、resuming、canceled"
        ),
        task_type: Optional[str] = Field(None, description=_TASK_TYPE_DESC),
        page_number: Optional[int] = Field(1, description="页码，默认1"),
        page_size: Optional[int] = Field(10, description="每页数量，默认10"),
        start_time: Optional[str] = Field(
            None, description="开始时间，可选；指定时才生效；支持 ISO8601 或相对时间如 3m、1h"
        ),
        end_time: Optional[str] = Field(None, description="结束时间，可选；指定时才生效"),
    ) -> ListClusterTasksOutput:
        """查询集群任务列表（DescribeClusterTasks）。支持分页、state、task_type；如果提供 instance_id，会自动映射为 node_name 进行过滤；默认带 detail；按 nodepool_id、时间及 instance_id 过滤。"""

        try:
            validate_cluster_id(cluster_id)
            if nodepool_id:
                validate_nodepool_id(nodepool_id)

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

            # 如果提供了 instance_id，通过 list_cluster_nodes 映射为 node_name
            node_name = None
            if instance_id:
                node_name = await _map_instance_id_to_node_name(cs, cluster_id, instance_id, _serialize_sdk_object)

            collected = [
                filter_task(t) for t in tasks if task_matches_filters(t, start_sec, end_sec, instance_id, node_name)
            ]
            lp = page_info or {}

            # 如果过滤后没有任务，但 total_count > 0 且从API获取到了任务，
            # 说明任务不匹配过滤条件，返回错误提示
            if len(collected) == 0 and len(tasks) > 0:
                return ListClusterTasksOutput(
                    count=0,
                    tasks=[],
                    page_number=lp.get("page_number") or page_number,
                    page_size=lp.get("page_size") or page_size,
                )

            return ListClusterTasksOutput(
                count=len(collected),
                tasks=collected,
                page_number=lp.get("page_number") or page_number,
                page_size=lp.get("page_size") or page_size,
            )
        except Exception as e:
            logger.error(f"list_cluster_tasks failed: {e}")
            return ListClusterTasksOutput(
                count=0,
                tasks=[],
                error=ErrorModel(error_code="ListClusterTasksError", error_message=str(e)),
            )
