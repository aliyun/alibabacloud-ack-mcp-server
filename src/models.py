from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


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


class PromQLSample(BaseModel):
    """PromQL 最佳实践样例"""
    rule_name: str = Field(..., description="观测异常现象的PromQL查询规则名")
    description: Optional[str] = Field(None, description="此查询规则的详细描述")
    recommendation_sop: Optional[str] = Field(None, description="此查询规则观测到的异常如何解决的推荐SOP")
    expression: str = Field(..., description="PromQL 表达式")
    severity: str = Field(..., description="严重程度：Critical / Warning / Normal")
    category: str = Field(..., description="观测查询规则的使用场景")
    labels: List[str] = Field(default_factory=list, description="观测查询规则的关联资源labels列表")


class QueryPrometheusMetricGuidanceOutput(BaseModel):
    metrics: List[MetricDefinition] = Field(default_factory=list, description="指标定义列表")
    promql_samples: List[PromQLSample] = Field(default_factory=list, description="PromQL最佳实践样例列表")
    error: Optional[ErrorModel] = None


# ACK Diagnose Models
class DiagnoseResourceInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    region_id: str = Field(..., description="集群所在的 regionId")
    resource_type: str = Field(..., description="诊断的目标资源类型：node/ingress/cluster/memory/pod/service/network")
    resource_target: str = Field(..., description="用于指定诊断对象的参数，JSON 字符串格式")


class DiagnoseResourceOutput(BaseModel):
    diagnose_task_id: Optional[str] = None
    result: Optional[str] = None
    status: Optional[str] = None
    finished_time: Optional[str] = None
    resource_type: Optional[str] = None
    resource_target: Optional[str] = None
    error: Optional[ErrorModel] = None


class GetDiagnoseResourceResultInput(BaseModel):
    cluster_id: str = Field(..., description="ACK 集群 clusterId")
    region_id: str = Field(..., description="集群所在的 regionId")
    diagnose_task_id: str = Field(..., description="生成的异步诊断任务id")


class DiagnosisStatusEnum(Enum):
    CREATED = 0
    RUNNING = 1
    COMPLETED = 2


class DiagnosisCodeEnum(Enum):
    COMPLETED = 0
    FAILED = 1


class GetDiagnoseResourceResultOutput(BaseModel):
    result: Optional[str] = None
    status: Optional[str] = Field(..., description="诊断状态：诊断已创建, 诊断运行中, 诊断已完成")
    code: Optional[str] = Field(..., description="诊断结果：诊断完成, 诊断失败")
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
    targetType: Optional[str] = Field("", description="巡检项的目标资源对象")
    targets: List[str] = Field(default_factory=list, description="巡检项的目标资源对象名列表")
    description: str = Field(..., description="巡检项的描述")
    fix: str = Field(..., description="修复建议方案")
    checkItemUid: str = Field(..., description="巡检项的唯一标识uid")
    level: str = Field(..., description="巡检项所属级别。取值：/advice：建议/warning：低危/error：中危/critical：高危")


class QueryInspectReportOutput(BaseModel):
    report_status: Optional[str] = None
    report_finish_time: Optional[str] = None
    summary: Optional[InspectSummary] = None
    checkItemResults: List[CheckItemResult] = Field(default_factory=list)
    error: Optional[ErrorModel] = None


# ACK Cluster Management Models
class ListClustersInput(BaseModel):
    region_id: str = Field(..., description="区域ID，例如 cn-hangzhou")
    page_size: Optional[int] = Field(500, description="查询每个region集群列表的一页大小，默认500")
    page_num: Optional[int] = Field(1, description="查询每个region集群列表的分页页码，默认1")


class ClusterInfo(BaseModel):
    cluster_name: str = Field(..., description="集群名")
    cluster_id: str = Field(..., description="集群的唯一id")
    state: str = Field(..., description="集群当前的状态，例如 Running")
    region_id: str = Field(..., description="集群所在的region")
    cluster_type: str = Field(..., description="集群的类型，ManagedKubernetes（托管集群）、Kubernetes（专有版集群）")
    current_version: Optional[str] = Field(None, description="集群k8s版本")
    vpc_id: Optional[str] = Field(None, description="集群专有网络 ID")
    vswitch_ids: List[str] = Field(default_factory=list, description="控制面虚拟交换机")
    resource_group_id: Optional[str] = Field(None, description="资源组id")
    security_group_id: Optional[str] = Field(None, description="安全组id")
    # network_mode: Optional[str] = Field(None, description="网络类型")
    proxy_mode: Optional[str] = Field(None, description="kube-proxy 代理模式(ipvs, iptables)")
    tags: List[dict] = Field(default_factory=list, description="集群资源标签")
    container_cidr: Optional[str] = Field(None, description="容器网络 CIDR，使用Flannel网络插件下配置")
    service_cidr: Optional[str] = Field(None, description="服务网络 CIDR")
    api_server_endpoints: dict[str, str] = Field(default_factory=list, description="集群API Server 访问地址")


class ListClustersOutput(BaseModel):
    count: int = Field(..., description="返回的集群数")
    error: Optional[ErrorModel] = Field(None, description="错误信息")
    clusters: List[ClusterInfo] = Field(default_factory=list, description="集群列表")


# 错误码定义
class ClusterErrorCodes:
    NO_RAM_POLICY_AUTH = "NO_RAM_POLICY_AUTH"
    MISS_REGION_ID = "MISS_REGION_ID"


# ACK Audit Log Models
class QueryAuditLogsInput(BaseModel):
    cluster_id: str = Field(..., description="集群ID，例如 cxxxxx")
    namespace: Optional[str] = Field("default", description="命名空间，支持精确匹配和后缀通配符")
    verbs: Optional[str] = Field(None, description="操作动词，多个值用逗号分隔，如 get,list,create")
    resource_types: Optional[str] = Field(None, description="K8s资源类型，多个值用逗号分隔，如 pods,services")
    resource_name: Optional[str] = Field(None, description="资源名称，支持精确匹配和后缀通配符")
    user: Optional[str] = Field(None, description="用户名，支持精确匹配和后缀通配符")
    start_time: Optional[str] = Field("24h", description="查询开始时间，支持ISO 8601格式或相对时间")
    end_time: Optional[str] = Field(None, description="查询结束时间，支持ISO 8601格式或相对时间")
    limit: Optional[int] = Field(10, description="结果限制，默认10，最大100")


class AuditLogEntry(BaseModel):
    timestamp: Optional[str] = Field(None, description="日志时间戳")
    verb: Optional[str] = Field(None, description="操作动词")
    resource_type: Optional[str] = Field(None, description="资源类型")
    resource_name: Optional[str] = Field(None, description="资源名称")
    namespace: Optional[str] = Field(None, description="命名空间")
    user: Optional[str] = Field(None, description="用户名")
    source_ips: Optional[List[str]] = Field(default_factory=list, description="源IP地址")
    user_agent: Optional[str] = Field(None, description="用户代理")
    response_code: Optional[int] = Field(None, description="响应代码")
    response_status: Optional[str] = Field(None, description="响应状态")
    request_uri: Optional[str] = Field(None, description="请求URI")
    request_object: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求对象")
    response_object: Optional[Dict[str, Any]] = Field(default_factory=dict, description="响应对象")
    raw_log: Optional[str] = Field(None, description="原始日志内容")


class QueryAuditLogsOutput(BaseModel):
    query: Optional[str] = Field(None, description="查询语句")
    entries: List[AuditLogEntry] = Field(default_factory=list, description="返回的日志条目")
    total: int = Field(0, description="总数")
    error: Optional[ErrorModel] = Field(None, description="错误信息")


# 审计日志错误码定义
class AuditLogErrorCodes:
    SLS_CLIENT_INIT_AK_ERROR = "SLS_CLIENT_INIT_AK_ERROR"
    LOGSTORE_NOT_FOUND = "LOGSTORE_NOT_FOUND"
    CLUSTER_NOT_FOUND = "CLUSTER_NOT_FOUND"
    AUDIT_NOT_ENABLED = "AUDIT_NOT_ENABLED"


# ==================== 集群审计项目信息相关模型 ====================

class GetClusterAuditProjectInput(BaseModel):
    """获取集群审计项目信息输入参数"""
    cluster_id: str = Field(..., description="ACK 集群 ID")


class ClusterAuditProjectInfo(BaseModel):
    """集群审计项目信息"""
    sls_project_name: Optional[str] = Field(None, description="集群 API Server 审计日志所在的 SLS Project")
    audit_enabled: bool = Field(False, description="当前集群是否已启用 API Server 审计功能")


class GetClusterAuditProjectOutput(BaseModel):
    """获取集群审计项目信息输出结果"""
    cluster_id: str = Field(..., description="集群 ID")
    audit_info: Optional[ClusterAuditProjectInfo] = Field(None, description="审计项目信息")
    error: Optional[ErrorModel] = Field(None, description="错误信息")


# ==================== Kubectl 相关模型 ====================

class KubectlInput(BaseModel):
    """Kubectl 命令输入参数"""
    command: str = Field(..., description="kubectl 命令参数，例如 'get pods -A'")
    cluster_id: Optional[str] = Field(None, description="可选的集群 ID，如果提供则通过 ACK API 获取 kubeconfig")


class KubectlOutput(BaseModel):
    """Kubectl 命令输出结果"""
    command: str = Field(..., description="kubectl 命令参数，例如 'get pods -A'")
    stdout: str = Field("", description="kubectl 命令执行结果")
    stderr: str = Field("", description="kubectl 命令执行失败的结果")
    exit_code: int = Field(0, description="kubectl 命令执行结果码")


class GetClusterKubeConfigOutput(BaseModel):
    """get_cluster_kubeconfig 命令输出结果"""
    error: Optional[ErrorModel] = Field(None, description="错误信息")
    kubeconfig: Optional[str] = Field(None, description="KUBECONFIG file path for an ACK cluster")


# Kubectl 错误码定义
class KubectlErrorCodes:
    KUBECONFIG_FETCH_FAILED = "KUBECONFIG_FETCH_FAILED"
    CLUSTER_NOT_FOUND = "CLUSTER_NOT_FOUND"
    INVALID_CLUSTER_ID = "INVALID_CLUSTER_ID"
    KUBECTL_COMMAND_FAILED = "KUBECTL_COMMAND_FAILED"


class GetCurrentTimeOutput(BaseModel):
    """获取当前时间的输出模型"""
    current_time_iso: str = Field(..., description="当前时间，ISO 8601 格式 (UTC)")
    current_time_unix: int = Field(..., description="当前时间，Unix 时间戳（秒级）")
    timezone: str = Field(default="UTC", description="时区信息")
    error: Optional[ErrorModel] = None


# ==================== 控制面日志相关模型 ====================

class QueryControlPlaneLogsInput(BaseModel):
    """查询控制面日志输入参数"""
    cluster_id: str = Field(..., description="集群ID，例如 cxxxxx")
    component_name: str = Field(..., description="控制面组件的名称，如 apiserver, kcm, scheduler, ccm")
    filter_pattern: Optional[str] = Field(None, description="额外过滤条件")
    start_time: Optional[str] = Field("24h", description="查询开始时间，支持ISO 8601格式或相对时间")
    end_time: Optional[str] = Field(None, description="查询结束时间，支持ISO 8601格式或相对时间")
    limit: Optional[int] = Field(10, description="结果限制，默认10，最大100")


class ControlPlaneLogEntry(BaseModel):
    """控制面日志条目"""
    timestamp: Optional[str] = Field(None, description="日志时间戳")
    level: Optional[str] = Field(None, description="日志级别")
    component: Optional[str] = Field(None, description="组件名称")
    message: Optional[str] = Field(None, description="日志消息")
    source: Optional[str] = Field(None, description="日志来源")
    raw_log: Optional[str] = Field(None, description="原始日志内容")


class QueryControlPlaneLogsOutput(BaseModel):
    """查询控制面日志输出结果"""
    query: Optional[str] = Field(None, description="查询语句")
    entries: List[ControlPlaneLogEntry] = Field(default_factory=list, description="返回的日志条目")
    total: int = Field(0, description="总数")
    error: Optional[ErrorModel] = Field(None, description="错误信息")


# 控制面日志错误码定义
class ControlPlaneLogErrorCodes:
    SLS_CLIENT_INIT_AK_ERROR = "SLS_CLIENT_INIT_AK_ERROR"
    LOGSTORE_NOT_FOUND = "LOGSTORE_NOT_FOUND"
    CLUSTER_NOT_FOUND = "CLUSTER_NOT_FOUND"
    CONTROLPLANE_LOG_NOT_ENABLED = "CONTROLPLANE_LOG_NOT_ENABLED"
    INVALID_COMPONENT = "INVALID_COMPONENT"


# ==================== 控制面日志配置相关模型 ====================

class ControlPlaneLogConfig(BaseModel):
    """控制面日志配置信息"""
    log_project: Optional[str] = Field(None, description="控制面组件日志对应存储的 SLS Project 名称")
    log_ttl: Optional[str] = Field(None, description="日志在 SLS logstore 里的数据保存时间，单位：天")
    aliuid: Optional[str] = Field(None, description="阿里云账号 ID")
    components: List[str] = Field(default_factory=list, description="当前开启控制面日志的组件列表")


class GetControlPlaneLogConfigOutput(BaseModel):
    """获取控制面日志配置输出结果"""
    cluster_id: str = Field(..., description="集群 ID")
    config: Optional[ControlPlaneLogConfig] = Field(None, description="控制面日志配置信息")
    error: Optional[ErrorModel] = Field(None, description="错误信息")
