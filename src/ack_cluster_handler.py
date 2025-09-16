

"""ACK Cluster Handler - Alibaba Cloud Container Service Cluster Management."""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from pydantic import Field

try:
    from .models import (
        ListClustersInput, 
        ListClustersOutput, 
        ClusterInfo, 
        ErrorModel, 
        ClusterErrorCodes
    )
except ImportError:
    from models import (
        ListClustersInput, 
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
            name="list_clusters",
            description="获取一个region下所有ACK集群列表"
        )
        async def list_clusters(
                ctx: Context,
                region_id: str = Field(..., description="区域ID，例如 cn-hangzhou"),
                page_size: Optional[int] = Field(500, description="查询每个region集群列表的一页大小，默认500"),
                page_num: Optional[int] = Field(1, description="查询每个region集群列表的分页页码，默认1"),
        ) -> ListClustersOutput:
            """获取一个region下所有ACK集群列表

            Args:
                ctx: FastMCP context containing lifespan providers
                region_id: 区域ID，例如 cn-hangzhou
                page_size: 查询每个region集群列表的一页大小，默认500
                page_num: 查询每个region集群列表的分页页码，默认1

            Returns:
                ListClustersOutput: 包含集群列表和错误信息的输出
            """
            # 验证必填参数
            if not region_id:
                return ListClustersOutput(
                    count=0,
                    error=ErrorModel(
                        error_code=ClusterErrorCodes.MISS_REGION_ID,
                        error_message="缺少region_id参数, 参考 https://help.aliyun.com/zh/ack/product-overview/supported-regions"
                    ),
                    clusters=[]
                )

            try:
                # 获取 CS 客户端
                cs_client = _get_cs_client(ctx, region_id)
                
                # 构建请求
                request = cs20151215_models.DescribeClustersV1Request(
                    page_size=min(page_size or 500, 500),
                    page_number=page_num or 1,
                    region_id=region_id,
                )
                runtime = util_models.RuntimeOptions()
                headers = {}
                
                # 调用 API
                response = await cs_client.describe_clusters_v1with_options_async(request, headers, runtime)
                
                # 处理响应
                clusters_data = _serialize_sdk_object(response.body.clusters) if response.body and response.body.clusters else []
                clusters = []
                
                for cluster_data in clusters_data:
                    try:
                        # 验证必填字段
                        cluster_name = cluster_data.get("name") or cluster_data.get("cluster_name") or ""
                        cluster_id = cluster_data.get("cluster_id") or cluster_data.get("clusterId") or ""
                        state = cluster_data.get("state") or cluster_data.get("cluster_state") or cluster_data.get("status") or ""
                        cluster_type = cluster_data.get("cluster_type") or cluster_data.get("clusterType") or ""
                        
                        # 如果必填字段为空，跳过这个集群
                        if not cluster_name or not cluster_id or not state or not cluster_type:
                            logger.warning(f"Skipping cluster with missing required fields: {cluster_data}")
                            continue
                        
                        cluster_info = ClusterInfo(
                            cluster_name=cluster_name,
                            cluster_id=cluster_id,
                            state=state,
                            region_id=cluster_data.get("region_id") or region_id,
                            cluster_type=cluster_type,
                            current_version=cluster_data.get("current_version") or cluster_data.get("currentVersion"),
                            vpc_id=cluster_data.get("vpc_id") or cluster_data.get("vpcId"),
                            vswitch_ids=cluster_data.get("vswitch_ids") or cluster_data.get("vswitchIds") or [],
                            resource_group_id=cluster_data.get("resource_group_id") or cluster_data.get("resourceGroupId"),
                            security_group_id=cluster_data.get("security_group_id") or cluster_data.get("securityGroupId"),
                            network_mode=cluster_data.get("network_mode") or cluster_data.get("networkMode"),
                            proxy_mode=cluster_data.get("proxy_mode") or cluster_data.get("proxyMode")
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
                logger.error(f"Failed to list clusters for region {region_id}: {e}")
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