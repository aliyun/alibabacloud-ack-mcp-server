

"""ACK Cluster Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
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


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    providers = getattr(ctx.request_context, "lifespan_context", {}).get("providers", {})
    factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return factory(region)


# 默认区域列表
DEFAULT_REGIONS = [
    "cn-hangzhou", "cn-shanghai", "cn-beijing", "cn-shenzhen", "cn-zhangjiakou", "cn-huhehaote",
    "cn-chengdu", "cn-hongkong", "ap-southeast-1", "ap-southeast-3", "ap-southeast-5",
    "ap-south-1", "ap-northeast-1", "eu-central-1", "eu-west-1", "us-west-1", "us-east-1",
]


class ACKClusterHandler:
    """Handler for ACK addon management operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK addon management handler.

        Args:
            server: FastMCP server instance
            allow_write: Whether to allow write operations
            settings: Configuration settings
        """
        self.server = server
        self.allow_write = settings.get("allow_write", True)
        self.settings = settings or {}

        # Register tools
        self._register_tools()

        logger.info("ACK Addon Management Handler initialized")

    def _register_tools(self):
        """Register addon management related tools."""

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
            # Get providers and config from lifespan context
            try:
                lifespan_context = ctx.request_context.lifespan_context
                lifespan_config = lifespan_context.get("config", {})
            except Exception as e:
                logger.error(f"Failed to get lifespan context: {e}")
                return {"error": "Failed to access lifespan context"}

            target_regions = regions or DEFAULT_REGIONS
            brief_list: List[Dict[str, Any]] = []
            errors: List[Dict[str, Any]] = []

            for region in target_regions:
                try:
                    cs_client = _get_cs_client(ctx, region)
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