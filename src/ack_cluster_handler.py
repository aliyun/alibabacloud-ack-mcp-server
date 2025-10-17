"""ACK Cluster Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from pydantic import Field
import json
from models import (
    ListClustersOutput,
    ClusterInfo,
    ErrorModel,
    ClusterErrorCodes
)


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


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    cs_client_factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region, config)


def parse_master_url(master_url: str) -> dict:
    """
    Parse the master_url string and extract API server endpoints.

    Args:
        master_url (str): The master URL string in format containing API endpoints

    Returns:
        dict: A dictionary containing the parsed endpoints
    """
    # Default response structure with empty strings instead of None
    endpoints = {"api_server_endpoint": "", "intranet_api_server_endpoint": ""}

    # If master_url is empty or None, return default
    if not master_url:
        return endpoints

    # Try to parse as JSON first
    try:
        url_data = json.loads(master_url)
        # Extract endpoints from the JSON structure
        if isinstance(url_data, dict):
            endpoints["api_server_endpoint"] = url_data.get("api_server_endpoint") or ""
            endpoints["intranet_api_server_endpoint"] = url_data.get(
                "intranet_api_server_endpoint"
            ) or ""
    except json.JSONDecodeError as e:
        # Log the error and return empty dict as requested
        print(f"JSON decode error when parsing master_url: {e}")
        return {"api_server_endpoint": "", "intranet_api_server_endpoint": ""}

    return endpoints


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
        if server is None:
            return
        self.server = server
        # 是否可写变更配置
        self.allow_write = self.settings.get("allow_write", False)
        self.settings = settings or {}

        # Register tools
        self.server.tool(
            name="list_clusters",
            description="获取所有region下所有ACK集群列表，默认返回最多10个集群"
        )(self.list_clusters)

        # TODO for extend 后续添加其他工具，需要按是否可变更资源 allow_write 区分

        logger.info("ACK Addon Management Handler initialized")

    async def list_clusters(
            self,
            ctx: Context,
            page_size: Optional[int] = Field(10, description="查询每个region集群列表的一页大小，默认10"),
            page_num: Optional[int] = Field(1, description="查询每个region集群列表的分页页码，默认1"),
    ) -> ListClustersOutput:
        """获取一个region下所有ACK集群列表

        Args:
            ctx: FastMCP context containing lifespan providers
            page_size: 查询每个region集群列表的一页大小，默认500
            page_num: 查询每个region集群列表的分页页码，默认1

        Returns:
           ListClustersOutput: 包含集群列表和错误信息的输出
        """

        try:
            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, "CENTER")

            # 构建请求
            request = cs20151215_models.DescribeClustersV1Request(
                page_size=min(page_size or 10, 500),
                page_number=page_num or 1,
            )
            runtime = util_models.RuntimeOptions()
            headers = {}

            # 调用 API
            response = await cs_client.describe_clusters_v1with_options_async(request, headers, runtime)

            # 处理响应
            clusters_data = _serialize_sdk_object(
                response.body.clusters) if response.body and response.body.clusters else []
            clusters = []

            for cluster_data in clusters_data:
                try:
                    # 验证必填字段
                    cluster_name = cluster_data.get("name") or cluster_data.get("cluster_name") or ""
                    cluster_id = cluster_data.get("cluster_id") or cluster_data.get("clusterId") or ""
                    state = cluster_data.get("state") or cluster_data.get("cluster_state") or cluster_data.get(
                        "status") or ""
                    cluster_type = cluster_data.get("cluster_type") or cluster_data.get("clusterType") or ""

                    # 如果必填字段为空，跳过这个集群
                    if not cluster_name or not cluster_id or not state or not cluster_type:
                        logger.warning(f"Skipping cluster with missing required fields: {cluster_data}")
                        continue

                    cluster_info = ClusterInfo(
                        cluster_name=cluster_name,
                        cluster_id=cluster_id,
                        state=state,
                        region_id=cluster_data.get("region_id"),
                        cluster_type=cluster_type,
                        current_version=cluster_data.get("current_version"),
                        vpc_id=cluster_data.get("vpc_id"),
                        vswitch_ids=cluster_data.get("vswitch_ids"),
                        resource_group_id=cluster_data.get("resource_group_id"),
                        security_group_id=cluster_data.get("security_group_id"),
                        # network_mode=cluster_data.get("network_mode"),
                        proxy_mode=cluster_data.get("proxy_mode"),
                        tags=cluster_data.get("tags"),
                        container_cidr=cluster_data.get("container_cidr"),
                        service_cidr=cluster_data.get("service_cidr"),
                        api_server_endpoints=parse_master_url(cluster_data.get("master_url", "")),
                    )
                    clusters.append(cluster_info)
                except Exception as e:
                    logger.warning(f"Failed to parse cluster data: {e}")
                    continue

            return ListClustersOutput(
                count=len(clusters),
                clusters=clusters
            )

        except Exception as e:
            logger.error(f"Failed to list clusters: {e}")
            error_message = str(e)
            error_code = ClusterErrorCodes.NO_RAM_POLICY_AUTH

            # 根据错误信息判断具体的错误码
            if "region" in error_message.lower() or "region_id" in error_message.lower():
                error_code = ClusterErrorCodes.MISS_REGION_ID

            return ListClustersOutput(
                count=0,
                error=ErrorModel(
                    error_code=error_code,
                    error_message=error_message
                ),
                clusters=[]
            )
