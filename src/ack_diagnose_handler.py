from typing import Dict, Any, Optional, List
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import json
from alibabacloud_cs20151215 import models as cs20151215_models
from alibabacloud_tea_util import models as util_models

try:
    from .models import (
        ErrorModel,
        DiagnoseResourceInput,
        DiagnoseResourceOutput,
        GetDiagnoseResourceResultInput,
        GetDiagnoseResourceResultOutput,
        DiagnosisStatusEnum,
        DiagnosisCodeEnum
    )
except ImportError:
    from models import (
        ErrorModel,
        DiagnoseResourceInput,
        DiagnoseResourceOutput,
        GetDiagnoseResourceResultInput,
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
    providers = getattr(ctx.request_context, "lifespan_context", {}).get("providers", {})
    factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return factory(region)


class DiagnoseHandler:
    """Handler for ACK diagnose operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)

        self.server.tool(
            name="diagnose_resource",
            description="对ACK集群的Kubernetes资源进行诊断，包括node/ingress/cluster/memory/pod/service/network等。发起一个ACK集群的资源的异步诊断任务，获取diagnose_task_id，然后需要通过轮训调用tool get_diagnose_resource_result 获取诊断报告结果，完成诊断大概需要3分钟左右。"
        )(self.diagnose_resource)

        self.server.tool(
            name="get_diagnose_resource_result",
            description="获取ACK集群资源诊断任务的结果"
        )(self.get_diagnose_resource_result)
        logger.info("ACK Diagnose Handler initialized")

    async def diagnose_resource(
            self,
            ctx: Context,
            cluster_id: str = Field(..., description="需要诊断的ACK集群clusterId"),
            region_id: str = Field(..., description="集群所在的regionId"),
            resource_type: str = Field(...,
                                       description="诊断的目标资源类型：node/ingress/cluster/memory/pod/service/network"),
            resource_target: str = Field(..., description="""用于指定诊断对象的参数，JSON字符串格式, 
            用于指定诊断对象的参数。不同诊断类型的参数示例：
                node: {"name": "cn-shanghai.10.10.10.107"}
                pod: {"namespace": "kube-system", "name": "csi-plugin-2cg9f"}
                network: {"src": "10.10.10.108", "dst": "10.11.247.16", "dport": "80"}
                ingress: {"url": "https://example.com"}
                memory: {"node":"cn-hangzhou.172.16.9.240"}
                service: {"namespace": "kube-system", "name": "nginx-ingress-lb"}
            """),
    ) -> DiagnoseResourceOutput | Dict[str, Any]:
        """发起ACK集群资源诊断任务"""
        if not self.allow_write:
            return {"error": ErrorModel(error_code="WriteDisabled",
                                        error_message="Write operations are disabled").model_dump()}

        try:
            # 解析 resource_target JSON
            try:
                target_dict = json.loads(resource_target)
            except json.JSONDecodeError as e:
                return {"error": ErrorModel(error_code="InvalidTarget",
                                            error_message=f"Invalid JSON in resource_target: {e}").model_dump()}

            # 获取 CS 客户端
            cs_client = _get_cs_client(ctx, region_id)

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

            return DiagnoseResourceOutput(
                diagnose_task_id=diagnose_task_id,
                error=None
            )

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
            finished_time = getattr(response.body, 'finished_time', None)
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
            logger.error(f"Failed to get cluster diagnosis result: {e}")
            error_code = "UnknownError"
            if "DIAGNOSE_TASK_FAILED" in str(e):
                error_code = "DIAGNOSE_TASK_FAILED"
            elif "CLUSTER_NOT_FOUND" in str(e):
                error_code = "CLUSTER_NOT_FOUND"
            elif "NO_RAM_POLICY_AUTH" in str(e):
                error_code = "NO_RAM_POLICY_AUTH"

            return {"error": ErrorModel(error_code=error_code, error_message=str(e)).model_dump()}
