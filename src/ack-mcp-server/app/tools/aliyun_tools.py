"""
定义所有与阿里云相关的 MCP 工具。
"""
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from app.context import app_context
from app.services.aliyun_service import AliyunService


def register_aliyun_tools(mcp_server: FastMCP, aliyun_svc: AliyunService):
    """注册所有阿里云相关的工具到 MCP 服务器。"""

    @mcp_server.tool("scale_cluster_nodepool")
    async def scale_cluster_nodepool(
        cluster_id: Annotated[str, Field(
            description="阿里云容器服务Kubernetes集群的唯一标识符",
            pattern=r"^c[0-9a-f]+$",
            min_length=10,
            max_length=50
        )],
        nodepool_id: Annotated[str, Field(
            description="节点池的唯一标识符",
            pattern=r"^np[0-9a-f]+$",
            min_length=10,
            max_length=50
        )],
        count: Annotated[int, Field(
            description="需要增加的节点数量",
            ge=1,
            le=500
        )],
    ) -> Dict[str, Any]:
        """
        对指定集群的节点池进行扩容操作。此操作为异步操作。

        Returns:
            一个包含任务ID和状态等信息的字典。

        Raises:
            ToolError: 如果扩容请求失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})

        try:
            return aliyun_svc.scale_nodepool(
                cluster_id=cluster_id,
                nodepool_id=nodepool_id,
                count=count,
                credentials=credentials,
            )
        except Exception as e:
            raise ToolError(f"Failed to scale nodepool: {e}") from e

    @mcp_server.tool("describe_task_info")
    async def describe_task_info(
        task_id: Annotated[str, Field(
            description="任务的唯一标识符，通常由其他操作（如扩容、缩容等）返回",
            min_length=1,
            max_length=100
        )],
    ) -> Dict[str, Any]:
        """
        查询阿里云异步任务的详细信息和执行状态。

        Returns:
            一个包含任务详细信息的字典。

        Raises:
            ToolError: 如果查询任务信息失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})

        try:
            return aliyun_svc.describe_task_info(
                task_id=task_id,
                credentials=credentials
            )
        except Exception as e:
            raise ToolError(f"Failed to describe task info: {e}") from e

    @mcp_server.tool("remove_nodepool_nodes")
    async def remove_nodepool_nodes(
        cluster_id: Annotated[str, Field(
            description="阿里云容器服务Kubernetes集群的唯一标识符",
            pattern=r"^c[0-9a-f]+$",
            min_length=10,
            max_length=50
        )],
        nodepool_id: Annotated[str, Field(
            description="节点池的唯一标识符",
            pattern=r"^np[0-9a-f]+$",
            min_length=10,
            max_length=50
        )],
        instance_ids: Annotated[List[str], Field(
            description="待移除的ECS实例ID列表，每个实例ID格式如 'i-1234567890abcdef'",
            min_length=1,
            max_length=100
        )],
        release_node: Annotated[bool, Field(
            description="是否同时释放ECS实例资源。True表示释放实例，False表示保留实例"
        )] = False,
        drain_node: Annotated[bool, Field(
            description="是否在移除前排空节点上的Pod。True表示优雅移除（推荐），False表示强制移除"
        )] = True,
        concurrency: Annotated[bool, Field(
            description="是否并发执行移除操作。True表示并发执行（更快），False表示串行执行（更安全）"
        )] = False,
    ) -> Dict[str, Any]:
        """
        从指定节点池中移除特定的节点实例。此操作为异步操作。

        Returns:
            一个包含任务ID和状态等信息的字典。

        Raises:
            ToolError: 如果移除节点请求失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")

        credentials = ctx.request.scope.get("credentials", {})

        try:
            return aliyun_svc.remove_nodepool_nodes(
                cluster_id=cluster_id,
                nodepool_id=nodepool_id,
                instance_ids=instance_ids,
                release_node=release_node,
                drain_node=drain_node,
                concurrency=concurrency,
                credentials=credentials,
            )
        except Exception as e:
            raise ToolError(f"Failed to remove nodepool nodes: {e}") from e

    @mcp_server.tool("create_cluster_diagnosis")
    async def create_cluster_diagnosis(
        cluster_id: Annotated[str, Field(
            description="需要创建诊断的集群ID",
            pattern=r"^c[0-9a-f]+$",
        )],
        diagnosis_type: Annotated[Literal["cluster", "node", "pod", "network", "ingress", "memory", "service"], Field(
            description="诊断类型",
        )] = "cluster",
        target: Annotated[Optional[Dict[str, Any]], Field(
            description="诊断目标，其结构取决于 `diagnosis_type`。例如，对于 'node' 类型，应为 {'name': 'node-name'}。",
        )] = None,
    ) -> Dict[str, Any]:
        """
        为指定的集群创建诊断任务。

        支持的诊断类型包括:
        - `cluster`: 整个集群
        - `node`: 特定节点, target=`{'name': 'node-name'}`
        - `pod`: 特定Pod, target=`{'namespace': 'ns', 'name': 'pod-name'}`
        - `network`: 网络链路, target=`{'src': 'ip1', 'dst': 'ip2', 'dport': 'port'}`
        - `ingress`: Ingress, target=`{'url': 'https://example.com'}`
        - `memory`: 节点内存, target=`{'node': 'node-name'}`
        - `service`: Service, target=`{'namespace': 'ns', 'name': 'svc-name'}`

        Returns:
            一个包含诊断ID的字典。

        Raises:
            ToolError: 如果创建诊断失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")
        credentials = ctx.request.scope.get("credentials", {})
        try:
            return aliyun_svc.create_cluster_diagnosis(
                cluster_id=cluster_id,
                diagnosis_type=diagnosis_type,
                target=target,
                credentials=credentials,
            )
        except Exception as e:
            raise ToolError(f"Failed to create cluster diagnosis: {e}") from e

    @mcp_server.tool("get_cluster_diagnosis_result")
    async def get_cluster_diagnosis_result(
        cluster_id: Annotated[str, Field(
            description="诊断所属的集群ID",
            pattern=r"^c[0-9a-f]+$",
        )],
        diagnosis_id: Annotated[str, Field(
            description="诊断任务的唯一标识符",
        )],
    ) -> Dict[str, Any]:
        """
        获取指定集群诊断任务的结果。

        Returns:
            一个包含诊断详细结果的字典。

        Raises:
            ToolError: 如果获取诊断结果失败。
        """
        ctx = app_context.get()
        if not ctx.request:
            raise RuntimeError("Could not get request from context.")
        credentials = ctx.request.scope.get("credentials", {})
        try:
            return aliyun_svc.get_cluster_diagnosis_result(
                cluster_id=cluster_id,
                diagnosis_id=diagnosis_id,
                credentials=credentials,
            )
        except Exception as e:
            raise ToolError(
                f"Failed to get cluster diagnosis result: {e}") from e
