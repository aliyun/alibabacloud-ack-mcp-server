import os
import re
import shlex
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, Optional

from cachetools import TTLCache
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field

from ack_cluster_handler import parse_master_url
from models import KubectlOutput, ExecutionLog, enable_execution_log_ctx

_K8S_NAME_RE = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$')
_SHELL_METACHARS = frozenset(';&|`$\\\n<>(){}[]\'"!*?#~')
_READONLY_COMMANDS = frozenset({
    "api-resources", "api-versions", "cluster-info", "describe",
    "diff", "events", "explain", "get", "kustomize", "logs",
    "options", "top", "version",
})
_FORBIDDEN_KUBECTL_FLAGS = frozenset({
    '--kubeconfig', '--server', '--token', '--client-certificate', '--client-key',
    '--as', '--as-group', '--user', '--cluster', '--context',
    '--insecure-skip-tls-verify', '--raw',
})
_INTERACTIVE_FLAGS = frozenset({'-i', '-t', '--stdin', '--tty'})
_WORKLOAD_TYPES = frozenset({'deployment', 'statefulset', 'daemonset', 'replicaset'})
_FORBIDDEN_FLAGS_NORMALIZED = frozenset(f.lstrip('-') for f in _FORBIDDEN_KUBECTL_FLAGS)


def validate_kubernetes_name(name: str, context: str = "resource") -> str:
    if not name or not _K8S_NAME_RE.match(name):
        raise ValueError(f"Invalid {context} name: {name}")
    return name


def validate_shell_safe_param(value: str, context: str = "parameter") -> str:
    if not value:
        raise ValueError(f"Empty {context}")
    if any(c in _SHELL_METACHARS for c in value):
        raise ValueError(f"Unsafe characters in {context}: {value}")
    return value


def validate_kubeconfig_path(path: str) -> str:
    if not path:
        raise ValueError("Empty kubeconfig path")
    if any(c in _SHELL_METACHARS for c in path):
        raise ValueError(f"Unsafe characters in kubeconfig path: {path}")
    if '..' in os.path.normpath(path).split(os.sep):
        raise ValueError(f"Path traversal detected in kubeconfig path: {path}")
    return os.path.abspath(os.path.expanduser(path))


def validate_workload_type(workload_type: str) -> str:
    normalized = workload_type.lower()
    if normalized not in _WORKLOAD_TYPES:
        raise ValueError(f"Invalid workload type: {workload_type}. Must be one of: {', '.join(sorted(_WORKLOAD_TYPES))}")
    return normalized


def _is_forbidden_flag(token: str) -> bool:
    if not token.startswith('-'):
        return False
    normalized = token.lstrip('-').split('=', 1)[0]
    return normalized in _FORBIDDEN_FLAGS_NORMALIZED


def _is_interactive_flag(token: str) -> bool:
    if token in _INTERACTIVE_FLAGS:
        return True
    if token.startswith('-') and not token.startswith('--') and 'i' in token and 't' in token:
        return True
    return False


class KubectlRunner:
    def __init__(self, kubeconfig_path: str, timeout: int = 30, allow_write: bool = False):
        self._env = {**os.environ, "KUBECONFIG": kubeconfig_path}
        self._timeout = timeout
        self._allow_write = allow_write

    def run(self, *args: str) -> dict[str, Any]:
        tokens = list(args)
        error = self._check_security(tokens)
        if error:
            return {"exit_code": 1, "stdout": "", "stderr": error}
        try:
            result = subprocess.run(["kubectl"] + tokens, shell=False,
                                    capture_output=True, text=True,
                                    timeout=self._timeout, env=self._env)
            return {"exit_code": result.returncode,
                    "stdout": result.stdout.strip() if result.stdout else "",
                    "stderr": result.stderr.strip() if result.stderr else ""}
        except subprocess.TimeoutExpired:
            return {"exit_code": 124, "stdout": "", "stderr": f"timed out after {self._timeout}s"}
        except FileNotFoundError:
            return {"exit_code": 127, "stdout": "", "stderr": "kubectl not installed"}

    def _check_security(self, tokens: list[str]) -> str | None:
        return (self._check_forbidden_flags(tokens)
                or self._check_interactive(tokens)
                or (not self._allow_write and self._check_write(tokens)))

    def _check_forbidden_flags(self, tokens: list[str]) -> str | None:
        found = [t for t in tokens if _is_forbidden_flag(t)]
        if found:
            return f"Forbidden flag(s) not allowed: {', '.join(found)}"
        return None

    def _check_interactive(self, tokens: list[str]) -> str | None:
        if not tokens:
            return None
        if tokens[0] == "port-forward":
            return "interactive mode not supported for kubectl port-forward, please use service types like NodePort or LoadBalancer"
        if tokens[0] == "edit":
            return "interactive mode not supported for kubectl edit, please use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply'"
        if any(_is_interactive_flag(t) for t in tokens):
            return "interactive mode not supported (commands with -it/-i/-t/--stdin/--tty flags), please use non-interactive commands"
        return None

    def _check_write(self, tokens: list[str]) -> str | None:
        if not tokens:
            return "Empty command not allowed"
        if tokens[0] not in _READONLY_COMMANDS:
            return f"Write command '{tokens[0]}' not allowed in read-only mode. Only read-only commands are permitted: {', '.join(sorted(_READONLY_COMMANDS))}"
        return None


_CLUSTER_ID_PATTERN = re.compile(r"^c[a-z0-9]{32}$")

class KubectlContextManager(TTLCache):
    """基于 TTL+LRU 缓存的 kubeconfig 文件管理器"""

    def __init__(self, ttl_minutes: int = 60):
        """初始化上下文管理器

        Args:
            ttl_minutes: kubeconfig有效期（分钟），默认60分钟
        """
        # 初始化 TTL+LRU 缓存
        super().__init__(maxsize=50, ttl=ttl_minutes * 60)  # TTL 以秒为单位，提前5min

        self._cs_client = None  # CS客户端实例
        self.do_not_cleanup_file = None  # 本地kubeconfig文件路径，不需要清理

        self._kube_dir = tempfile.mkdtemp(prefix="mcp-kubeconfig-")

        self._setup_cleanup_handlers()

    def _setup_cleanup_handlers(self):
        """设置清理处理器"""
        import atexit
        import signal

        def cleanup_contexts():
            """清理所有上下文"""
            try:
                context_manager = get_context_manager()
                if context_manager:
                    context_manager.cleanup()
                else:
                    self.cleanup_all_mcp_files()
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                raise e

        def signal_handler(signum, frame):
            """信号处理器"""
            cleanup_contexts()
            exit(0)

        atexit.register(cleanup_contexts)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def cleanup_all_mcp_files(self):
        """类方法：清理所有MCP创建的kubeconfig文件（安全清理）"""
        try:
            kube_dir = os.path.expanduser("~/.kube")
            if not os.path.exists(kube_dir):
                return

            removed_count = 0
            for filename in os.listdir(kube_dir):
                if filename.startswith("mcp-kubeconfig-") and filename.endswith(".yaml"):
                    file_path = os.path.join(kube_dir, filename)
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except Exception:
                        pass

            if removed_count > 0:
                print(f"Cleaned up {removed_count} MCP kubeconfig files")
        except Exception:
            pass

    def _get_or_create_kubeconfig_file(self, cluster_id: str, kubeconfig_mode: str, kubeconfig_path: str, execution_log: ExecutionLog) -> str:
        """获取或创建集群的 kubeconfig 文件

        Args:
            cluster_id: 集群ID
            kubeconfig_mode: 获取kubeconfig的模式，支持 "ACK_PUBLIC", "ACK_PRIVATE", "LOCAL"
            kubeconfig_path: 本地kubeconfig文件路径（仅在模式为LOCAL时使用）
            execution_log: 执行日志
            
        Returns:
            kubeconfig 文件路径
        """
        # 检查缓存中是否已存在
        if cluster_id in self:
            logger.debug(f"Found cached kubeconfig for cluster {cluster_id}")
            execution_log.api_calls.append({
                "api": "GetKubeconfig",
                "source": "cache",
                "cluster_id": cluster_id,
                "status": "success"
            })
            return self[cluster_id]

        if kubeconfig_mode == "INCLUSTER":
            # 使用集群内配置
            logger.debug(f"Using in-cluster kubeconfig for cluster {cluster_id}")
            kubeconfig_path = self._construct_incluster_kubeconfig()
            execution_log.api_calls.append({
                "api": "GetKubeconfig",
                "source": "incluster",
                "cluster_id": cluster_id,
                "status": "success"
            })
            self[cluster_id] = kubeconfig_path
            return kubeconfig_path

        if kubeconfig_mode == "LOCAL":
            # 使用本地 kubeconfig 文件
            # 检查路径是否为空
            if not kubeconfig_path:
                raise ValueError(f"Local kubeconfig path is not set")
            kubeconfig_path = os.path.abspath(os.path.expanduser(kubeconfig_path))
            if not os.path.exists(kubeconfig_path):
                raise ValueError(f"File {kubeconfig_path} does not exist")
            self.do_not_cleanup_file = kubeconfig_path
            logger.debug(f"Using local kubeconfig for cluster {cluster_id} from {kubeconfig_path}")
            execution_log.api_calls.append({
                "api": "GetKubeconfig",
                "source": "local_file",
                "cluster_id": cluster_id,
                "path": kubeconfig_path,
                "status": "success"
            })
            self[cluster_id] = kubeconfig_path
            return kubeconfig_path

        # 从 ACK 获取 kubeconfig
        private_ip_address = kubeconfig_mode == "ACK_PRIVATE"

        # 创建新的 kubeconfig 文件
        kubeconfig_content = self._get_kubeconfig_from_ack(cluster_id, private_ip_address, int(self.ttl / 60), execution_log)  # 转换为分钟
        if not kubeconfig_content:
            raise ValueError(f"Failed to get kubeconfig for cluster {cluster_id}")

        # 创建 kubeconfig 文件
        kubeconfig_path = os.path.join(self._kube_dir, f"mcp-kubeconfig-{cluster_id}.yaml")

        # 确保目录存在
        os.makedirs(os.path.dirname(kubeconfig_path), exist_ok=True)

        fd = os.open(kubeconfig_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(kubeconfig_content)

        # 添加到缓存
        self[cluster_id] = kubeconfig_path
        return kubeconfig_path

    def popitem(self):
        """重写 popitem 方法，在驱逐缓存项时清理 kubeconfig 文件"""
        key, path = super().popitem()
        # 删除 kubeconfig 文件
        if path and os.path.exists(path):
            if self.do_not_cleanup_file and os.path.samefile(path, self.do_not_cleanup_file):
                logger.debug(f"Skipped removal of protected kubeconfig file: {path}")
                return key, path
            try:
                os.remove(path)
                logger.debug(f"Removed cached kubeconfig file: {path}")
            except Exception as e:
                logger.warning(f"Failed to remove cached kubeconfig file {path}: {e}")

        return key, path

    def cleanup(self):
        """清理资源，删除所有 MCP 创建的 kubeconfig 文件和缓存"""
        removed_count = 0
        for key, path in list(self.items()):
            if path and os.path.exists(path):
                # 只有当do_not_cleanup_file存在且路径不同时才清理
                if self.do_not_cleanup_file and os.path.samefile(path, self.do_not_cleanup_file):
                    continue
                try:
                    os.remove(path)
                    removed_count += 1
                except Exception:
                    pass
        self.clear()
        print(f"Cleaned up {removed_count} kubeconfig files")

    def set_cs_client(self, cs_client):
        """设置CS客户端

        Args:
            cs_client: CS客户端实例
        """
        self._cs_client = cs_client

    def _get_cs_client(self):
        """获取CS客户端"""
        if not self._cs_client:
            raise ValueError("CS client not set")
        return self._cs_client

    def _get_kubeconfig_from_ack(self, cluster_id: str, private_ip_address: bool = False, ttl_minutes: int = 60, execution_log: ExecutionLog = None) -> Optional[str]:
        """通过ACK API获取kubeconfig配置

        Args:
            cluster_id: 集群ID
            private_ip_address: 是否获取内网连接配置
            ttl_minutes: kubeconfig有效期（分钟），默认60分钟
            execution_log: 执行日志
        """
        try:
            # 获取CS客户端
            cs_client = self._get_cs_client()
            from alibabacloud_cs20151215 import models as cs_models

            # 先检查集群详情，确认是否有公网端点
            api_start = int(time.time() * 1000)
            detail_response = cs_client.describe_cluster_detail(cluster_id)
            api_duration = int(time.time() * 1000) - api_start
            
            # Extract request_id
            request_id = None
            if hasattr(detail_response, 'headers') and detail_response.headers:
                request_id = detail_response.headers.get('x-acs-request-id', 'N/A')

            if not detail_response or not detail_response.body:
                if execution_log:
                    execution_log.api_calls.append({
                        "api": "DescribeClusterDetail",
                        "cluster_id": cluster_id,
                        "request_id": request_id,
                        "duration_ms": api_duration,
                        "status": "failed",
                        "error": "No response body"
                    })
                raise ValueError(f"Failed to get cluster details for {cluster_id}")

            cluster_info = detail_response.body
            # 检查是否有公网API Server端点
            master_url_str = getattr(cluster_info, 'master_url', '')
            master_url = parse_master_url(master_url_str)
            if private_ip_address:
                if not master_url["intranet_api_server_endpoint"]:
                    if execution_log:
                        execution_log.api_calls.append({
                            "api": "DescribeClusterDetail",
                            "cluster_id": cluster_id,
                            "request_id": request_id,
                            "duration_ms": api_duration,
                            "status": "failed",
                            "error": "No intranet endpoint"
                        })
                    raise ValueError(
                        f"Cluster {cluster_id} does not have intranet endpoint access, "
                        f"Please enable intranet endpoint access setting first."
                    )
            else:
                if not master_url["api_server_endpoint"]:
                    if execution_log:
                        execution_log.api_calls.append({
                            "api": "DescribeClusterDetail",
                            "cluster_id": cluster_id,
                            "request_id": request_id,
                            "duration_ms": api_duration,
                            "status": "failed",
                            "error": "No public endpoint"
                        })
                    raise ValueError(
                        f"Cluster {cluster_id} does not have public endpoint access, "
                        f"Please enable public endpoint access setting first."
                    )
            
            # Log successful cluster detail check
            if execution_log:
                execution_log.api_calls.append({
                    "api": "DescribeClusterDetail",
                    "cluster_id": cluster_id,
                    "request_id": request_id,
                    "duration_ms": api_duration,
                    "status": "success"
                })

            # 调用DescribeClusterUserKubeconfig API
            request = cs_models.DescribeClusterUserKubeconfigRequest(
                private_ip_address=private_ip_address,
                temporary_duration_minutes=ttl_minutes,  # 使用传入的TTL
            )

            api_start = int(time.time() * 1000)
            response = cs_client.describe_cluster_user_kubeconfig(cluster_id, request)
            api_duration = int(time.time() * 1000) - api_start
            
            # Extract request_id
            request_id = None
            if hasattr(response, 'headers') and response.headers:
                request_id = response.headers.get('x-acs-request-id', 'N/A')

            if response and response.body and response.body.config:
                logger.info(f"Successfully fetched kubeconfig for cluster {cluster_id} (TTL: {ttl_minutes} minutes)")
                if execution_log:
                    execution_log.api_calls.append({
                        "api": "DescribeClusterUserKubeconfig",
                        "cluster_id": cluster_id,
                        "request_id": request_id,
                        "duration_ms": api_duration,
                        "status": "success",
                        "mode": "private" if private_ip_address else "public",
                        "ttl_minutes": ttl_minutes
                    })
                return response.body.config
            else:
                logger.warning(f"No kubeconfig found for cluster {cluster_id}")
                if execution_log:
                    execution_log.api_calls.append({
                        "api": "DescribeClusterUserKubeconfig",
                        "cluster_id": cluster_id,
                        "request_id": request_id,
                        "duration_ms": api_duration,
                        "status": "failed",
                        "error": "No kubeconfig in response"
                    })
                return None

        except Exception as e:
            logger.error(f"Failed to fetch kubeconfig for cluster {cluster_id}: {e}")
            raise e

    def _construct_incluster_kubeconfig(self) -> str:
        """构造集群内 kubeconfig 文件路径
        
        Returns:
            kubeconfig 文件路径
        """
        tokenFile = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        rootCAFile = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        host, port = os.getenv("KUBERNETES_SERVICE_HOST"), os.getenv("KUBERNETES_SERVICE_PORT")
        if not host or not port:
            raise ValueError("unable to load in-cluster configuration, KUBERNETES_SERVICE_HOST and KUBERNETES_SERVICE_PORT must be defined")
        
        kubeconfig_path = os.path.join(self._kube_dir, "config.incluster")
        fd = os.open(kubeconfig_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority: {rootCAFile}
    server: https://{host}:{port}
  name: in-cluster
contexts:
- context:
    cluster: in-cluster
    user: in-cluster
  name: in-cluster
current-context: in-cluster
kind: Config
users:
- name: in-cluster
  user:
    tokenFile: {tokenFile}
""")
        return kubeconfig_path

    def get_kubeconfig_path(self, cluster_id: str, kubeconfig_mode: str, kubeconfig_path: str, execution_log: ExecutionLog) -> str:
        """获取集群的 kubeconfig 文件路径

        Args:
            cluster_id: 集群ID
            kubeconfig_mode: 获取kubeconfig的模式，支持 "ACK_PUBLIC", "ACK_PRIVATE", "LOCAL"
            kubeconfig_path: 本地kubeconfig文件路径（仅在模式为LOCAL时使用）
            execution_log: 执行日志
            
        Returns:
            kubeconfig 文件路径
        """
        return self._get_or_create_kubeconfig_file(cluster_id, kubeconfig_mode, kubeconfig_path, execution_log)


# 全局上下文管理器实例
_context_manager: Optional[KubectlContextManager] = None


def get_context_manager(ttl_minutes: int = 60) -> KubectlContextManager:
    """获取全局上下文管理器实例

    Args:
        ttl_minutes: kubeconfig有效期（分钟），默认60分钟
    """
    global _context_manager
    if _context_manager is None:
        _context_manager = KubectlContextManager(ttl_minutes=ttl_minutes)
    return _context_manager


class KubectlHandler:
    """
        Handler for running kubectl commands via a FastMCP tool.

        Design:
            kubeconfig management policy: https://github.com/aliyun/alibabacloud-ack-mcp-server/issues/1

    """

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the kubectl handler.

        Args:
            server: FastMCP server instance
            settings: Optional settings dictionary
        """
        self.settings = settings or {}

        # 超时配置
        self.kubectl_timeout = self.settings.get("kubectl_timeout", 30)

        # 是否可写变更配置
        self.allow_write = self.settings.get("allow_write", False)
        
        # Per-handler toggle
        self.enable_execution_log = self.settings.get("enable_execution_log", False)

        if server is None:
            return
        self.server = server

        self._register_tools()

    def _setup_cs_client(self, ctx: Context):
        """设置CS客户端（仅在需要时）"""
        try:
            # 检查是否已经设置过
            if hasattr(get_context_manager(), '_cs_client') and get_context_manager()._cs_client:
                return

            lifespan_context = ctx.request_context.lifespan_context
            if isinstance(lifespan_context, dict):
                providers = lifespan_context.get("providers", {})
            else:
                providers = getattr(lifespan_context, "providers", {})

            cs_client_factory = providers.get("cs_client_factory")
            if cs_client_factory:
                # 传入统一签名所需的 config
                config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}
                get_context_manager().set_cs_client(cs_client_factory("CENTER", config))
                logger.debug("CS client factory set successfully")
            else:
                logger.warning("cs_client not available in lifespan context")
        except Exception as e:
            logger.error(f"Failed to setup CS client: {e}")

    def run_command(self, command: str, kubeconfig_path: str, timeout: int, execution_log: ExecutionLog) -> Dict[str, Any]:
        try:
            tokens = shlex.split(command.strip())
        except ValueError:
            return {"exit_code": 1, "stdout": "", "stderr": "Invalid command syntax (unbalanced quotes or malformed input)"}
        cmd_start = int(time.time() * 1000)
        kubectl = KubectlRunner(kubeconfig_path, timeout, self.allow_write)
        result = kubectl.run(*tokens)
        cmd_duration = int(time.time() * 1000) - cmd_start
        execution_log.api_calls.append({
            "api": "KubectlCommand",
            "command": command,
            "type": "normal",
            "duration_ms": cmd_duration,
            "exit_code": result["exit_code"],
            "status": "success" if result["exit_code"] == 0 else "failed",
            "timeout": timeout
        })
        return result

    def _register_tools(self):
        """Register kubectl tool."""

        @self.server.tool(
            name="ack_kubectl",
            description="Execute kubectl command with intelligent context management for ACK clusters. You MUST use this tool when accessing ACK clusters. Using external shells or any other kubectl entrypoints is NOT allowed. Supports cluster_id for automatic context switching and creation."
        )
        async def ack_kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description="""IMPORTANT POLICY: When accessing ACK clusters, you MUST use this tool. Do NOT invoke kubectl via shell or any external mechanism.

Arguments after 'kubectl', e.g. 'get pods -A', 'config get-contexts', 'config use-context <name>'. Don't include the kubectl prefix. 

IMPORTANT: Do not use interactive commands. Instead:
- Use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply' instead of 'kubectl edit'
- Use 'kubectl exec' with specific commands instead of 'kubectl exec -it'
- Use service types like NodePort or LoadBalancer instead of 'kubectl port-forward'
- When using kubectl, if you need to modify certain fields, do not generate a complete YAML file for the update; instead, use the patch operation to modify the specific fields.

Response Format:
The tool returns a KubectlOutput object with the following fields:
- command: The kubectl command that was executed
- stdout: Standard output from the command (successful results)
- stderr: Standard error output (error messages, warnings)
- exit_code: Command exit code (0 for success, non-zero for errors)

Examples:
user: what pods are running in the cluster?
assistant: get pods

user: what is the status of the pod my-pod?
assistant: get pod my-pod -o jsonpath='{.status.phase}'

user: I need to edit the pod configuration
assistant: Using patch for targeted changes
patch pod my-pod --patch '{"spec":{"containers":[{"name":"main","image":"new-image"}]}}'

if need use patch to delete some exist field, need patch this field but set value to null.
example drop a exist nodeSelector kubernetes.io/hostname key: kubectl patch deployments nginx-deployment -p '{"spec": {"template": {"spec": {"nodeSelector": {"kubernetes.io/hostname": null}}}}}'

user: I need to execute a command in the pod
assistant: exec my-pod -- /bin/sh -c "your command here"""
                ),
                cluster_id: str = Field(
                    ..., description="The ID of the Kubernetes cluster to query. If specified, will auto find/create "
                                     "and switch to appropriate context. If you are not sure of cluster id, "
                                     "please use the list_clusters tool to get it first."
                ),
        ) -> KubectlOutput:

            # Set per-request context from handler setting
            enable_execution_log_ctx.set(self.enable_execution_log)

            # Initialize execution log
            start_ms = int(time.time() * 1000)
            execution_log = ExecutionLog(
                tool_call_id=f"ack_kubectl_{cluster_id}_{start_ms}",
                start_time=datetime.utcnow().isoformat() + "Z"
            )

            if not _CLUSTER_ID_PATTERN.match(cluster_id):
                error_msg = f"Invalid cluster_id format: {cluster_id}"
                execution_log.error = error_msg
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": "InvalidClusterId",
                    "cluster_id": cluster_id
                }
                return KubectlOutput(
                    command=command,
                    stdout="",
                    stderr=error_msg,
                    exit_code=1,
                    execution_log=execution_log
                )

            try:
                # 设置CS客户端
                self._setup_cs_client(ctx)

                # 获取 kubeconfig 文件路径
                context_manager = get_context_manager()
                kubeconfig_path = context_manager.get_kubeconfig_path(cluster_id, self.settings.get("kubeconfig_mode"), self.settings.get("kubeconfig_path"), execution_log)

                result = self.run_command(command, kubeconfig_path, self.kubectl_timeout, execution_log)

                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms

                return KubectlOutput(
                    command=command,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    exit_code=result["exit_code"],
                    execution_log=execution_log
                )

            except Exception as e:
                logger.error(f"kubectl tool execution error: {e}")
                execution_log.error = str(e)
                execution_log.end_time = datetime.utcnow().isoformat() + "Z"
                execution_log.duration_ms = int(time.time() * 1000) - start_ms
                execution_log.metadata = {
                    "error_type": type(e).__name__,
                    "failure_stage": "kubectl_execution",
                    "command": command
                }
                return KubectlOutput(
                    command=command,
                    stdout="",
                    stderr=str(e),
                    exit_code=1,
                    execution_log=execution_log
                )
