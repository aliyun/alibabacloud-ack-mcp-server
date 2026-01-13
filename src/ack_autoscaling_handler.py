"""ACK Autoscaling Handler - Autoscaling and workload elasticity analysis."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
import subprocess

from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import httpx
import time
import math
from datetime import datetime

from models import (
    WorkloadAutoscalingAnalysisOutput,
    WorkloadResourceProfile,
    HPARecommendation,
    ErrorModel,
    ExecutionLog,
    enable_execution_log_ctx,
)

# 波动性分析参数配置
PROMETHEUS_QUERY_DURATION = 7 * 24 * 3600  # Prometheus 查询时长（秒），默认 7 天

STD_DEV_SCALE_FACTOR_CPU = 1  # CPU 标准差归一化缩放因子
STD_DEV_SCALE_FACTOR_MEMORY = 3  # Memory 标准差归一化缩放因子

VOLATILITY_COVERAGE_WINDOW = 60 * 60  # 波动覆盖率窗口大小（秒），默认 1 小时

AMPLITUDE_WINDOW_DURATION = 3 * 60  # 振幅检测窗口大小（秒），默认 30 分钟
AMPLITUDE_TIME_DIFFERENCE = 3 * 60  # 振幅检测窗口间隔要求（秒），默认 30 分钟
AMPLITUDE_THRESHOLD_MULTIPLIER = 1.3  # 振幅判断阈值倍数（相对于 pod_request）
AMPLITUDE_WINDOW_STEP = 5  # 振幅检测窗口滑动步长

VOLATILITY_SCORE_WEIGHT_AMPLITUDE = 0.7  # 振幅指标权重
VOLATILITY_SCORE_WEIGHT_STD_DEV = 0.2  # 标准差指标权重
VOLATILITY_SCORE_WEIGHT_COVERAGE = 0.1  # 波动覆盖率指标权重

VOLATILITY_THRESHOLD = 0.75  # 波动性综合评分阈值

# HPA 推荐参数配置
MIN_REPLICAS_FOR_HPA = 1  # HPA 最小副本数要求
MIN_READY_RATIO_FOR_HPA = 0.5  # Ready Pod 比例阈值

HPA_DEFAULT_MIN_REPLICAS = 1

HPA_CPU_PERCENTILE_FOR_AVG = 0.9  # CPU averageUtilization 计算的分位值
HPA_MEMORY_PERCENTILE_FOR_AVG = 0.9  # Memory averageUtilization 计算的分位值
HPA_CPU_PERCENTILE_FOR_MINMAX = 0.95  # CPU min/maxReplicas 计算的分位值
HPA_MEMORY_PERCENTILE_FOR_MINMAX = 0.95  # Memory min/maxReplicas 计算的分位值

HPA_MIN_TARGET_UTILIZATION = 0.3  # averageUtilization 最小值
HPA_MAX_TARGET_UTILIZATION = 0.75  # averageUtilization 最大值

HPA_MIN_REPLICAS_TARGET_UTIL_CPU = 0.5  # minReplicas 计算的 CPU 目标利用率
HPA_MIN_REPLICAS_TARGET_UTIL_MEMORY = 0.5  # minReplicas 计算的 Memory 目标利用率

HPA_MAX_REPLICAS_FACTOR = 3  # maxReplicas 计算的放大系数

@dataclass
class ElasticityAnalysisResult:
    resource_analysis: List[WorkloadResourceProfile]
    autoscaling_recommended: bool

@dataclass
class WorkloadPrecheckResult:
    stable_for_hpa: bool
    replicas: int
    ready_replicas: int
    ready_ratio: float
    message: str = ""


from ack_prometheus_handler import PrometheusHandler
from kubectl_handler import get_context_manager


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    cs_client_factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region, config)


class ACKAutoscalingHandler:
    """Handler for autoscaling related analysis operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or {}
        self.enable_execution_log = self.settings.get("enable_execution_log", False)
        self.kubectl_timeout = self.settings.get("kubectl_timeout", 30)
        self.allow_write = self.settings.get("allow_write", False)

        self._prometheus_helper = PrometheusHandler(server=None, settings=self.settings)

        if server is None:
            return
        self.server = server

        self.server.tool(
            name="analyze_workload_autoscaling",
            description="评估特定工作负载的弹性伸缩特征，并给出 HPA 配置推荐",
        )(self.analyze_workload_autoscaling)

        logger.info("ACK Autoscaling Handler initialized")

    async def analyze_workload_autoscaling(
        self,
        ctx: Context,
        cluster_id: str = Field(..., description="集群 ID"),
        namespace: str = Field(..., description="命名空间名称"),
        workload_type: str = Field(..., description="工作负载类型"),
        workload_name: str = Field(..., description="工作负载名称"),
    ) -> WorkloadAutoscalingAnalysisOutput:
        """评估工作负载的弹性伸缩特征，并给出 HPA 配置推荐"""

        enable_execution_log_ctx.set(self.enable_execution_log)

        start_ms = int(time.time() * 1000)
        execution_log = ExecutionLog(
            tool_call_id=f"analyze_workload_autoscaling_{cluster_id}_{namespace}_{workload_name}_{start_ms}",
            start_time=datetime.utcnow().isoformat() + "Z",
        )

        try:
            endpoint = self._prometheus_helper._resolve_prometheus_endpoint(
                ctx, cluster_id, execution_log
            )
            if not endpoint:
                error_msg = "无法获取 Prometheus HTTP API，请确定此集群是否已经正常部署阿里云Prometheus 或 环境变量 PROMETHEUS_HTTP_API[_<cluster_id>]"
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": "MissingEndpoint",
                    "failure_stage": "resolve_endpoint",
                }
                return WorkloadAutoscalingAnalysisOutput(
                    cluster_id=cluster_id,
                    namespace=namespace,
                    workload_type=workload_type,
                    workload_name=workload_name,
                    resource_analysis=[],
                    error=ErrorModel(
                        error_code="MissingEndpoint",
                        error_message=error_msg,
                    ),
                    execution_log=execution_log,
                )

            execution_log.messages.append("Stage 1: Prechecking workload stability for HPA eligibility")

            precheck_result = await self._precheck_workload_stability(
                ctx, cluster_id, namespace, workload_type, workload_name, execution_log
            )

            execution_log.messages.append(
                "Stage 2: Analyzing workload elasticity characteristics"
            )

            elasticity_result = await self._analyze_workload_elasticity(
                ctx, endpoint, cluster_id, namespace, workload_type, workload_name, execution_log
            )

            if not precheck_result.stable_for_hpa:
                message = precheck_result.message if precheck_result.message else "工作负载不满足 HPA 基础稳定性条件"
                execution_log.messages.append(f"Overall analysis indicates this workload is not suitable for autoscaling: {message}")
                hpa_recommendation = HPARecommendation(recommended=False, message=message)
            elif not elasticity_result.autoscaling_recommended:
                message = "工作负载在观测周期内资源使用波动不明显，不建议开启 HPA"
                execution_log.messages.append(f"Overall analysis indicates this workload is not suitable for autoscaling: {message}")
                hpa_recommendation = HPARecommendation(recommended=False, message=message)
            else:
                execution_log.messages.append(
                    "Overall analysis indicates this workload is suitable for autoscaling; proceeding to HPA recommendation analysis"
                )
                hpa_recommendation = await self._analyze_hpa_recommendation(
                    ctx, endpoint, cluster_id, namespace, workload_type, workload_name, elasticity_result.resource_analysis, execution_log
                )

            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms

            return WorkloadAutoscalingAnalysisOutput(
                cluster_id=cluster_id,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
                resource_analysis=elasticity_result.resource_analysis,
                hpa_recommendation=hpa_recommendation,
                execution_log=execution_log,
            )

        except Exception as e:
            logger.error(f"Failed to analyze workload autoscaling: {e}")
            execution_log.error = str(e)
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms
            execution_log.metadata = {
                "error_type": type(e).__name__,
                "failure_stage": "analyze_workload_autoscaling",
            }
            return WorkloadAutoscalingAnalysisOutput(
                cluster_id=cluster_id,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
                resource_analysis=[],
                error=ErrorModel(
                    error_code="UnknownError",
                    error_message=str(e),
                ),
                execution_log=execution_log,
            )

    # ==================== 阶段一：Workload 前置稳定性检查 ====================

    async def _precheck_workload_stability(
        self,
        ctx: Context,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        execution_log: ExecutionLog,
    ) -> WorkloadPrecheckResult:
        """Workload 前置稳定性检查：判断是否满足开启 HPA 的基础条件。"""
        try:
            cs_client = _get_cs_client(ctx, "CENTER")
            context_manager = get_context_manager()
            context_manager.set_cs_client(cs_client)

            kubeconfig_path = context_manager.get_kubeconfig_path(
                cluster_id,
                self.settings.get("kubeconfig_mode"),
                self.settings.get("kubeconfig_path"),
                execution_log,
            )

            command = (
                f"kubectl --kubeconfig {kubeconfig_path} "
                f"get {workload_type} {workload_name} -n {namespace} -o json"
            )

            cmd_start = int(time.time() * 1000)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.kubectl_timeout,
            )
            cmd_duration = int(time.time() * 1000) - cmd_start

            execution_log.api_calls.append(
                {
                    "api": "KubectlPrecheckWorkload",
                    "command": f"get {workload_type} {workload_name} -n {namespace} -o json",
                    "duration_ms": cmd_duration,
                    "exit_code": result.returncode,
                    "status": "success" if result.returncode == 0 else "failed",
                }
            )

            if result.returncode != 0:
                execution_log.warnings.append(
                    f"Precheck: kubectl failed to get workload spec/status: {result.stderr}"
                )
                return WorkloadPrecheckResult(
                    stable_for_hpa=False,
                    replicas=0,
                    ready_replicas=0,
                    ready_ratio=0.0,
                )

            workload_json = json.loads(result.stdout)
            spec = workload_json.get("spec", {}) or {}
            status = workload_json.get("status", {}) or {}

            replicas = (
                spec.get("replicas")
                or status.get("replicas")
                or 1
            )
            try:
                replicas = int(replicas)
            except Exception as e:
                execution_log.warnings.append(f"Failed to parse replicas value, using default: {e}")
                replicas = 1

            ready_replicas = status.get("readyReplicas") or 0
            try:
                ready_replicas = int(ready_replicas)
            except Exception as e:
                execution_log.warnings.append(f"Failed to parse ready_replicas value, using default: {e}")
                ready_replicas = 0

            ready_ratio = (
                float(ready_replicas) / float(replicas)
                if replicas > 0
                else 0.0
            )

            stable_for_hpa = True
            reasons = []
            if replicas < MIN_REPLICAS_FOR_HPA:
                stable_for_hpa = False
                reasons.append(f"副本数={replicas}，低于 HPA 最小阈值({MIN_REPLICAS_FOR_HPA})")
                execution_log.messages.append(
                    f"Precheck: replicas={replicas} is below minimum threshold for HPA ({MIN_REPLICAS_FOR_HPA})"
                )

            if ready_ratio < MIN_READY_RATIO_FOR_HPA:
                stable_for_hpa = False
                reasons.append(f"Ready 比例={ready_ratio:.2f}，低于稳定性阈值({MIN_READY_RATIO_FOR_HPA:.2f})")
                execution_log.messages.append(
                    f"Precheck: ready_ratio={ready_ratio:.2f} is below stability threshold ({MIN_READY_RATIO_FOR_HPA:.2f})"
                )

            message = "；".join(reasons) if reasons else ""

            execution_log.messages.append(
                f"Precheck summary: replicas={replicas}, ready_replicas={ready_replicas}, ready_ratio={ready_ratio:.2f}"
            )

            return WorkloadPrecheckResult(
                stable_for_hpa=stable_for_hpa,
                replicas=replicas,
                ready_replicas=ready_replicas,
                ready_ratio=ready_ratio,
                message=message,
            )

        except subprocess.TimeoutExpired:
            execution_log.warnings.append(
                "Precheck: timeout while querying workload via kubectl"
            )
            return WorkloadPrecheckResult(
                stable_for_hpa=False,
                replicas=0,
                ready_replicas=0,
                ready_ratio=0.0,
            )
        except json.JSONDecodeError as e:
            execution_log.warnings.append(
                f"Precheck: failed to parse workload JSON: {str(e)}"
            )
            return WorkloadPrecheckResult(
                stable_for_hpa=False,
                replicas=0,
                ready_replicas=0,
                ready_ratio=0.0,
            )
        except Exception as e:
            execution_log.warnings.append(
                f"Precheck: unexpected error while checking workload stability: {str(e)}"
            )
            return WorkloadPrecheckResult(
                stable_for_hpa=False,
                replicas=0,
                ready_replicas=0,
                ready_ratio=0.0,
            )

    # ==================== 阶段二：弹性特征分析 ====================

    async def _analyze_workload_elasticity(
        self,
        ctx: Context,
        endpoint: str,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        execution_log: ExecutionLog,
    ) -> ElasticityAnalysisResult:
        """综合分析工作负载的弹性相关信号，并给出是否建议开启弹性伸缩的判断。"""
        volatility_results = await self._analyze_resources_volatility(
            ctx, endpoint, cluster_id, namespace, workload_type, workload_name, execution_log
        )
        if not volatility_results:
            execution_log.warnings.append(
                "No valid resource time-series data available for elasticity analysis; autoscaling not recommended. "
                "Check if Prometheus data collection is working correctly."
            )
            return ElasticityAnalysisResult(
                resource_analysis=[],
                autoscaling_recommended=False,
            )

        has_volatile = any(r.is_volatile for r in volatility_results)
        return ElasticityAnalysisResult(
            resource_analysis=volatility_results,
            autoscaling_recommended=has_volatile,
        )

    async def _analyze_resources_volatility(
        self,
        ctx: Context,
        endpoint: str,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        execution_log: ExecutionLog,
    ) -> List[WorkloadResourceProfile]:
        """分析 CPU 和内存的资源使用特征，用于评估弹性适配性。"""
        results = []
        now_sec = int(time.time())
        start_sec = now_sec - PROMETHEUS_QUERY_DURATION

        cpu_result = await self._analyze_single_resource_volatility(
            ctx, endpoint, cluster_id, namespace, workload_type, workload_name,
            resource_type="cpu",
            start_sec=start_sec,
            end_sec=now_sec,
            execution_log=execution_log,
        )
        if cpu_result:
            results.append(cpu_result)

        memory_result = await self._analyze_single_resource_volatility(
            ctx, endpoint, cluster_id, namespace, workload_type, workload_name,
            resource_type="memory",
            start_sec=start_sec,
            end_sec=now_sec,
            execution_log=execution_log,
        )
        if memory_result:
            results.append(memory_result)

        return results

    async def _analyze_single_resource_volatility(
        self,
        ctx: Context,
        endpoint: str,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        resource_type: str,
        start_sec: int,
        end_sec: int,
        execution_log: ExecutionLog,
    ) -> Optional[WorkloadResourceProfile]:
        """分析单个资源维度的特征。

        使用三个指标计算波动性：
        1. 标准差(std_dev): 衡量数据离散程度
        2. 振幅(amplitude): 滑动窗口间最大波动
        3. 波动覆盖率(coverage): 波动窗口比例

        """
        try:
            samples = await self._query_resource_time_series_with_timestamp(
                endpoint, cluster_id, namespace, workload_name, resource_type, start_sec, end_sec, execution_log
            )

            if not samples:
                execution_log.warnings.append(
                    f"No {resource_type} data points collected for workload '{workload_name}' in namespace '{namespace}'"
                )
                return None

            time_series = {"samples": samples}
            values = [s["value"] for s in samples]
            max_value = max(values)
            min_value = min(values)
            avg_value = sum(values) / len(values)
            p95_value = self._calculate_percentile_value(values, 0.95)
            p99_value = self._calculate_percentile_value(values, 0.99)

            original_pod_request = await self._get_pod_request(
                ctx, cluster_id, namespace, workload_type, workload_name, resource_type, execution_log
            )
            
            # 用于波动性算法的 request 基准值
            calculated_pod_request = original_pod_request
            if not original_pod_request or original_pod_request <= 0:
                execution_log.warnings.append(
                    f"{resource_type} Unable to retrieve pod request; using percentile-based capacity baseline for volatility calculation"
                )
                # CPU 使用 P95，Memory 使用 P99，与资源画像保持一致
                percentile_value = p95_value if resource_type == "cpu" else p99_value
                calculated_pod_request = percentile_value

            scale_factor = STD_DEV_SCALE_FACTOR_CPU if resource_type == "cpu" else STD_DEV_SCALE_FACTOR_MEMORY
            std_dev = self._calculate_std_dev(time_series, scale_factor)
            amplitude = self._calculate_amplitude(time_series, calculated_pod_request)
            coverage = self._calculate_volatility_coverage(time_series, calculated_pod_request)
            score = (
                VOLATILITY_SCORE_WEIGHT_AMPLITUDE * amplitude + 
                VOLATILITY_SCORE_WEIGHT_STD_DEV * std_dev + 
                VOLATILITY_SCORE_WEIGHT_COVERAGE * coverage
            )

            is_volatile = score >= VOLATILITY_THRESHOLD

            execution_log.messages.append(
                f"Volatility analysis for {resource_type}: max={max_value:.6f}, min={min_value:.6f}, "
                f"request={calculated_pod_request:.6f}, std_dev={std_dev:.6f}, amplitude={amplitude:.6f}, "
                f"coverage={coverage:.6f}, score={score:.6f}, volatile={is_volatile}"
            )

            # 精度处理：CPU 3位小数，Memory 1位小数
            precision = 3 if resource_type == "cpu" else 1
            # 单位后缀：CPU 为 Core，Memory 为 MiB
            unit = " Core" if resource_type == "cpu" else " MiB"

            # pod_request 字段：仅展示原始配置值，若未配置则为 None
            pod_request_str = None
            if original_pod_request and original_pod_request > 0:
                pod_request_str = f"{round(original_pod_request, precision)}{unit}"

            return WorkloadResourceProfile(
                resource_type=resource_type,
                pod_request=pod_request_str,
                is_volatile=is_volatile,
                percentiles={
                    "min": f"{round(min_value, precision)}{unit}",
                    "max": f"{round(max_value, precision)}{unit}",
                    "avg": f"{round(avg_value, precision)}{unit}",
                    "p95": f"{round(p95_value, precision)}{unit}",
                    "p99": f"{round(p99_value, precision)}{unit}",
                },
            )

        except httpx.HTTPStatusError as e:
            execution_log.warnings.append(
                f"Prometheus query failed for {resource_type}: {e.response.status_code} - {e.response.text}"
            )
            return None
        except Exception as e:
            execution_log.warnings.append(f"Volatility analysis failed for {resource_type}: {str(e)}")
            return None

    # ==================== 阶段三：HPA 推荐分析 ====================

    async def _analyze_hpa_recommendation(
        self,
        ctx: Context,
        endpoint: str,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        volatility_results: List[WorkloadResourceProfile],
        execution_log: ExecutionLog,
    ) -> Optional[HPARecommendation]:
        """基于分位数算法推荐 HPA 配置。"""
        try:
            # 获取 CPU 和 Memory 的波动性结果
            cpu_volatile = False
            memory_volatile = False
            cpu_request = None
            memory_request = None

            for result in volatility_results:
                if result.resource_type == "cpu":
                    cpu_volatile = result.is_volatile
                    # 从字符串中提取数值，如 "0.2 Core" -> 0.2
                    if result.pod_request:
                        parts = result.pod_request.split()
                        if parts:
                            cpu_request = float(parts[0])
                elif result.resource_type == "memory":
                    memory_volatile = result.is_volatile
                    # 从字符串中提取数值，如 "512.0 MiB" -> 512.0
                    if result.pod_request:
                        parts = result.pod_request.split()
                        if parts:
                            memory_request = float(parts[0])

            # 重新查询历史数据用于分位数计算
            now_sec = int(time.time())
            start_sec = now_sec - PROMETHEUS_QUERY_DURATION

            cpu_samples = await self._query_resource_time_series_with_timestamp(
                endpoint, cluster_id, namespace, workload_name, "cpu", start_sec, now_sec, execution_log
            )
            memory_samples = await self._query_resource_time_series_with_timestamp(
                endpoint, cluster_id, namespace, workload_name, "memory", start_sec, now_sec, execution_log
            )

            # 提取纯数值列表用于分位数计算
            cpu_values = [s["value"] for s in cpu_samples]
            memory_values = [s["value"] for s in memory_samples]

            # 获取 pod_request（如果波动性分析中没有）
            if not cpu_request:
                cpu_request = await self._get_pod_request(
                    ctx, cluster_id, namespace, workload_type, workload_name, "cpu", execution_log
                )
            if not memory_request:
                memory_request = await self._get_pod_request(
                    ctx, cluster_id, namespace, workload_type, workload_name, "memory", execution_log
                )

            if not cpu_request or not memory_request:
                execution_log.warnings.append("Failed to retrieve pod request for HPA recommendation")
                return HPARecommendation(recommended=False, message="无法获取 Pod Request 配置，无法生成 HPA 推荐")

            execution_log.messages.append(
                f"HPA input: cpu_samples={len(cpu_values)}, memory_samples={len(memory_values)}, "
                f"cpu_req={cpu_request:.3f}, mem_req={memory_request:.1f}"
            )

            # 计算统计数据
            if not cpu_values or not memory_values:
                execution_log.warnings.append("Insufficient sample data for HPA recommendation")
                return HPARecommendation(recommended=False, message="Prometheus 历史数据不足，无法生成 HPA 推荐")

            cpu_avg = sum(cpu_values) / len(cpu_values)
            memory_avg = sum(memory_values) / len(memory_values)
            cpu_p_avg = self._calculate_percentile_value(cpu_values, HPA_CPU_PERCENTILE_FOR_AVG)
            memory_p_avg = self._calculate_percentile_value(memory_values, HPA_MEMORY_PERCENTILE_FOR_AVG)
            cpu_p_minmax = self._calculate_percentile_value(cpu_values, HPA_CPU_PERCENTILE_FOR_MINMAX)
            memory_p_minmax = self._calculate_percentile_value(memory_values, HPA_MEMORY_PERCENTILE_FOR_MINMAX)

            execution_log.messages.append(
                f"HPA percentiles: "
                f"cpu(p{int(HPA_CPU_PERCENTILE_FOR_AVG*100)}={cpu_p_avg:.3f}, p{int(HPA_CPU_PERCENTILE_FOR_MINMAX*100)}={cpu_p_minmax:.3f}), "
                f"memory(p{int(HPA_MEMORY_PERCENTILE_FOR_AVG*100)}={memory_p_avg:.1f}, p{int(HPA_MEMORY_PERCENTILE_FOR_MINMAX*100)}={memory_p_minmax:.1f})"
            )

            # 计算 averageUtilization
            cpu_avg_util = self._calculate_average_utilization(
                cpu_values, cpu_request, HPA_CPU_PERCENTILE_FOR_AVG
            )
            memory_avg_util = self._calculate_average_utilization(
                memory_values, memory_request, HPA_MEMORY_PERCENTILE_FOR_AVG
            )

            if cpu_avg_util is None or memory_avg_util is None:
                execution_log.warnings.append("Failed to calculate average utilization for HPA recommendation")
                return HPARecommendation(recommended=False, message="无法生成 HPA 推荐")

            # 分别限制在合理范围内
            cpu_target_util = max(HPA_MIN_TARGET_UTILIZATION, min(cpu_avg_util, HPA_MAX_TARGET_UTILIZATION))
            memory_target_util = max(HPA_MIN_TARGET_UTILIZATION, min(memory_avg_util, HPA_MAX_TARGET_UTILIZATION))

            # 计算 minReplicas
            cpu_min_replicas = self._calculate_min_replicas(
                cpu_values, cpu_request, HPA_CPU_PERCENTILE_FOR_MINMAX, HPA_MIN_REPLICAS_TARGET_UTIL_CPU
            )
            memory_min_replicas = self._calculate_min_replicas(
                memory_values, memory_request, HPA_MEMORY_PERCENTILE_FOR_MINMAX, HPA_MIN_REPLICAS_TARGET_UTIL_MEMORY
            )

            if cpu_min_replicas is None or memory_min_replicas is None:
                execution_log.warnings.append("Failed to calculate min replicas for HPA recommendation")
                return HPARecommendation(recommended=False, message="无法生成 HPA 推荐")

            min_replicas = max(HPA_DEFAULT_MIN_REPLICAS, int(math.ceil(max(cpu_min_replicas, memory_min_replicas))))

            # 计算 maxReplicas
            cpu_max_replicas = self._calculate_max_replicas(
                cpu_values, cpu_request, HPA_CPU_PERCENTILE_FOR_MINMAX, cpu_target_util, HPA_MAX_REPLICAS_FACTOR
            )
            memory_max_replicas = self._calculate_max_replicas(
                memory_values, memory_request, HPA_MEMORY_PERCENTILE_FOR_MINMAX, memory_target_util, HPA_MAX_REPLICAS_FACTOR
            )

            if cpu_max_replicas is None or memory_max_replicas is None:
                execution_log.warnings.append("Failed to calculate max replicas for HPA recommendation")
                return HPARecommendation(recommended=False, message="无法生成 HPA 推荐")

            max_replicas = int(math.ceil(max(cpu_max_replicas, memory_max_replicas)))

            # 校验：最大副本数必须大于最小副本数
            if max_replicas <= min_replicas:
                execution_log.warnings.append(
                    f"HPA recommendation skipped: max_replicas({max_replicas}) must be greater than min_replicas({min_replicas})"
                )
                return HPARecommendation(recommended=False, message=f"无法生成 HPA 推荐")

            # 根据波动性结果构建 target_utilization
            target_utilization_dict = {}
            if cpu_volatile:
                target_utilization_dict["cpu"] = f"{int(cpu_target_util * 100)}%"
            if memory_volatile:
                target_utilization_dict["memory"] = f"{int(memory_target_util * 100)}%"

            # 计算历史平均利用率
            average_utilization_dict = {}
            if cpu_volatile and cpu_request > 0:
                average_utilization_dict["cpu"] = f"{int(round(cpu_avg / cpu_request * 100))}%"
            if memory_volatile and memory_request > 0:
                average_utilization_dict["memory"] = f"{int(round(memory_avg / memory_request * 100))}%"

            # 生成日志
            metrics_str = ",".join(target_utilization_dict.keys()) if target_utilization_dict else "none"
            execution_log.messages.append(
                f"HPA result: metrics={metrics_str}, "
                f"cpu_target={int(cpu_target_util * 100)}%, memory_target={int(memory_target_util * 100)}%, "
                f"min_replicas={min_replicas}, max_replicas={max_replicas}"
            )

            return HPARecommendation(
                recommended=True,
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                target_utilization=target_utilization_dict,
                average_utilization=average_utilization_dict,
                message="HPA 推荐基于当前 Pod Request 配置计算。若 Request 配置不合理，将影响 HPA 推荐的准确性。建议先使用资源画像功能优化 Request 配置，再应用 HPA 推荐。",
            )

        except Exception as e:
            logger.error(f"HPA recommendation analysis failed: {e}")
            execution_log.warnings.append(f"HPA recommendation analysis failed: {str(e)}")
            return HPARecommendation(recommended=False, message=f"HPA 推荐分析失败: {str(e)}")

    # ==================== HPA 推荐算法辅助函数 ====================

    async def _query_resource_time_series_with_timestamp(
        self,
        endpoint: str,
        cluster_id: str,
        namespace: str,
        workload_name: str,
        resource_type: str,
        start_sec: int,
        end_sec: int,
        execution_log: ExecutionLog,
    ) -> List[Dict[str, Any]]:
        """查询资源的历史时序数据，返回带时间戳的样本列表。"""
        try:
            if resource_type == "cpu":
                promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{workload_name}.*",container!="",container!="POD"}}[2m]))'
            elif resource_type == "memory":
                promql = f'sum(container_memory_working_set_bytes{{namespace="{namespace}",pod=~"{workload_name}.*",container!="",container!="POD"}})'
            else:
                return []

            params = {
                "query": promql,
                "start": str(start_sec),
                "end": str(end_sec),
                "step": "60s",
            }
            url = endpoint.rstrip("/") + "/api/v1/query_range"

            execution_log.messages.append(f"Querying {resource_type} metrics with PromQL: {promql}")

            api_start = int(time.time() * 1000)
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            api_duration = int(time.time() * 1000) - api_start
            execution_log.api_calls.append({
                "api": "PrometheusQueryRange",
                "resource_type": resource_type,
                "endpoint": url,
                "cluster_id": cluster_id,
                "duration_ms": api_duration,
                "status": "success",
                "http_status": resp.status_code,
            })

            result_data = data.get("data", {}) if isinstance(data, dict) else {}
            result_series = result_data.get("result", []) if isinstance(result_data, dict) else []

            samples = []
            if result_series and isinstance(result_series, list) and len(result_series) > 0:
                series = result_series[0]
                if isinstance(series, dict):
                    series_values = series.get("values", [])
                    for item in series_values:
                        if not isinstance(item, (list, tuple)) or len(item) < 2:
                            continue
                        try:
                            timestamp = int(item[0])
                            val = float(item[1])
                            if resource_type == "memory":
                                val = val / (1024 * 1024)  # bytes 转 MiB
                            samples.append({"timestamp": timestamp, "value": val})
                        except Exception:
                            continue

            samples.sort(key=lambda x: x["timestamp"])
            execution_log.messages.append(
                f"Collected {len(samples)} workload-level data points for {resource_type} analysis"
            )
            return samples

        except Exception as e:
            execution_log.warnings.append(f"Failed to query {resource_type} time series: {str(e)}")
            return []

    def _calculate_average_utilization(self, values: List[float], request: float, percentile: float) -> Optional[float]:
        """计算 averageUtilization = Percentile / Request。"""
        if not values or not request or request <= 0:
            return None
        percentile_value = self._calculate_percentile_value(values, percentile)
        return percentile_value / request

    def _calculate_percentile_value(self, values: List[float], percentile: float) -> Optional[float]:
        """计算分位数原始值。"""
        if not values:
            return None
        values_sorted = sorted(values)
        index = int(len(values_sorted) * percentile)
        index = min(index, len(values_sorted) - 1)
        return values_sorted[index]

    def _calculate_min_replicas(
        self, values: List[float], request: float, percentile: float, target_util: float
    ) -> Optional[float]:
        """计算 minReplicas = Percentile / (TargetUtil * Request)。"""
        if not values or not request or request <= 0 or target_util <= 0:
            return None
        percentile_value = self._calculate_percentile_value(values, percentile)
        if percentile_value is None:
            return None
        return percentile_value / (target_util * request)

    def _calculate_max_replicas(
        self, values: List[float], request: float, percentile: float, target_util: float, factor: float
    ) -> Optional[float]:
        """计算 maxReplicas = (Percentile * Factor) / (TargetUtil * Request)。"""
        if not values or not request or request <= 0 or target_util <= 0:
            return None
        percentile_value = self._calculate_percentile_value(values, percentile)
        if percentile_value is None:
            return None
        return (percentile_value * factor) / (target_util * request)

    # ==================== 波动性算法辅助函数 ====================

    async def _get_pod_request(
        self,
        ctx: Context,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        resource_type: str,
        execution_log: ExecutionLog,
    ) -> Optional[float]:
        """查询 workload 的 pod request 值（使用最小值作为基准容量）。"""
        try:
            cs_client = _get_cs_client(ctx, "CENTER")
            context_manager = get_context_manager()
            context_manager.set_cs_client(cs_client)

            kubeconfig_path = context_manager.get_kubeconfig_path(
                cluster_id, 
                self.settings.get("kubeconfig_mode"), 
                self.settings.get("kubeconfig_path"), 
                execution_log
            )

            command = f"kubectl --kubeconfig {kubeconfig_path} get {workload_type} {workload_name} -n {namespace} -o json"
            
            cmd_start = int(time.time() * 1000)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.kubectl_timeout
            )
            cmd_duration = int(time.time() * 1000) - cmd_start

            execution_log.api_calls.append({
                "api": "KubectlGetWorkload",
                "command": f"get {workload_type} {workload_name} -n {namespace} -o json",
                "duration_ms": cmd_duration,
                "exit_code": result.returncode,
                "status": "success" if result.returncode == 0 else "failed",
            })

            if result.returncode != 0:
                execution_log.warnings.append(
                    f"{resource_type} kubectl 查询 workload 失败: {result.stderr}"
                )
                return None

            workload_json = json.loads(result.stdout)
            containers = workload_json.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            if not containers:
                execution_log.warnings.append(f"No containers found in {resource_type} workload")
                return None

            total_request = 0.0
            found_request = False

            for container in containers:
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                
                if resource_type == "cpu":
                    request_str = requests.get("cpu")
                    if request_str:
                        request_value = self._parse_cpu_value(request_str)
                        if request_value:
                            total_request += request_value
                            found_request = True
                elif resource_type == "memory":
                    request_str = requests.get("memory")
                    if request_str:
                        request_value = self._parse_memory_value(request_str)
                        if request_value:
                            total_request += request_value
                            found_request = True

            if found_request and total_request > 0:
                execution_log.messages.append(f"Successfully retrieved {resource_type} pod request: {total_request:.6f}")
                return total_request

            execution_log.warnings.append(f"No request value configured for {resource_type} in workload")
            return None

        except subprocess.TimeoutExpired:
            execution_log.warnings.append(f"Timeout while querying {resource_type} via kubectl")
            return None
        except json.JSONDecodeError as e:
            execution_log.warnings.append(f"Failed to parse workload JSON for {resource_type}: {str(e)}")
            return None
        except Exception as e:
            execution_log.warnings.append(f"Failed to retrieve pod request for {resource_type}: {str(e)}")
            return None

    def _parse_cpu_value(self, cpu_str: str) -> Optional[float]:
        """解析 CPU 值（单位：cores）。"""
        try:
            if cpu_str.endswith('m'):
                return float(cpu_str[:-1]) / 1000
            return float(cpu_str)
        except Exception:
            return None

    def _parse_memory_value(self, memory_str: str) -> Optional[float]:
        """解析内存值（单位：MiB）。"""
        try:
            memory_str = memory_str.strip()
            if memory_str.endswith('Ki'):
                return float(memory_str[:-2]) / 1024
            elif memory_str.endswith('Mi'):
                return float(memory_str[:-2])
            elif memory_str.endswith('Gi'):
                return float(memory_str[:-2]) * 1024
            elif memory_str.endswith('Ti'):
                return float(memory_str[:-2]) * 1024 * 1024
            elif memory_str.endswith('K'):
                return float(memory_str[:-1]) / 1024
            elif memory_str.endswith('M'):
                return float(memory_str[:-1])
            elif memory_str.endswith('G'):
                return float(memory_str[:-1]) * 1024
            elif memory_str.endswith('T'):
                return float(memory_str[:-1]) * 1024 * 1024
            else:
                return float(memory_str) / (1024 * 1024)
        except Exception:
            return None

    def _calculate_std_dev(self, time_series: Dict[str, Any], scale_factor: int) -> float:
        """计算标准差（归一化）。"""
        samples = time_series.get("samples", [])
        if not samples:
            return 0.0

        sum_values = sum(sample.get("value") for sample in samples)
        mean = sum_values / len(samples)

        sum_squared_differences = sum((sample.get("value") - mean) ** 2 for sample in samples)
        variance = sum_squared_differences / len(samples)
        std_dev = math.sqrt(variance)

        log_value = math.log(1 + math.pow(10, -scale_factor) * std_dev)
        return log_value / (1 + log_value)

    def _calculate_volatility_coverage(self, time_series: Dict[str, Any], pod_request: float) -> float:
        """计算波动覆盖率：统计波动窗口占比。"""
        samples = time_series.get("samples", [])
        if not samples:
            return 0.0

        window_size = VOLATILITY_COVERAGE_WINDOW
        total_windows = 0
        volatility_windows = 0

        i = 0
        while i < len(samples):
            start = samples[i].get("timestamp")
            end = start + window_size

            max_value = float('-inf')
            min_value = float('inf')
            windowed = False

            while i < len(samples) and samples[i].get("timestamp") < end:
                if not windowed:
                    max_value = samples[i].get("value")
                    min_value = samples[i].get("value")
                    windowed = True
                else:
                    max_value = max(max_value, samples[i].get("value"))
                    min_value = min(min_value, samples[i].get("value"))
                i += 1

            if windowed:
                total_windows += 1
                if (max_value - min_value) > pod_request:
                    volatility_windows += 1

        return volatility_windows / total_windows if total_windows > 0 else 0.0

    def _calculate_amplitude(self, time_series: Dict[str, Any], pod_request: float) -> float:
        """计算振幅：检测滑动窗口间的显著波动。"""
        window_duration = AMPLITUDE_WINDOW_DURATION
        time_difference = AMPLITUDE_TIME_DIFFERENCE

        windows = self._create_sliding_windows(time_series, window_duration)
        window_count = len(windows)
        if window_count == 0:
            return 0.0

        for i in range(window_count):
            for j in range(i + 1, window_count):
                amplitude_condition = (
                    (windows[i].get("max_usage") - windows[j].get("min_usage")) > pod_request * AMPLITUDE_THRESHOLD_MULTIPLIER or
                    (windows[j].get("max_usage") - windows[i].get("min_usage")) > pod_request * AMPLITUDE_THRESHOLD_MULTIPLIER
                )
                time_difference_condition = int(
                    windows[j].get("start_timestamp") - windows[i].get("end_timestamp")
                ) > time_difference

                if amplitude_condition and time_difference_condition:
                    return 1.0

        return 0.0

    def _create_sliding_windows(self, time_series: Dict[str, Any], window_duration: float) -> List[Dict[str, Any]]:
        """创建滑动窗口。"""
        windows = []
        samples = time_series.get("samples", [])
        sample_count = len(samples)
        if sample_count == 0:
            return windows

        sample_end_timestamp = samples[-1].get("timestamp")
        start_index = 0

        while start_index < sample_count:
            end_timestamp = samples[start_index].get("timestamp") + window_duration
            if end_timestamp > sample_end_timestamp:
                break

            min_value = samples[start_index].get("value")
            max_value = samples[start_index].get("value")
            end_index = start_index

            for i in range(start_index, sample_count):
                if samples[i].get("timestamp") > end_timestamp:
                    break
                min_value = min(min_value, samples[i].get("value"))
                max_value = max(max_value, samples[i].get("value"))
                end_index = i

            windows.append({
                'start_timestamp': samples[start_index].get("timestamp"),
                'end_timestamp': samples[end_index].get("timestamp"),
                'min_usage': min_value,
                'max_usage': max_value
            })

            start_index += AMPLITUDE_WINDOW_STEP

        return windows
