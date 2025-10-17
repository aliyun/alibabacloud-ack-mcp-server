from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import json
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models
from models import (
    ErrorModel,
    GetDiagnoseResourceResultOutput,
    DiagnosisStatusEnum,
    DiagnosisCodeEnum
)


def _serialize_sdk_object(obj):
    """序列化阿里云SDK对象为可JSON序列化的字典."""
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (list, tuple)):
        return [_serialize_sdk_object(item) for item in obj]

    if isinstance(obj, dict):
        return {key: _serialize_sdk_object(value) for key, value in obj.items()}

    try:
        if hasattr(obj, 'to_map'):
            return obj.to_map()

        if hasattr(obj, '__dict__'):
            return _serialize_sdk_object(obj.__dict__)

        return str(obj)
    except Exception:
        return str(obj)


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return factory(region, config)


class DiagnoseHandler:
    """Handler for ACK diagnose operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {}
        if server is None:
            return
        self.server = server
        self.allow_write = self.settings.get("allow_write", True)
        self.server.tool(
            name="diagnose_resource",
            description="""对ACK集群的Kubernetes资源进行诊断，当遇到问题难以定位时，使用该工具进行深度诊断。支持诊断的资源包括：
1. **node**：K8s 节点
2. **ingress**：Ingress
3. **memory**：节点内存
4. **pod**：Pod
5. **service**：Service
6. **network**：网络连通性
                        """
        )(self.diagnose_resource)

        # self.server.tool(
        #     name="get_diagnose_resource_result",
        #     description="获取ACK集群资源诊断任务的结果"
        # )(self.get_diagnose_resource_result)
        logger.info("ACK Diagnose Handler initialized")

    async def diagnose_resource(
            self,
            ctx: Context,
            cluster_id: str = Field(..., description="需要诊断的ACK集群clusterId"),
            resource_type: str = Field(...,
                                       description="诊断的目标资源类型，枚举值：node|ingress|memory|pod|service|network"),
            resource_target: str = Field(..., description="""用于指定诊断对象的参数，参数必须为合法 JSON 字符串（键和值均用双引号），不得输出多余文字。不同类型示例：
                node: {"name": "cn-shanghai.10.10.10.107"}，其中name为k8s节点的名称
                pod: {"namespace": "kube-system", "name": "csi-plugin-2cg9f"}， 其中namespace为pod所在的命名空间，name为pod的名称
                network: {"src": "10.10.10.108", "dst": "10.11.247.16", "dport": "80", "protocol":"tcp"}， 其中src为源地址，dst为目标地址，dport为目标端口，protocol为协议
                ingress: {"url": "https://example.com"}，其中url为ingress的URL地址
                memory: {"node":"cn-hangzhou.172.16.9.240"}，其中node为k8s节点的名称
                service: {"namespace": "kube-system", "name": "nginx-ingress-lb"}，其中namespace为service所在的命名空间，name为service的名称
            """),
    ) -> GetDiagnoseResourceResultOutput | Dict[str, Any]:
        """发起ACK集群资源诊断任务"""
        # if not self.allow_write:
        #     return {"error": ErrorModel(error_code="WriteDisabled",
        #                                 error_message="Write operations are disabled").model_dump()}

        try:
            # 解析 resource_target JSON
            try:
                target_dict = json.loads(resource_target)
            except json.JSONDecodeError as e:
                return {"error": ErrorModel(error_code="InvalidTarget",
                                            error_message=f"Invalid JSON in resource_target: {e}").model_dump()}

            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, "CENTER")

            # 创建诊断请求
            request = cs20151215_models.CreateClusterDiagnosisRequest(
                type=resource_type,
                target=target_dict
            )
            runtime = util_models.RuntimeOptions()
            headers = {}

            response = await cs_client.create_cluster_diagnosis_with_options_async(
                cluster_id, request, headers, runtime
            )

            # 提取诊断任务ID
            diagnose_task_id = getattr(response.body, 'diagnosis_id', None) if response.body else None
            if not diagnose_task_id:
                return {"error": ErrorModel(error_code="NoTaskId",
                                            error_message="Failed to get diagnosis task ID from response").model_dump()}

            # 使用循环等待诊断完成
            result = await self.wait_for_diagnosis_completion(
                ctx, cluster_id, "CENTER", diagnose_task_id
            )
            return result

        except Exception as e:
            logger.error(f"Failed to create cluster diagnosis: {e}")
            error_code = "UnknownError"
            if "RESOURCE_NOT_FOUND" in str(e):
                error_code = "RESOURCE_NOT_FOUND"
            elif "CLUSTER_NOT_FOUND" in str(e):
                error_code = "CLUSTER_NOT_FOUND"
            elif "NO_RAM_POLICY_AUTH" in str(e):
                error_code = "NO_RAM_POLICY_AUTH"

            return {"error": ErrorModel(error_code=error_code, error_message=str(e)).model_dump()}

    async def get_diagnose_resource_result(
            self,
            ctx: Context,
            cluster_id: str = Field(..., description="需要查询的prometheus所在的集群clusterId"),
            region_id: str = Field(..., description="集群所在的regionId"),
            diagnose_task_id: str = Field(..., description="生成的异步诊断任务id"),
    ) -> GetDiagnoseResourceResultOutput | Dict[str, Any]:
        """获取集群资源诊断任务的结果"""
        try:
            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, region_id)

            # 获取诊断结果请求（新版SDK使用 GetClusterDiagnosisResultRequest）
            request = cs20151215_models.GetClusterDiagnosisResultRequest()
            runtime = util_models.RuntimeOptions()
            headers = {}

            response = await cs_client.get_cluster_diagnosis_result_with_options_async(
                cluster_id, diagnose_task_id, request, headers, runtime
            )

            if not response.body:
                return {"error": ErrorModel(error_code="NoResponse",
                                            error_message="No response body from diagnosis result query").model_dump()}

            # 提取结果信息
            result = getattr(response.body, 'result', None)
            status = getattr(response.body, 'status', None)
            code = getattr(response.body, 'code', None)
            finished_time = getattr(response.body, 'finished', None)
            resource_type = getattr(response.body, 'type', None)
            resource_target = getattr(response.body, 'target', None)

            return GetDiagnoseResourceResultOutput(
                result=result,
                status=DiagnosisStatusEnum(status).name if status else None,
                code=DiagnosisCodeEnum(code).name if code else None,
                finished_time=finished_time,
                resource_type=resource_type,
                resource_target=json.dumps(resource_target) if resource_target else None,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to get diagnosis result: {e}")
            error_code = "UnknownError"
            if "DIAGNOSE_TASK_FAILED" in str(e):
                error_code = "DIAGNOSE_TASK_FAILED"
            elif "CLUSTER_NOT_FOUND" in str(e):
                error_code = "CLUSTER_NOT_FOUND"
            elif "NO_RAM_POLICY_AUTH" in str(e):
                error_code = "NO_RAM_POLICY_AUTH"

            return {"error": ErrorModel(error_code=error_code, error_message=str(e)).model_dump()}

    async def wait_for_diagnosis_completion(
            self,
            ctx: Context,
            cluster_id: str,
            region_id: str,
            diagnose_task_id: str,
            max_wait_time: int = 300,  # 最大等待时间（秒）
            poll_interval: int = 10    # 轮询间隔（秒）
    ) -> GetDiagnoseResourceResultOutput | Dict[str, Any]:
        """循环获取诊断结果，直到诊断结束
        
        Args:
            ctx: FastMCP context
            cluster_id: 集群ID
            region_id: 区域ID
            diagnose_task_id: 诊断任务ID
            max_wait_time: 最大等待时间（秒），默认5分钟
            poll_interval: 轮询间隔（秒），默认10秒
            
        Returns:
            诊断结果，当状态为COMPLETED或FAILED时返回最终结果
        """
        import asyncio
        from datetime import datetime, timedelta
        
        start_time = datetime.now()
        max_end_time = start_time + timedelta(seconds=max_wait_time)
        
        logger.info(f"开始等待诊断任务 {diagnose_task_id} 完成，最大等待时间: {max_wait_time}秒")
        
        while datetime.now() < max_end_time:
            try:
                # 获取当前诊断状态
                result = await self.get_diagnose_resource_result(
                    ctx, cluster_id, region_id, diagnose_task_id
                )
                
                # 检查是否有错误
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"获取诊断结果时出错: {result['error']}")
                    return result
                
                # 检查状态
                status = result.status if hasattr(result, 'status') else None
                code = result.code if hasattr(result, 'code') else None
                
                logger.info(f"诊断任务 {diagnose_task_id} 当前状态: {status}, 结果码: {code}")
                
                # 检查是否完成
                if status == "COMPLETED":
                    logger.info(f"诊断任务 {diagnose_task_id} 已完成")
                    return result
                elif status == "FAILED" or code == "FAILED":
                    logger.warning(f"诊断任务 {diagnose_task_id} 失败")
                    return result
                elif status in ["CREATED", "RUNNING"]:
                    # 继续等待
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    remaining_time = max_wait_time - elapsed_time
                    logger.info(f"诊断任务 {diagnose_task_id} 仍在进行中，已等待 {elapsed_time:.1f}秒，剩余时间 {remaining_time:.1f}秒")
                    
                    # 等待指定间隔后继续轮询
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    # 未知状态，继续等待
                    logger.warning(f"诊断任务 {diagnose_task_id} 状态未知: {status}，继续等待")
                    await asyncio.sleep(poll_interval)
                    continue
                    
            except Exception as e:
                logger.error(f"轮询诊断结果时出错: {e}")
                # 如果是网络错误等临时问题，继续重试
                await asyncio.sleep(poll_interval)
                continue
        
        # 超时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        error_message = f"诊断任务 {diagnose_task_id} 在 {elapsed_time:.1f}秒内未完成，已超时"
        logger.warning(error_message)
        
        return {
            "error": ErrorModel(
                error_code="DIAGNOSE_TIMEOUT",
                error_message=error_message
            ).model_dump()
        }