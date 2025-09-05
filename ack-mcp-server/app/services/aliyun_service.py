"""
封装与阿里云容器服务 API 的所有交互。
"""
from typing import Any, Dict, List, Optional, Type

# 导入阿里云 SDK
from alibabacloud_cs20151215 import models as cs_models
from alibabacloud_cs20151215.client import Client as CsClient
from alibabacloud_tea_util import models as util_models

from app.config import get_logger
from app.services.base import BaseAliyunService

logger = get_logger()


class AliyunService(BaseAliyunService):
    """
    一个封装了阿里云容器服务（ACK）客户端操作的服务类。
    继承自 BaseAliyunService，使用默认的 CS endpoint 格式和认证逻辑。
    """

    def _get_client_class(self) -> Type[CsClient]:
        """
        返回容器服务的客户端类。

        Returns:
            CsClient: 阿里云容器服务客户端类
        """
        return CsClient

    def scale_nodepool(
        self,
        cluster_id: str,
        nodepool_id: str,
        count: int,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        扩容指定的节点池。

        Args:
            cluster_id: 集群ID
            nodepool_id: 节点池ID
            count: 目标节点数量
            credentials: 认证凭证
        """
        logger.info(
            f"Scaling nodepool '{nodepool_id}' in cluster '{cluster_id}' to {count} nodes."
        )

        # 创建客户端
        cs_client = self._create_client(credentials)

        request = cs_models.ScaleClusterNodePoolRequest(count=count)
        runtime = util_models.RuntimeOptions()
        try:
            response = cs_client.scale_cluster_node_pool_with_options(
                cluster_id, nodepool_id, request, {}, runtime
            )
            logger.info(
                f"Scale request sent successfully. Task ID: {response.body.task_id}")
            return response.body.to_map()
        except Exception as e:
            logger.error(f"Failed to scale nodepool: {e}", exc_info=True)
            raise

    def describe_task_info(
        self,
        task_id: str,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        查询指定任务的详细信息。

        Args:
            task_id: 任务ID
            credentials: 认证凭证
        """
        logger.info(f"Describing task info for task ID: {task_id}")

        # 创建客户端
        cs_client = self._create_client(credentials)

        runtime = util_models.RuntimeOptions()
        try:
            response = cs_client.describe_task_info_with_options(
                task_id, {}, runtime)
            return response.body.to_map()
        except Exception as e:
            logger.error(f"Failed to describe task info: {e}", exc_info=True)
            raise

    def remove_nodepool_nodes(
        self,
        cluster_id: str,
        nodepool_id: str,
        instance_ids: List[str],
        release_node: bool,
        drain_node: bool = True,
        concurrency: bool = False,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        从指定的节点池中移除一个或多个节点。

        Args:
            cluster_id: 集群ID
            nodepool_id: 节点池ID
            nodes: 要移除的节点列表
            release_node: 是否释放节点
            drain_node: 是否在移除前排空节点上的Pod
            concurrency: 是否并发执行移除操作
            credentials: 认证凭证
        """
        logger.info(
            f"Removing nodes {instance_ids} from nodepool '{nodepool_id}' in cluster '{cluster_id}' "
            f"(release_node={release_node}, drain_node={drain_node}, concurrency={concurrency})."
        )

        # 创建客户端
        cs_client = self._create_client(credentials)

        # 创建移除节点请求，传递所有相关参数
        request = cs_models.RemoveNodePoolNodesRequest(
            instance_ids=instance_ids,
            release_node=release_node,
            drain_node=drain_node,
            concurrency=concurrency
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = cs_client.remove_node_pool_nodes_with_options(
                cluster_id, nodepool_id, request, {}, runtime
            )
            logger.info(
                f"Remove nodes request sent successfully. Task ID: {response.body.task_id}"
            )
            return response.body.to_map()
        except Exception as e:
            logger.error(f"Failed to remove nodes: {e}", exc_info=True)
            raise

    def create_cluster_diagnosis(
        self,
        cluster_id: str,
        diagnosis_type: str,
        target: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        为指定的集群创建诊断。

        Args:
            cluster_id: 集群ID
            diagnosis_type: 诊断类型
            target: 诊断目标，具体结构取决于诊断类型
            credentials: 认证凭证
        """
        logger.info(
            f"Creating diagnosis of type '{diagnosis_type}' for cluster '{cluster_id}' with target: {target}.")

        # 创建客户端
        cs_client = self._create_client(credentials)

        request_params: Dict[str, Any] = {'type': diagnosis_type}
        if target:
            request_params['target'] = target
        request = cs_models.CreateClusterDiagnosisRequest(**request_params)
        runtime = util_models.RuntimeOptions()
        try:
            response = cs_client.create_cluster_diagnosis_with_options(
                cluster_id, request, {}, runtime
            )
            logger.info(
                f"Create diagnosis request sent successfully. Diagnosis ID: {response.body.diagnosis_id}"
            )
            return response.body.to_map()
        except Exception as e:
            logger.error(
                f"Failed to create cluster diagnosis: {e}", exc_info=True)
            raise

    def get_cluster_diagnosis_result(
        self,
        cluster_id: str,
        diagnosis_id: str,
        credentials: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取指定集群诊断的结果。

        Args:
            cluster_id: 集群ID
            diagnosis_id: 诊断ID
            credentials: 认证凭证
        """
        logger.info(
            f"Getting diagnosis result for cluster '{cluster_id}' and diagnosis '{diagnosis_id}'.")

        # 创建客户端
        cs_client = self._create_client(credentials)

        request = cs_models.GetClusterDiagnosisResultRequest()
        runtime = util_models.RuntimeOptions()
        try:
            response = cs_client.get_cluster_diagnosis_result_with_options(
                cluster_id, diagnosis_id, request, {}, runtime
            )
            return response.body.to_map()
        except Exception as e:
            logger.error(
                f"Failed to get cluster diagnosis result: {e}", exc_info=True)
            raise
