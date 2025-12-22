"""ACK Cost Analysis Handler - Alibaba Cloud Container Service Cost Analysis."""

from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import subprocess
import json
import re
import math
import time
from datetime import datetime
from models import (
    WorkloadCostOutput,
    ErrorModel,
    ExecutionLog,
    enable_execution_log_ctx,
)


def _get_cs_client(ctx: Context, region: str):
    """从 lifespan providers 中获取指定区域的 CS 客户端。"""
    lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
    providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
    config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
    cs_client_factory = providers.get("cs_client_factory") if isinstance(providers, dict) else None
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region, config)


class ACKCostAnalysisHandler:
    """Handler for ACK cost analysis operations."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the ACK cost analysis handler.

        Args:
            server: FastMCP server instance
            settings: Configuration settings
        """
        self.settings = settings or {}
        
        # 是否可写变更配置
        self.allow_write = self.settings.get("allow_write", False)
        
        # Per-handler toggle
        self.enable_execution_log = self.settings.get("enable_execution_log", False)

        if server is None:
            return
        self.server = server

        self.server.tool(
            name="analyze_workload_cost",
            description="""分析特定工作负载的资源使用情况和成本优化建议。
            
## 使用场景
- 分析单个工作负载的资源配置和实时使用情况
- 评估资源利用率（实际使用 vs requests）
- 获取资源画像推荐配置（如果启用）

## 注意事项
- 利用率可能超过 100%，表示实际使用超过 request 配置
- resource_recommendation 为 null 表示未启用资源画像或没有推荐数据
"""
        )(self.analyze_workload_cost)
        
        logger.info("ACK Cost Analysis Handler initialized")

    async def analyze_workload_cost(
        self,
        ctx: Context,
        cluster_id: str = Field(..., description="集群 ID"),
        namespace: str = Field(..., description="命名空间名称"),
        workload_type: str = Field(..., description="工作负载类型"),
        workload_name: str = Field(..., description="工作负载名称"),
    ) -> WorkloadCostOutput:
        """
        分析工作负载成本明细

        分析步骤（workload 维度）：
        1. 根据瞬时水位，进行稳定性、效率分析：获取 kubectl top metric, 以及 request、limit 水位
        2. [Optional] 若开启了资源画像，通过资源画像结果 CR，获取推荐配置 Request 值

        Args:
            ctx: FastMCP context
            cluster_id: 集群 ID
            namespace: 命名空间
            workload_type: 工作负载类型
            workload_name: 工作负载名称

        Returns:
            WorkloadCostOutput: 工作负载成本分析结果
        """
        # Set per-request context from handler setting
        enable_execution_log_ctx.set(self.enable_execution_log)

        # Initialize execution log
        start_ms = int(time.time() * 1000)
        execution_log = ExecutionLog(
            tool_call_id=f"analyze_workload_cost_{cluster_id}_{namespace}_{workload_name}_{start_ms}",
            start_time=datetime.utcnow().isoformat() + "Z"
        )

        try:
            execution_log.messages.append(
                "Step 1: Analyzing stability and efficiency based on instant metrics (kubectl top + request/limit)"
            )
            instant_analysis = await self._analyze_instant_metrics(
                ctx, cluster_id, namespace, workload_type, workload_name, execution_log
            )

            execution_log.messages.append(
                "Step 2 [Optional]: Fetching resource recommendation from Recommendation CR"
            )
            recommendation = await self._get_resource_recommendation(
                ctx, cluster_id, namespace, workload_type, workload_name, execution_log
            )

            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms

            # 构建资源指标字典
            cpu_util = instant_analysis.get("resource_utilization", {}).get("cpu_utilization")
            memory_util = instant_analysis.get("resource_utilization", {}).get("memory_utilization")
            
            resource_metrics = {
                "cpu_usage": instant_analysis.get("instant_cpu_usage", "N/A"),
                "cpu_request": instant_analysis.get("cpu_request") or "未配置",
                "cpu_limit": instant_analysis.get("cpu_limit") or "未配置",
                "memory_usage": instant_analysis.get("instant_memory_usage", "N/A"),
                "memory_request": instant_analysis.get("memory_request") or "未配置",
                "memory_limit": instant_analysis.get("memory_limit") or "未配置",
                "cpu_utilization": f"{cpu_util * 100:.2f}%" if cpu_util is not None else "N/A",
                "memory_utilization": f"{memory_util * 100:.2f}%" if memory_util is not None else "N/A"
            }

            return WorkloadCostOutput(
                cluster_id=cluster_id,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
                resource_metrics=resource_metrics,
                resource_recommendation=recommendation,
                execution_log=execution_log
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze workload cost: {e}")
            execution_log.error = str(e)
            execution_log.end_time = datetime.utcnow().isoformat() + "Z"
            execution_log.duration_ms = int(time.time() * 1000) - start_ms
            execution_log.metadata = {
                "error_type": type(e).__name__,
                "failure_stage": "analyze_workload_cost"
            }
            
            return WorkloadCostOutput(
                cluster_id=cluster_id,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
                resource_metrics=None,
                error=ErrorModel(
                    error_code="AnalysisFailed",
                    error_message=str(e)
                ),
                execution_log=execution_log
            )

    # ==================== 各分析步骤的具体实现 ====================
    
    async def _analyze_instant_metrics(
        self,
        ctx: Context,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        execution_log: ExecutionLog
    ) -> Dict[str, Any]:
        """根据瞬时水位分析稳定性和效率：kubectl top + request/limit"""
        try:
            from kubectl_handler import get_context_manager
            
            # 设置 CS client
            cs_client = _get_cs_client(ctx, "CENTER")
            context_manager = get_context_manager()
            context_manager.set_cs_client(cs_client)
            
            # 获取 kubeconfig
            kubeconfig_path = context_manager.get_kubeconfig_path(
                cluster_id,
                self.settings.get("kubeconfig_mode"),
                self.settings.get("kubeconfig_path"),
                execution_log
            )
            
            # 获取 workload spec（request/limit）
            logger.debug(f"Fetching workload spec for {workload_type}/{workload_name}")
            cmd_spec = f"kubectl --kubeconfig {kubeconfig_path} get {workload_type} {workload_name} -n {namespace} -o json"
            result_spec = subprocess.run(cmd_spec, shell=True, capture_output=True, text=True, timeout=30)
            
            if result_spec.returncode != 0:
                raise ValueError(f"Failed to get workload spec: {result_spec.stderr}")
            
            try:
                workload = json.loads(result_spec.stdout)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON response from kubectl get {workload_type}: {e}")
            
            spec = workload.get("spec", {})
            pod_selector_labels = spec.get("selector", {}).get("matchLabels", {})
            
            # 获取所有容器的 request/limit
            containers = spec.get("template", {}).get("spec", {}).get("containers", [])
            if not containers:
                raise ValueError("No containers found in workload")
            
            # 计算单个 pod 的总 request/limit（所有容器的总和）
            total_cpu_request_per_pod = 0
            total_memory_request_per_pod = 0
            total_cpu_limit_per_pod = 0
            total_memory_limit_per_pod = 0
            
            for container in containers:
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                
                cpu_req = requests.get("cpu", "0")
                if cpu_req and cpu_req != "0":
                    total_cpu_request_per_pod += self._parse_cpu_to_cores(cpu_req)
                
                mem_req = requests.get("memory", "0")
                if mem_req and mem_req != "0":
                    total_memory_request_per_pod += self._parse_memory_to_mib(mem_req)
                
                cpu_lim = limits.get("cpu", "0")
                if cpu_lim and cpu_lim != "0":
                    total_cpu_limit_per_pod += self._parse_cpu_to_cores(cpu_lim)
                
                mem_lim = limits.get("memory", "0")
                if mem_lim and mem_lim != "0":
                    total_memory_limit_per_pod += self._parse_memory_to_mib(mem_lim)
            
            logger.debug(f"Workload spec: cpu_request_per_pod={total_cpu_request_per_pod} cores, memory_request_per_pod={total_memory_request_per_pod}MiB")
            
            # 获取 pods 列表
            logger.debug(f"Fetching pods for {workload_type}/{workload_name}")
            label_selector = ",".join([f"{k}={v}" for k, v in pod_selector_labels.items()]) if pod_selector_labels else ""
            
            if label_selector:
                cmd_pods = f"kubectl --kubeconfig {kubeconfig_path} get pods -n {namespace} -l '{label_selector}' -o json"
            else:
                # 如果没有 selector，通过 owner reference 查找
                cmd_pods = f"kubectl --kubeconfig {kubeconfig_path} get pods -n {namespace} -o json"
            
            result_pods = subprocess.run(cmd_pods, shell=True, capture_output=True, text=True, timeout=30)
            
            if result_pods.returncode != 0:
                logger.warning(f"Failed to get pods: {result_pods.stderr}")
                pod_list = []
            else:
                try:
                    pods_data = json.loads(result_pods.stdout)
                    pod_list = pods_data.get("items", [])
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON response from kubectl get pods: {e}")
                    pod_list = []
                
                # 如果没有 label selector，通过 owner reference 过滤
                if not label_selector and pod_list:
                    pod_list = [
                        pod for pod in pod_list
                        if any(
                            owner.get("name") == workload_name and owner.get("kind", "").lower() == workload_type.lower()
                            for owner in pod.get("metadata", {}).get("ownerReferences", [])
                        )
                    ]
            
            logger.debug(f"Found {len(pod_list)} pods")
            
            # 获取 kubectl top pods（瞬时使用量）
            instant_cpu_usage_total = 0
            instant_memory_usage_total = 0
            top_data_available = False
            
            if pod_list:
                logger.debug("Fetching kubectl top pods metrics (batch mode)")
                
                # 批量获取 top 数据
                if label_selector:
                    cmd_top = f"kubectl --kubeconfig {kubeconfig_path} top pods -n {namespace} -l '{label_selector}' --no-headers"
                else:
                    cmd_top = f"kubectl --kubeconfig {kubeconfig_path} top pods -n {namespace} --no-headers"
                
                result_top = subprocess.run(cmd_top, shell=True, capture_output=True, text=True, timeout=30)
                
                if result_top.returncode == 0 and result_top.stdout:
                    # 格式（无 header）：POD_NAME   CPU(cores)   MEMORY(bytes)
                    pod_names_set = {pod.get("metadata", {}).get("name", "") for pod in pod_list}
                    
                    for line in result_top.stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        
                        parts = line.split()
                        if len(parts) >= 3:
                            pod_name = parts[0]
                            cpu_str = parts[1]
                            memory_str = parts[2]
                            
                            # 只统计属于当前 workload 的 pod
                            if not label_selector and pod_name not in pod_names_set:
                                continue
                            
                            instant_cpu_usage_total += self._parse_cpu_to_cores(cpu_str)
                            instant_memory_usage_total += self._parse_memory_to_mib(memory_str)
                            
                            top_data_available = True
            
            # 计算平均值（单 pod 维度）
            pod_count = len(pod_list) if pod_list else 0
            avg_cpu_usage_per_pod = instant_cpu_usage_total / pod_count if pod_count > 0 else 0
            avg_memory_usage_per_pod = instant_memory_usage_total / pod_count if pod_count > 0 else 0
            
            # 格式化为字符串
            cpu_usage_str = f"{avg_cpu_usage_per_pod:.3f}" if avg_cpu_usage_per_pod > 0 else "0.000"
            memory_usage_str = f"{int(avg_memory_usage_per_pod)}Mi" if avg_memory_usage_per_pod > 0 else "0Mi"
            
            cpu_request_str = f"{total_cpu_request_per_pod:.3f}" if total_cpu_request_per_pod > 0 else None
            memory_request_str = f"{int(total_memory_request_per_pod)}Mi" if total_memory_request_per_pod > 0 else None
            cpu_limit_str = f"{total_cpu_limit_per_pod:.3f}" if total_cpu_limit_per_pod > 0 else None
            memory_limit_str = f"{int(total_memory_limit_per_pod)}Mi" if total_memory_limit_per_pod > 0 else None
            
            logger.debug(f"Per-pod metrics: CPU usage={cpu_usage_str}, Memory usage={memory_usage_str}, CPU request={cpu_request_str}, Memory request={memory_request_str}")
            
            # 计算资源利用率（利用率 = 实际使用量 / request 配置）
            resource_utilization = {}
            if total_cpu_request_per_pod > 0:
                resource_utilization["cpu_utilization"] = avg_cpu_usage_per_pod / total_cpu_request_per_pod
            else:
                resource_utilization["cpu_utilization"] = 0.0
                
            if total_memory_request_per_pod > 0:
                resource_utilization["memory_utilization"] = avg_memory_usage_per_pod / total_memory_request_per_pod
            else:
                resource_utilization["memory_utilization"] = 0.0
            
            logger.info(
                f"Analysis complete: "
                f"cpu_util={resource_utilization.get('cpu_utilization', 0):.2%}, "
                f"mem_util={resource_utilization.get('memory_utilization', 0):.2%}"
            )
            
            return {
                "cpu_request": cpu_request_str,
                "memory_request": memory_request_str,
                "cpu_limit": cpu_limit_str,
                "memory_limit": memory_limit_str,
                "instant_cpu_usage": cpu_usage_str,
                "instant_memory_usage": memory_usage_str,
                "resource_utilization": resource_utilization,
                "pod_count": pod_count,
                "top_data_available": top_data_available,
            }
        except Exception as e:
            logger.warning(f"Failed to analyze instant metrics, using defaults: {e}")
            return {
                "cpu_request": None,
                "memory_request": None,
                "cpu_limit": None,
                "memory_limit": None,
                "instant_cpu_usage": "N/A",
                "instant_memory_usage": "N/A",
                "resource_utilization": {},
                "pod_count": 0,
                "top_data_available": False,
            }
    
    async def _get_resource_recommendation(
        self,
        ctx: Context,
        cluster_id: str,
        namespace: str,
        workload_type: str,
        workload_name: str,
        execution_log: ExecutionLog
    ) -> Optional[Dict[str, Any]]:
        """获取资源画像推荐配置"""
        try:
            from kubectl_handler import get_context_manager
            
            # 设置 CS client
            cs_client = _get_cs_client(ctx, "CENTER")
            context_manager = get_context_manager()
            context_manager.set_cs_client(cs_client)
            
            # 获取 kubeconfig
            kubeconfig_path = context_manager.get_kubeconfig_path(
                cluster_id,
                self.settings.get("kubeconfig_mode"),
                self.settings.get("kubeconfig_path"),
                execution_log
            )
            
            # 构建 label selector（workload kind 使用驼峰命名）
            workload_kind_map = {
                "deployment": "Deployment",
                "statefulset": "StatefulSet",
                "daemonset": "DaemonSet"
            }
            workload_kind = workload_kind_map.get(workload_type.lower(), workload_type.capitalize())
            
            label_selector = (
                f"alpha.alibabacloud.com/recommendation-workload-namespace={namespace},"
                f"alpha.alibabacloud.com/recommendation-workload-name={workload_name},"
                f"alpha.alibabacloud.com/recommendation-workload-kind={workload_kind}"
            )
            
            cmd = f"kubectl --kubeconfig {kubeconfig_path} get recommendation -n {namespace} -l '{label_selector}' -o json"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0 or not result.stdout:
                return None
            
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.debug(f"Invalid JSON response from kubectl get recommendation: {e}")
                return None
            
            items = data.get("items", [])
            
            if not items:
                return None
            
            rec = items[0]
            status = rec.get("status", {})
            if not status.get("recommendResources"):
                return None
            
            recommend_resources = status["recommendResources"]
            container_recs = recommend_resources.get("containerRecommendations", [])
            
            if not container_recs:
                return None
            
            # 提取所有容器的推荐值
            containers = []
            
            for container_rec in container_recs:
                target = container_rec.get("target", {})
                container_name = container_rec.get("containerName", "")
                
                cpu_target = target.get("cpu", "")
                memory_target = target.get("memory", "")
                
                # 计算推荐配置（画像值 × 1.3 倍安全冗余后规整）
                cpu_recommended = self._calculate_recommended_cpu(cpu_target, 1.3)
                memory_recommended = self._calculate_recommended_memory(memory_target, 1.3)
                
                containers.append({
                    "container_name": container_name,
                    "cpu_recommended": cpu_recommended,
                    "memory_recommended": memory_recommended
                })
            
            return {
                "containers": containers,
                "resource_recommendation_status": rec.get("metadata", {}).get("labels", {}).get("alpha.alibabacloud.com/recommendation-status", "")
            }
        except Exception as e:
            logger.debug(f"No resource recommendation found: {e}")
            return None

    def _parse_cpu_to_cores(self, cpu_str: str) -> float:
        """将 CPU 资源转换为 cores 单位
        
        Examples:
            "100m" -> 0.1
            "2" -> 2.0
            "1500m" -> 1.5
        """
        if not cpu_str:
            return 0.0
        
        cpu_str = cpu_str.strip()
        if cpu_str.endswith('m'):
            return float(cpu_str[:-1]) / 1000  # millicores -> cores
        else:
            return float(cpu_str)
    
    def _parse_memory_to_mib(self, mem_str: str) -> float:
        """将内存资源转换为 MiB 单位
        
        Examples:
            "256Mi" -> 256.0
            "1Gi" -> 1024.0
            "512Ki" -> 0.5
            "1G" -> 953.67
        """
        if not mem_str:
            return 0.0
        
        mem_str = mem_str.strip()
        match = re.match(r'^([0-9.]+)([KMGTPE]i?)?$', mem_str, re.IGNORECASE)
        if not match:
            return 0.0
        
        value = float(match.group(1))
        unit = match.group(2) or "Mi"
        
        # 二进制单位（IEC）
        if unit == "Ki":
            return value / 1024
        elif unit == "Mi":
            return value
        elif unit == "Gi":
            return value * 1024
        elif unit == "Ti":
            return value * 1024 * 1024
        elif unit == "Pi":
            return value * 1024 * 1024 * 1024
        elif unit == "Ei":
            return value * 1024 * 1024 * 1024 * 1024
        # 十进制单位（SI）
        elif unit == "K":
            return value * 1000 / 1024 / 1024
        elif unit == "M":
            return value * 1000 * 1000 / 1024 / 1024
        elif unit == "G":
            return value * 1000 * 1000 * 1000 / 1024 / 1024
        elif unit == "T":
            return value * 1000 * 1000 * 1000 * 1000 / 1024 / 1024
        elif unit == "P":
            return value * 1000 * 1000 * 1000 * 1000 * 1000 / 1024 / 1024
        elif unit == "E":
            return value * 1000 * 1000 * 1000 * 1000 * 1000 * 1000 / 1024 / 1024
        else:
            return value
    
    def _format_cpu_value(self, cores: float) -> str:
        """向上规整到 0.01 cores
        
        Examples:
            0.121 -> "0.130"
            0.005 -> "0.010"
        """
        cores = math.ceil(cores / 0.01) * 0.01
        return f"{cores:.3f}"
    
    def _format_memory_value(self, mib: float) -> str:
        """向上规整到 10Mi
        
        Examples:
            256.5 -> "260Mi"
            332.8 -> "340Mi"
        """
        mib = math.ceil(mib / 10) * 10
        return f"{int(mib)}Mi"
    
    def _calculate_recommended_cpu(self, cpu_str: str, multiplier: float) -> str:
        """计算 CPU 推荐配置值（画像值 × 安全冗余系数后规整）"""
        if not cpu_str:
            return ""
        
        try:
            cores = self._parse_cpu_to_cores(cpu_str)
            recommended_cores = cores * multiplier
            return self._format_cpu_value(recommended_cores)
        except Exception:
            return cpu_str
    
    def _calculate_recommended_memory(self, mem_str: str, multiplier: float) -> str:
        """计算 Memory 推荐配置值（画像值 × 安全冗余系数后规整）"""
        if not mem_str:
            return ""
        
        try:
            mib = self._parse_memory_to_mib(mem_str)
            recommended_mib = mib * multiplier
            return self._format_memory_value(recommended_mib)
        except Exception:
            return mem_str
