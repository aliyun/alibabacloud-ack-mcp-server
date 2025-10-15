from typing import Any
from fastmcp import FastMCP, Context
from pydantic import Field
import os
import subprocess
from typing import Dict, Optional
from cachetools import TTLCache
from loguru import logger
from ack_cluster_handler import parse_master_url
from models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel


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

        # 使用 .kube 目录存储 kubeconfig 文件
        self._kube_dir = os.path.expanduser("~/.kube")
        os.makedirs(self._kube_dir, exist_ok=True)

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

    def _get_or_create_kubeconfig_file(self, cluster_id: str) -> str:
        """获取或创建集群的 kubeconfig 文件
        
        Args:
            cluster_id: 集群ID
            
        Returns:
            kubeconfig 文件路径
        """
        # 检查缓存中是否已存在
        if cluster_id in self:
            logger.debug(f"Found cached kubeconfig for cluster {cluster_id}")
            return self[cluster_id]

        # 创建新的 kubeconfig 文件
        kubeconfig_content = self._get_kubeconfig_from_ack(cluster_id, int(self.ttl / 60))  # 转换为分钟
        if not kubeconfig_content:
            raise ValueError(f"Failed to get kubeconfig for cluster {cluster_id}")

        # 创建 kubeconfig 文件
        kubeconfig_path = os.path.join(self._kube_dir, f"mcp-kubeconfig-{cluster_id}.yaml")

        # 确保目录存在
        os.makedirs(os.path.dirname(kubeconfig_path), exist_ok=True)

        with open(kubeconfig_path, 'w') as f:
            f.write(kubeconfig_content)

        # 添加到缓存
        self[cluster_id] = kubeconfig_path
        return kubeconfig_path

    def popitem(self):
        """重写 popitem 方法，在驱逐缓存项时清理 kubeconfig 文件"""
        key, path = super().popitem()
        # 删除 kubeconfig 文件
        if path and os.path.exists(path):
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

    def _get_kubeconfig_from_ack(self, cluster_id: str, ttl_minutes: int = 60) -> Optional[str]:
        """通过ACK API获取kubeconfig配置
        
        Args:
            cluster_id: 集群ID
            ttl_minutes: kubeconfig有效期（分钟），默认60分钟
        """
        try:
            # 获取CS客户端
            cs_client = self._get_cs_client()
            from alibabacloud_cs20151215 import models as cs_models

            # 先检查集群详情，确认是否有公网端点
            detail_response = cs_client.describe_cluster_detail(cluster_id)

            if not detail_response or not detail_response.body:
                raise ValueError(f"Failed to get cluster details for {cluster_id}")

            cluster_info = detail_response.body
            # 检查是否有公网API Server端点
            master_url_str = getattr(cluster_info, 'master_url', '')
            master_url = parse_master_url(master_url_str)
            if not master_url["api_server_endpoint"]:
                raise ValueError(f"Cluster {cluster_id} does not have public endpoint access, "
                                 f"Please enable public endpoint access setting first.")

            # 调用DescribeClusterUserKubeconfig API
            request = cs_models.DescribeClusterUserKubeconfigRequest(
                private_ip_address=False,  # 获取公网连接配置
                temporary_duration_minutes=ttl_minutes,  # 使用传入的TTL
            )

            response = cs_client.describe_cluster_user_kubeconfig(cluster_id, request)

            if response and response.body and response.body.config:
                logger.info(f"Successfully fetched kubeconfig for cluster {cluster_id} (TTL: {ttl_minutes} minutes)")
                return response.body.config
            else:
                logger.warning(f"No kubeconfig found for cluster {cluster_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to fetch kubeconfig for cluster {cluster_id}: {e}")
            raise e

    def get_kubeconfig_path(self, cluster_id: str) -> str:
        """获取集群的 kubeconfig 文件路径
        
        Args:
            cluster_id: 集群ID
            
        Returns:
            kubeconfig 文件路径
        """
        return self._get_or_create_kubeconfig_file(cluster_id)


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
    """Handler for running kubectl commands via a FastMCP tool."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the kubectl handler.

        Args:
            server: FastMCP server instance
            settings: Optional settings dictionary
        """
        self.settings = settings or {}
        if server is None:
            return
        self.server = server

        # 超时配置
        self.kubectl_timeout = self.settings.get("kubectl_timeout", 30)

        # 是否可写变更配置
        self.allow_write = self.settings.get("allow_write", False)
        
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

    def is_write_command(self, command: str) -> tuple[bool, Optional[str]]:
        """检查是否为可写命令
        所有kubectl command operations: https://kubernetes.io/docs/reference/kubectl/

        Args:
            command: kubectl 命令字符串

        Returns:
            (是否为可写命令, 错误信息)
        """
        # 定义只读命令列表
        readonly_commands = {
            "api-resources",
            "api-versions", 
            "cluster-info",
            "describe",
            "diff",
            "events",
            "explain",
            "get",
            "kustomize",
            "logs",
            "options",
            "top",
            "version"
        }
        
        # 提取命令的第一个参数（主命令）
        command_parts = command.strip().split()
        if not command_parts:
            return True, "Empty command not allowed"
            
        main_command = command_parts[0]
        
        # 检查是否为只读命令
        if main_command in readonly_commands:
            return False, None
        
        # 所有其他命令都视为写命令
        return True, f"Write command '{main_command}' not allowed in read-only mode. Only read-only commands are permitted: {', '.join(sorted(readonly_commands))}"




    def is_interactive_command(self, command: str) -> tuple[bool, Optional[str]]:
        """检查是否为交互式 kubectl 命令

        Args:
            command: kubectl 命令字符串

        Returns:
            (是否为交互式命令, 错误信息)
        """
        is_interactive = " -it" in command
        is_port_forward = "port-forward " in command
        is_edit = "edit " in command

        if is_interactive:
            return True, "interactive mode not supported (commands with -it flag), please use non-interactive commands"
        if is_port_forward:
            return True, "interactive mode not supported for kubectl port-forward, please use service types like NodePort or LoadBalancer"
        if is_edit:
            return True, "interactive mode not supported for kubectl edit, please use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply'"

        return False, None

    def is_streaming_command(self, command: str) -> tuple[bool, Optional[str]]:
        """检查是否为流式命令

        Args:
            command: kubectl 命令字符串

        Returns:
            (是否为流式命令, 流式类型)
        """
        is_watch = " get " in command and " -w" in command
        is_logs = " logs " in command and " -f" in command
        is_attach = " attach " in command

        if is_watch:
            return True, "watch"
        if is_logs:
            return True, "logs"
        if is_attach:
            return True, "attach"

        return False, None

    def run_streaming_command(self, command: str, kubeconfig_path: str, timeout: int = 10) -> Dict[str, Any]:
        """运行流式命令，支持超时控制"""
        try:
            full_command = f"kubectl --kubeconfig {kubeconfig_path} {command}"
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            stdout_lines = []
            stderr_lines = []
            process_terminated = False

            def read_stdout():
                try:
                    for line in iter(process.stdout.readline, ''):
                        if line and not process_terminated:
                            stdout_lines.append(line)
                except Exception:
                    pass

            def read_stderr():
                try:
                    for line in iter(process.stderr.readline, ''):
                        if line and not process_terminated:
                            stderr_lines.append(line)
                except Exception:
                    pass

            import threading
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process_terminated = True
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)

            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            exit_code = process.returncode
            if process_terminated and exit_code is None:
                exit_code = 124

            return {
                "exit_code": exit_code or 0,
                "stdout": "".join(stdout_lines),
                "stderr": "".join(stderr_lines)
            }

        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e)
            }

    def run_command(self, command: str, kubeconfig_path: str, timeout: int = 10) -> Dict[str, Any]:
        """Run a kubectl command and return structured result."""
        try:
            full_command = f"kubectl --kubeconfig {kubeconfig_path} {command}"
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout.strip() if result.stdout else "",
                "stderr": result.stderr.strip() if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
            }
        except subprocess.CalledProcessError as e:
            return {
                "exit_code": e.returncode,
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else str(e),
            }

    def _register_tools(self):
        """Register kubectl tool."""

        @self.server.tool(
            name="ack_kubectl",
            description="Execute kubectl command with intelligent context management. Supports cluster_id for "
                        "automatic context switching and creation."
        )
        async def ack_kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description="""Arguments after 'kubectl', e.g. 'get pods -A', 'config get-contexts', 'config use-context <name>'. Don't include the kubectl prefix. 

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

            try:
                # 设置CS客户端
                self._setup_cs_client(ctx)

                # 检查是否为只读模式
                if not self.allow_write:
                    is_write_command, not_allow_write_error = self.is_write_command(command)
                    if is_write_command:
                        return KubectlOutput(
                            command=command,
                            stdout="",
                            stderr=not_allow_write_error,
                            exit_code=1
                        )

                # 检查是否为交互式命令
                is_interactive, interactive_error = self.is_interactive_command(command)
                if is_interactive:
                    return KubectlOutput(
                        command=command,
                        stdout="",
                        stderr=interactive_error,
                        exit_code=1
                    )

                # 获取 kubeconfig 文件路径
                context_manager = get_context_manager()
                kubeconfig_path = context_manager.get_kubeconfig_path(cluster_id)

                # 检查是否为流式命令
                is_streaming, stream_type = self.is_streaming_command(command)

                if is_streaming:
                    result = self.run_streaming_command(command, kubeconfig_path, self.kubectl_timeout)
                else:
                    result = self.run_command(command, kubeconfig_path, self.kubectl_timeout)

                return KubectlOutput(
                    command=command,
                    stdout=result["stdout"],
                    stderr=result["stderr"],
                    exit_code=result["exit_code"]
                )

            except Exception as e:
                logger.error(f"kubectl tool execution error: {e}")
                return KubectlOutput(
                    command=command,
                    stdout="",
                    stderr=str(e),
                    exit_code=1
                )
