from typing import Dict, Any, Optional, List
import subprocess
import shlex
import tempfile
import os
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
from cachetools import LRUCache

# 导入模型
try:
    from .models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel, GetClusterKubeConfigOutput
except ImportError:
    from models import KubectlOutput, KubectlErrorCodes, ErrorModel, GetClusterKubeConfigOutput


class KubeconfigCache(LRUCache):
    """自定义 LRUCache，用于清理 kubeconfig 临时文件"""

    def popitem(self):
        """重写 popitem 方法，在驱逐缓存项时清理临时文件"""
        key, path = super().popitem()
        # 删除临时文件
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"Removed cached kubeconfig file: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove cached kubeconfig file {path}: {e}")
        return key, path


class KubectlHandler:
    """Handler for running kubectl commands via a FastMCP tool."""

    # kubeconfig 缓存最大大小
    _KUBECONFIG_CACHE_MAX_SIZE = 5

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the kubectl handler.

        Args:
            server: FastMCP server instance
            settings: Configuration settings
        """
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)
        # 使用自定义的 KubeconfigCache 作为 kubeconfig 缓存
        self._kubeconfig_cache = KubeconfigCache(maxsize=self._KUBECONFIG_CACHE_MAX_SIZE)

        self.server.tool(
            name="ack_kubectl",
            description="""Executes a kubectl command against the ACK Kubernetes cluster. Use this tool only when you need to query or modify the state of the ACK Kubernetes cluster.
            
IMPORTANT: Interactive commands are not supported in this environment. This includes:
- kubectl exec with -it flag (use non-interactive exec instead)
- kubectl edit (use kubectl get -o yaml, kubectl patch, or kubectl apply instead)
- kubectl port-forward (use alternative methods like NodePort or LoadBalancer)

For interactive operations, please use these non-interactive alternatives:
- Instead of 'kubectl edit', use 'kubectl get -o yaml' to view, 'kubectl patch' for targeted changes, or 'kubectl apply' to apply full changes
- Instead of 'kubectl exec -it', use 'kubectl exec' with a specific command
- Instead of 'kubectl port-forward', use service types like NodePort or LoadBalancer
            """
        )(self.ack_kubectl)

        # self.server.tool(
        #     name="get_cluster_kubeconfig",
        #     description="Get the KUBECONFIG file path for an ACK cluster. Set it via the KUBECONFIG environment variable or the --kubeconfig flag, then run kubectl commands."
        # )(self.get_cluster_kubeconfig)

        logger.info("Kubectl Handler initialized")

    def _get_sls_client(self, ctx: Context):
        """获取 SLS 客户端工厂"""
        try:
            lifespan_context = ctx.request_context.lifespan_context
            if isinstance(lifespan_context, dict):
                providers = lifespan_context.get("providers", {})
            else:
                providers = getattr(lifespan_context, "providers", {})

            sls_client_factory = providers.get("sls_client_factory")
            if not sls_client_factory:
                raise ValueError("sls_client_factory not available")
            return sls_client_factory
        except Exception as e:
            logger.error(f"Failed to get SLS client factory: {e}")
            raise

    def _get_cs_client(self, ctx: Context, region_id: str):
        """获取 CS 客户端"""
        try:
            lifespan_context = ctx.request_context.lifespan_context
            if isinstance(lifespan_context, dict):
                providers = lifespan_context.get("providers", {})
            else:
                providers = getattr(lifespan_context, "providers", {})

            cs_client_factory = providers.get("cs_client_factory")
            if not cs_client_factory:
                raise ValueError("cs_client_factory not available")
            return cs_client_factory(region_id)
        except Exception as e:
            logger.error(f"Failed to get CS client: {e}")
            raise

    def _get_kubeconfig_from_ack(self, ctx: Context, cluster_id: str, region_id: str) -> Optional[str]:
        """通过 ACK API 获取 kubeconfig 配置"""
        try:
            # 获取 CS 客户端
            cs_client = self._get_cs_client(ctx, region_id)

            # 调用 DescribeClusterUserKubeconfig API
            from alibabacloud_cs20151215 import models as cs_models

            request = cs_models.DescribeClusterUserKubeconfigRequest(
                private_ip_address=False  # 获取公网连接配置
            )

            response = cs_client.describe_cluster_user_kubeconfig(cluster_id, request)

            if response and response.body and response.body.config:
                logger.info(f"Successfully fetched kubeconfig for cluster {cluster_id}")
                return response.body.config
            else:
                logger.warning(f"No kubeconfig found for cluster {cluster_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch kubeconfig for cluster {cluster_id}: {e}")
            return None

    def _get_kubeconfig_path(self, ctx: Context, cluster_id: str ) -> Optional[str]:
        # 从上下文中获取 region_id
        lifespan_context = ctx.request_context.lifespan_context
        if isinstance(lifespan_context, dict):
            region_id = lifespan_context.get("config", {}).get("region_id", "cn-hangzhou")
        else:
            region_id = getattr(lifespan_context, "config", {}).get("region_id", "cn-hangzhou")

        # 检查缓存中是否已有 kubeconfig 路径
        cache_key = f"{cluster_id}:{region_id}"
        cached_path = self._kubeconfig_cache.get(cache_key)
        # 检查文件是否存在
        if cached_path and os.path.exists(cached_path):
            logger.debug(f"Using cached kubeconfig for cluster {cluster_id}")
            return cached_path
        else:
            # 文件不存在，从缓存中移除
            self._kubeconfig_cache.pop(cache_key, None)

        # 获取 kubeconfig
        kubeconfig_content = self._get_kubeconfig_from_ack(ctx, cluster_id, region_id)

        if kubeconfig_content:
            # 创建临时文件存储 kubeconfig
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(kubeconfig_content)
                kubeconfig_path = f.name
                # 缓存 kubeconfig 路径
                self._kubeconfig_cache[cache_key] = kubeconfig_path
                logger.debug(f"Cached kubeconfig for cluster {cluster_id}")
                return kubeconfig_path
        return None

    def run_command(self, cmd: List[str], kubeconfig_path: Optional[str] = None) -> Dict[str, Any]:
        """Run a kubectl command and return structured result."""
        try:
            # 如果有 kubeconfig 路径，设置 KUBECONFIG 环境变量
            env = os.environ.copy()
            if kubeconfig_path:
                env["KUBECONFIG"] = kubeconfig_path
                logger.debug(f"Using kubeconfig: {kubeconfig_path}")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip() if result.stderr else None,
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"kubectl failed: {' '.join(cmd)}")
            return {
                "exit_code": e.returncode,
                "stdout": e.stdout.strip() if e.stdout else None,
                "stderr": e.stderr.strip() if e.stderr else str(e),
            }

    async def ack_kubectl(
            self,
            ctx: Context,
            command: str = Field(
                ..., description="""
The complete kubectl command to execute. Prefer to use heredoc syntax for multi-line commands. Please include the kubectl prefix as well.

IMPORTANT: Do not use interactive commands. Instead:
- Use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply' instead of 'kubectl edit'
- Use 'kubectl exec' with specific commands instead of 'kubectl exec -it'
- Use service types like NodePort or LoadBalancer instead of 'kubectl port-forward'

Examples:
user: what pods are running in the cluster?
assistant: kubectl get pods

user: what is the status of the pod my-pod?
assistant: kubectl get pod my-pod -o jsonpath='{.status.phase}'

user: I need to edit the pod configuration
assistant: # Option 1: Using patch for targeted changes
kubectl patch pod my-pod --patch '{"spec":{"containers":[{"name":"main","image":"new-image"}]}}'

# Option 2: Using get and apply for full changes
kubectl get pod my-pod -o yaml > pod.yaml
# Edit pod.yaml locally
kubectl apply -f pod.yaml

user: I need to execute a command in the pod
assistant: kubectl exec my-pod -- /bin/sh -c "your command here"
                """
            ),
            cluster_id: Optional[str] = Field(
                None, description="Optional cluster ID to fetch kubeconfig from ACK API"
            ),
    ) -> KubectlOutput:
        kubeconfig_source = "local"
        kubeconfig_path = None

        try:
            # 如果提供了 cluster_id，尝试从 ACK API 获取 kubeconfig
            if cluster_id:
                kubeconfig_path = self._get_kubeconfig_path(ctx, cluster_id)

                if kubeconfig_path:
                    kubeconfig_source = "ack_api"
                    logger.info(f"Using ACK API kubeconfig for cluster {cluster_id}")
                else:
                    # 如果获取不到 kubeconfig，返回错误
                    error_msg = f"Failed to fetch kubeconfig for cluster {cluster_id}"
                    logger.error(error_msg)
                    return KubectlOutput(
                        status="error",
                        exit_code=1,
                        error=error_msg,
                        kubeconfig_source="ack_api"
                    )

            # 执行 kubectl 命令
            args = shlex.split(command)
            result = self.run_command(args, kubeconfig_path)

            status = "success" if result.get("exit_code") == 0 else "error"

            return KubectlOutput(
                status=status,
                exit_code=result.get("exit_code", 1),
                stdout=result.get("stdout"),
                stderr=result.get("stderr"),
                kubeconfig_source=kubeconfig_source
            )

        except Exception as e:
            logger.exception("kubectl tool execution error")
            return KubectlOutput(
                status="error",
                exit_code=1,
                error=str(e),
                kubeconfig_source=kubeconfig_source
            )

    async def get_cluster_kubeconfig(
            self,
            ctx: Context,
            cluster_id: Optional[str] = Field(
                None, description="cluster ID of an ACK cluster to fetch kubeconfig "
            ),
    ) -> GetClusterKubeConfigOutput:
        kubeconfig_path = None
        try:
            # 如果提供了 cluster_id，尝试从 ACK API 获取 kubeconfig
            if cluster_id:
                kubeconfig_path = self._get_kubeconfig_path(ctx, cluster_id)

                if kubeconfig_path:
                    logger.info(f"Using ACK API kubeconfig for cluster {cluster_id}")
                else:
                    # 如果获取不到 kubeconfig，返回错误
                    error_msg = f"Failed to fetch kubeconfig for cluster {cluster_id}"
                    logger.error(error_msg)
                    return GetClusterKubeConfigOutput(
                        error=ErrorModel(
                            error_code="FETCH_KUBECONFIG_FAILED",
                            error_message=error_msg
                        )
                    )

            return GetClusterKubeConfigOutput(
                kubeconfig=kubeconfig_path
            )
        except Exception as e:
            logger.exception("get_cluster_kubeconfig toll execution error")
            return GetClusterKubeConfigOutput(
                error=ErrorModel(
                    error_code="FETCH_KUBECONFIG_FAILED",
                    error_message=error_msg
                )
            )
