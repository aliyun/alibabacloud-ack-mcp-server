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



