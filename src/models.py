from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorModel(BaseModel):
    error_code: str = Field(...)
    error_message: str = Field(...)


class QueryPrometheusInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    promql: str = Field(..., description="PromQL 表达式")
    start_time: Optional[str] = Field(None, description="RFC3339 或 unix；与 end_time 同时提供为 range 查询")
    end_time: Optional[str] = Field(None, description="RFC3339 或 unix；与 start_time 同时提供为 range 查询")
    step: Optional[str] = Field(None, description="range 查询步长，例如 30s")


class QueryPrometheusSeriesPoint(BaseModel):
    metric: Dict[str, Any] = Field(default_factory=dict)
    values: List[Any] = Field(default_factory=list)


class QueryPrometheusOutput(BaseModel):
    resultType: str
    result: List[QueryPrometheusSeriesPoint]


class QueryPrometheusMetricGuidanceInput(BaseModel):
    resource_label: str = Field(..., description="node/pod/container 等")
    metric_category: str = Field(..., description="cpu/memory/network/disk")


class MetricDefinition(BaseModel):
    description: Optional[str]
    category: Optional[str]
    labels: List[str] = Field(default_factory=list)
    name: Optional[str]
    type: Optional[str]


class QueryPrometheusMetricGuidanceOutput(BaseModel):
    metrics: List[MetricDefinition] = Field(default_factory=list)
    error: Optional[ErrorModel] = None


# ACK Diagnose Models
class DiagnoseResourceInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    region_id: str = Field(..., description="集群所在的 regionId")
    resource_type: str = Field(..., description="诊断的目标资源类型：node/ingress/cluster/memory/pod/service/network")
    resource_target: str = Field(..., description="用于指定诊断对象的参数，JSON 字符串格式")


class DiagnoseResourceOutput(BaseModel):
    diagnose_task_id: Optional[str] = None
    error: Optional[ErrorModel] = None


class GetDiagnoseResourceResultInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    region_id: str = Field(..., description="集群所在的 regionId")
    diagnose_task_id: str = Field(..., description="生成的异步诊断任务id")


class GetDiagnoseResourceResultOutput(BaseModel):
    result: Optional[str] = None
    status: Optional[str] = None
    finished_time: Optional[str] = None
    resource_type: Optional[str] = None
    resource_target: Optional[str] = None
    error: Optional[ErrorModel] = None


# ACK Inspect Models
class QueryInspectReportInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    region_id: str = Field(..., description="集群所在的 regionId")
    is_result_exception: bool = Field(True, description="是否只返回异常的结果，默认为true")


class InspectSummary(BaseModel):
    errorCount: int = Field(0, description="error级别的检查结果个数")
    warnCount: int = Field(0, description="warn级别的检查结果个数")
    normalCount: int = Field(0, description="normal级别的检查结果个数")
    adviceCount: int = Field(0, description="advice级别的检查结果个数")
    unknownCount: int = Field(0, description="结果为unknown的检查结果个数")


class InspectTarget(BaseModel):
    target_name: str = Field(..., description="巡检项的目标资源对象名")


class CheckItemResult(BaseModel):
    category: str = Field(..., description="巡检项归属领域：security/performance/stability/limitation/cost")
    name: str = Field(..., description="巡检项的名称")
    targetType: str = Field(..., description="巡检项的目标资源对象")
    targets: List[str] = Field(default_factory=list, description="巡检项的目标资源对象名列表")
    description: str = Field(..., description="巡检项的描述")
    fix: str = Field(..., description="修复建议方案")


class QueryInspectReportOutput(BaseModel):
    report_status: Optional[str] = None
    report_finish_time: Optional[str] = None
    summary: Optional[InspectSummary] = None
    checkItemResults: List[CheckItemResult] = Field(default_factory=list)
    error: Optional[ErrorModel] = None



