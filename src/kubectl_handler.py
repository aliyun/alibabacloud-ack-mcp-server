from typing import Dict, Any, Optional, List
import subprocess
import shlex
import os
import threading
import time
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field
import os
import time
import threading
import tempfile
import subprocess
from typing import Dict, Optional, List
from loguru import logger

# 导入模型
try:
    from .models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel
except ImportError:
    from models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel

"""Kubeconfig Context Manager - 基于原生kubectl context的上下文管理模块
"""


class KubectlContextManager:
    """基于原生kubectl的上下文管理器

    负责管理kubectl上下文，包括：
    - 上下文创建和删除
    - 上下文切换
    - 过期时间管理
    """

    def __init__(self, mcp_kubeconfig_path: Optional[str] = None, default_ttl: int = 60):
        """初始化上下文管理器

        Args:
            mcp_kubeconfig_path: MCP专用的kubeconfig文件路径
            default_ttl: 默认过期时间（分钟）
        """
        self.default_ttl = default_ttl
        self._context_cache: Dict[str, float] = {}  # 上下文名称 -> 过期时间
        self._lock = threading.RLock()
        self._cs_client = None  # CS客户端实例

        # 设置 MCP kubeconfig 文件路径
        self._mcp_kubeconfig_path = mcp_kubeconfig_path
        self._ensure_mcp_kubeconfig_exists()

        logger.info(f"KubectlContextManager initialized with MCP kubeconfig: {self._mcp_kubeconfig_path}")

    def _ensure_mcp_kubeconfig_exists(self):
        """确保 MCP kubeconfig 文件存在"""
        import os
        import yaml

        if not os.path.exists(self._mcp_kubeconfig_path):
            # 创建基本的 kubeconfig 结构
            mcp_kubeconfig = {
                'apiVersion': 'v1',
                'kind': 'Config',
                'clusters': [],
                'contexts': [],
                'users': [],
                'preferences': {}
            }

            # 确保目录存在
            os.makedirs(os.path.dirname(self._mcp_kubeconfig_path), exist_ok=True)

            # 写入文件
            with open(self._mcp_kubeconfig_path, 'w') as f:
                yaml.dump(mcp_kubeconfig, f, default_flow_style=False)

            logger.info(f"Created MCP kubeconfig file: {self._mcp_kubeconfig_path}")

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

    def _get_kubeconfig_from_ack(self, cluster_id: str) -> Optional[str]:
        """通过ACK API获取kubeconfig配置"""
        try:
            # 获取CS客户端
            cs_client = self._get_cs_client()

            # 调用DescribeClusterUserKubeconfig API
            from alibabacloud_cs20151215 import models as cs_models

            request = cs_models.DescribeClusterUserKubeconfigRequest(
                private_ip_address=False,  # 获取公网连接配置
                temporary_duration_minutes=self.default_ttl,
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
            raise e

    def _run_kubectl_command(self, args: List[str]) -> Dict[str, str]:
        """执行kubectl命令

        Args:
            args: kubectl命令参数

        Returns:
            简化的结果字典，包含stdout和stderr
        """
        try:
            cmd = ["kubectl"] + args
            # 使用 MCP kubeconfig 文件
            cmd.extend(["--kubeconfig", self._mcp_kubeconfig_path])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except subprocess.CalledProcessError as e:
            return {
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else str(e)
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Command timed out"
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e)
            }

    def _find_context_by_cluster_id(self, cluster_id: str) -> Optional[str]:
        """根据cluster_id查找对应的上下文名称

        Args:
            cluster_id: 集群ID

        Returns:
            包含cluster_id的上下文名称，如果不存在则返回None
        """
        result = self._run_kubectl_command(["config", "get-contexts"])
        if result["stderr"]:
            return None

        try:
            lines = result["stdout"].strip().split('\n')
            # 跳过标题行
            for line in lines[1:]:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    context_name = parts[1]
                    if cluster_id in context_name:
                        return context_name
            return None
        except Exception as e:
            logger.error(f"Failed to parse contexts output: {e}")
            raise e

    def _is_context_expired(self, context_name: str) -> bool:
        """检查上下文是否过期（提前5分钟认为过期）

        Args:
            context_name: 上下文名称

        Returns:
            是否过期
        """
        if context_name not in self._context_cache:
            return False
        # 提前5分钟认为过期
        return time.time() > (self._context_cache[context_name] - 300)

    def _cleanup_expired_contexts(self):
        """清理过期的上下文"""
        with self._lock:
            expired_contexts = []
            for context_name, expires_at in self._context_cache.items():
                if time.time() > expires_at:
                    expired_contexts.append(context_name)

            for context_name in expired_contexts:
                self._remove_context_internal(context_name)
                logger.debug(f"Cleaned up expired context: {context_name}")

    def _remove_context_internal(self, context_name: str):
        """内部方法：移除上下文（不加锁）"""
        try:
            # 从kubectl中删除上下文
            result = self._run_kubectl_command(["config", "delete-context", context_name])
            if not result["stderr"]:
                logger.debug(f"Removed context from kubectl: {context_name}")
            else:
                logger.warning(f"Failed to remove context from kubectl: {result['stderr']}")

            # 从缓存中移除
            if context_name in self._context_cache:
                del self._context_cache[context_name]

        except Exception as e:
            logger.warning(f"Failed to remove context {context_name}: {e}")
            raise e

    def switch_context(self, context_name: str) -> None:
        """切换上下文

        Args:
            context_name: 上下文名称

        Raises:
            ValueError: 当上下文不存在或已过期时
            RuntimeError: 当切换上下文失败时
        """
        with self._lock:
            # 检查上下文是否存在
            if not self._context_exists(context_name):
                error_msg = f"Context '{context_name}' does not exist"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 检查是否过期
            if self._is_context_expired(context_name):
                error_msg = f"Context '{context_name}' has expired"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 切换上下文
            result = self._run_kubectl_command(["config", "use-context", context_name])
            if not result["stderr"]:
                logger.info(f"Successfully switched to context: {context_name}")
            else:
                error_msg = f"Failed to switch to context '{context_name}': {result['stderr']}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

    def switch_context_for_cluster(self, cluster_id: str) -> None:
        """为指定集群智能切换上下文

        Args:
            cluster_id: 集群ID

        Raises:
            ValueError: 当集群ID无效或上下文操作失败时
            RuntimeError: 当无法获取kubeconfig或创建上下文失败时
        """
        try:
            # 1. 首先检查是否已存在包含cluster_id的上下文
            existing_context_name = self._find_context_by_cluster_id(cluster_id)

            if existing_context_name:
                # 检查上下文是否过期
                if self._is_context_expired(existing_context_name):
                    logger.info(
                        f"Context '{existing_context_name}' for cluster {cluster_id} has expired, recreating...")
                    # 移除过期上下文
                    self._remove_context_internal(existing_context_name)
                    existing_context_name = None
                else:
                    # 上下文有效，直接切换
                    try:
                        self.switch_context(existing_context_name)
                        logger.info(f"Switched to existing context '{existing_context_name}' for cluster {cluster_id}")
                        return
                    except (ValueError, RuntimeError) as e:
                        logger.warning(
                            f"Failed to switch to existing context '{existing_context_name}': {e}, will recreate...")
                        existing_context_name = None

            # 2. 如果不存在有效上下文，从ACK API获取并创建新上下文
            if not existing_context_name:
                logger.info(f"Creating new kubeconfig context for cluster {cluster_id}")
                kubeconfig_content = self._get_kubeconfig_from_ack(cluster_id)

                if not kubeconfig_content:
                    error_msg = f"Failed to fetch kubeconfig from ACK API for cluster {cluster_id}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # 创建新上下文
                created_context_name = self._create_context_from_kubeconfig(
                    kubeconfig_content=kubeconfig_content,
                    ttl=self.default_ttl
                )

                if not created_context_name:
                    error_msg = f"Failed to create context from kubeconfig for cluster {cluster_id}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # 切换到新创建的上下文
                try:
                    self.switch_context(created_context_name)
                    logger.info(
                        f"Created and switched to new context '{created_context_name}' for cluster {cluster_id}")
                except Exception as e:
                    error_msg = f"Failed to switch to newly created context '{created_context_name}' for cluster {cluster_id}: {e}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error handling context for cluster {cluster_id}: {e}"
            logger.error(error_msg)
            raise e

    def _context_exists(self, context_name: str) -> bool:
        """检查上下文是否存在"""
        result = self._run_kubectl_command(["config", "get-contexts"])
        if result["stderr"]:
            return False
        return context_name in result["stdout"]

    def _is_auto_created_context(self, context_name: str) -> bool:
        """检查是否为自动创建的上下文

        Args:
            context_name: 上下文名称

        Returns:
            是否为自动创建的上下文
        """
        return context_name.startswith("mcp-auto-")

    def _create_context_from_kubeconfig(self, kubeconfig_content: str, ttl: Optional[int] = None) -> Optional[str]:
        """从kubeconfig内容创建上下文（避免覆盖现有context）"""
        with self._lock:
            self._cleanup_expired_contexts()

            try:
                # 直接解析kubeconfig内容，不需要临时文件
                import yaml
                kubeconfig_data = yaml.safe_load(kubeconfig_content)

                if not kubeconfig_data:
                    logger.error("Invalid kubeconfig content")
                    return None

                current_context = kubeconfig_data.get('current-context', '')
                if not current_context:
                    logger.error("No current context found in kubeconfig")
                    return None

                # 获取上下文信息
                contexts = kubeconfig_data.get('contexts', [])
                clusters = kubeconfig_data.get('clusters', [])
                users = kubeconfig_data.get('users', [])

                # 找到当前上下文对应的配置
                current_ctx_config = None
                for ctx in contexts:
                    if ctx.get('name') == current_context:
                        current_ctx_config = ctx.get('context', {})
                        break

                if not current_ctx_config:
                    logger.error(f"Context configuration not found for '{current_context}'")
                    return None

                # 找到对应的集群和用户配置
                cluster_name = current_ctx_config.get('cluster', '')
                user_name = current_ctx_config.get('user', '')

                cluster_config = None
                user_config = None

                for cluster in clusters:
                    if cluster.get('name') == cluster_name:
                        cluster_config = cluster.get('cluster', {})
                        break

                for user in users:
                    if user.get('name') == user_name:
                        user_config = user.get('user', {})
                        break

                if not cluster_config or not user_config:
                    logger.error(f"Cluster or user configuration not found for context '{current_context}'")
                    return None

                # 创建集群配置（使用唯一名称避免冲突）
                unique_cluster_name = f"{cluster_name}-{int(time.time())}"
                cluster_cmd = ["config", "set-cluster", unique_cluster_name]
                if cluster_config.get('server'):
                    cluster_cmd.extend(["--server", cluster_config['server']])

                # 处理证书授权数据
                ca_data = cluster_config.get('certificate-authority-data')
                ca_file = cluster_config.get('certificate-authority')
                if ca_data:
                    # 将证书数据写入临时文件
                    import base64
                    import tempfile
                    ca_content = base64.b64decode(ca_data).decode('utf-8')
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                        f.write(ca_content)
                        ca_file = f.name
                    cluster_cmd.extend(["--certificate-authority", ca_file])
                elif ca_file:
                    cluster_cmd.extend(["--certificate-authority", ca_file])

                result = self._run_kubectl_command(cluster_cmd)
                if result["stderr"]:
                    logger.error(f"Failed to set cluster {unique_cluster_name}: {result['stderr']}")
                    return None

                # 创建用户配置（使用唯一名称避免冲突）
                unique_user_name = f"{user_name}-{int(time.time())}"
                user_cmd = ["config", "set-credentials", unique_user_name]
                if user_config.get('token'):
                    user_cmd.extend(["--token", user_config['token']])

                # 处理客户端证书数据
                cert_data = user_config.get('client-certificate-data')
                cert_file = user_config.get('client-certificate')
                if cert_data:
                    # 将证书数据写入临时文件
                    import base64
                    import tempfile
                    cert_content = base64.b64decode(cert_data).decode('utf-8')
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                        f.write(cert_content)
                        cert_file = f.name
                    user_cmd.extend(["--client-certificate", cert_file])
                elif cert_file:
                    user_cmd.extend(["--client-certificate", cert_file])

                # 处理客户端密钥数据
                key_data = user_config.get('client-key-data')
                key_file = user_config.get('client-key')
                if key_data:
                    # 将密钥数据写入临时文件
                    import base64
                    import tempfile
                    key_content = base64.b64decode(key_data).decode('utf-8')
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                        f.write(key_content)
                        key_file = f.name
                    user_cmd.extend(["--client-key", key_file])
                elif key_file:
                    user_cmd.extend(["--client-key", key_file])

                result = self._run_kubectl_command(user_cmd)
                if result["stderr"]:
                    logger.error(f"Failed to set credentials {unique_user_name}: {result['stderr']}")
                    return None

                # 创建上下文配置（使用特定格式命名自动创建的context）
                unique_context_name = f"mcp-auto-{current_context}-{int(time.time())}"
                context_cmd = [
                    "config", "set-context", unique_context_name,
                    "--cluster", unique_cluster_name,
                    "--user", unique_user_name
                ]

                if current_ctx_config.get('namespace'):
                    context_cmd.extend(["--namespace", current_ctx_config['namespace']])

                result = self._run_kubectl_command(context_cmd)
                if not result["stderr"]:
                    # 设置过期时间
                    expires_at = time.time() + (ttl or self.default_ttl) * 60
                    self._context_cache[unique_context_name] = expires_at
                    logger.info(
                        f"Created context '{unique_context_name}' (from '{current_context}'), expires at {expires_at}")
                    return unique_context_name
                else:
                    logger.error(f"Failed to create context {unique_context_name}: {result['stderr']}")
                    return None

            except Exception as e:
                logger.error(f"Failed to create context: {e}")
                raise e

    def cleanup_all(self):
        """清理所有自动创建的上下文（删除整个 MCP kubeconfig 文件）"""
        with self._lock:
            try:
                import os

                # 删除 MCP kubeconfig 文件
                if os.path.exists(self._mcp_kubeconfig_path):
                    os.remove(self._mcp_kubeconfig_path)
                    logger.info(f"Deleted MCP kubeconfig file: {self._mcp_kubeconfig_path}")
                else:
                    logger.info("MCP kubeconfig file does not exist, nothing to clean up")

                # 清空缓存
                self._context_cache.clear()
                logger.info("Cleaned up all auto-created contexts by removing MCP kubeconfig")

            except Exception as e:
                logger.error(f"Failed to cleanup auto-created contexts: {e}")
                raise e


# 全局上下文管理器实例
_context_manager: Optional[KubectlContextManager] = None


def get_context_manager(mcp_kubeconfig_path: Optional[str] = None) -> KubectlContextManager:
    """获取全局上下文管理器实例

    Args:
        mcp_kubeconfig_path: MCP专用的kubeconfig文件路径

    Returns:
        上下文管理器实例
    """
    global _context_manager
    if _context_manager is None:
        _context_manager = KubectlContextManager(mcp_kubeconfig_path)
    return _context_manager


def switch_context_for_cluster(cluster_id: str) -> None:
    """便捷函数：为指定集群智能切换上下文

    Args:
        cluster_id: 集群ID

    Raises:
        ValueError: 当集群ID无效或上下文操作失败时
        RuntimeError: 当无法获取kubeconfig或创建上下文失败时
    """
    return get_context_manager().switch_context_for_cluster(cluster_id)


class KubectlHandler:
    """Handler for running kubectl commands via a FastMCP tool."""

    def __init__(self, server: FastMCP, settings: Optional[Dict[str, Any]] = None):
        """Initialize the kubectl handler.

        Args:
            server: FastMCP server instance
            settings: Configuration settings
        """
        self.server = server
        self.settings = settings or {}
        self.allow_write = self.settings.get("allow_write", True)

        # 设置 MCP kubeconfig 路径
        self.mcp_kubeconfig_path = os.path.expanduser("~/.kube/mcp-kubeconfig")

        # 初始化上下文管理器，传递 MCP kubeconfig 路径
        self.context_manager = get_context_manager(self.mcp_kubeconfig_path)

        self._register_tools()
        self._setup_cleanup_handlers()
        logger.info("Kubectl Handler initialized with context manager")

    def _setup_cleanup_handlers(self):
        """设置清理处理器"""
        import atexit
        import signal

        def cleanup_contexts():
            """清理所有上下文"""
            try:
                logger.info("Cleaning up kubectl contexts on exit...")
                self.context_manager.cleanup_all()
            except Exception as e:
                logger.warning(f"Failed to cleanup contexts on exit: {e}")

        def signal_handler(signum, frame):
            """信号处理器"""
            logger.info(f"Received signal {signum}, cleaning up contexts...")
            cleanup_contexts()
            exit(0)

        # 注册退出清理
        atexit.register(cleanup_contexts)

        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _setup_cs_client(self, ctx: Context):
        """设置CS客户端（仅在需要时）"""
        try:
            # 检查是否已经设置过
            if hasattr(self.context_manager, '_cs_client') and self.context_manager._cs_client:
                return

            lifespan_context = ctx.request_context.lifespan_context
            if isinstance(lifespan_context, dict):
                providers = lifespan_context.get("providers", {})
            else:
                providers = getattr(lifespan_context, "providers", {})

            cs_client_factory = providers.get("cs_client_factory")
            if cs_client_factory:
                self.context_manager.set_cs_client(cs_client_factory("CENTER"))
                logger.debug("CS client factory set successfully")
            else:
                logger.warning("cs_client not available in lifespan context")
        except Exception as e:
            logger.error(f"Failed to setup CS client: {e}")

    def is_interactive_command(self, command: str) -> tuple[bool, Optional[str]]:
        """检查是否为交互式 kubectl 命令

        Args:
            command: kubectl 命令字符串

        Returns:
            tuple: (是否为交互式命令, 错误信息)
        """
        # 检查是否包含交互式命令模式
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

    def build_kubectl_command(self, command: str) -> List[str]:
        """构建完整的 kubectl 命令列表

        Args:
            command: kubectl 命令参数（不包含 kubectl 前缀）

        Returns:
            List[str]: 完整的命令列表，包含 --kubeconfig 参数
        """
        # 直接拼接命令字符串，然后解析
        full_command = f"kubectl --kubeconfig {self.mcp_kubeconfig_path} {command}"
        return shlex.split(full_command)

    def is_streaming_command(self, command: str) -> tuple[bool, Optional[str]]:
        """检查是否为流式命令

        Args:
            command: kubectl 命令字符串

        Returns:
            tuple: (是否为流式命令, 流式命令类型)
        """
        is_watch = "get " in command and " -w" in command
        is_logs = "logs " in command and " -f" in command
        is_attach = "attach " in command

        if is_watch:
            return True, "watch"
        if is_logs:
            return True, "logs"
        if is_attach:
            return True, "attach"

        return False, None

    def run_streaming_command(self, command: str, timeout: int = 7) -> Dict[str, Any]:
        """运行流式命令，支持超时控制

        Args:
            command: kubectl 命令字符串
            timeout: 超时时间（秒）

        Returns:
            Dict: 包含执行结果的字典
        """
        try:
            # 直接拼接命令字符串，使用 shell=True
            full_command = f"kubectl --kubeconfig {self.mcp_kubeconfig_path} {command}"

            # 创建进程
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
            is_timeout = False

            def read_stdout():
                """读取 stdout"""
                try:
                    for line in iter(process.stdout.readline, ''):
                        if is_timeout:
                            break
                        stdout_lines.append(line)
                        logger.info(f"STDOUT: {line.strip()}")
                except Exception as e:
                    logger.error(f"Error reading stdout: {e}")

            def read_stderr():
                """读取 stderr"""
                try:
                    for line in iter(process.stderr.readline, ''):
                        if is_timeout:
                            break
                        stderr_lines.append(line)
                        logger.error(f"STDERR: {line.strip()}")
                except Exception as e:
                    logger.error(f"Error reading stderr: {e}")

            # 启动读取线程
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)

            stdout_thread.start()
            stderr_thread.start()

            # 等待超时或进程结束
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                is_timeout = True
                process.kill()
                process.wait()

                return {
                    "exit_code": 124,  # 超时退出码
                    "stdout": "".join(stdout_lines),
                    "stderr": f"Timeout reached after {timeout} seconds\n" + "".join(stderr_lines)
                }

            # 等待读取线程完成
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            return {
                "exit_code": process.returncode,
                "stdout": "".join(stdout_lines),
                "stderr": "".join(stderr_lines)
            }

        except Exception as e:
            logger.error(f"Streaming command failed: {e}")
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e)
            }

    def run_command(self, command: str) -> Dict[str, Any]:
        """Run a kubectl command and return structured result."""
        try:
            # 直接拼接命令字符串，使用 shell=True
            full_command = f"kubectl --kubeconfig {self.mcp_kubeconfig_path} {command}"
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True, check=True)
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout.strip() if result.stdout else "",
                "stderr": result.stderr.strip() if result.stderr else "",
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"kubectl command failed: {command}")
            return {
                "exit_code": e.returncode,
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else str(e),
            }

    def _register_tools(self):
        """Register kubectl tool."""

        @self.server.tool(
            name="kubectl",
            description="Execute kubectl command with intelligent context management. Supports cluster_id for "
                        "automatic context switching and creation."
        )
        async def kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description=""
                                     """Arguments after 'kubectl', e.g. 'get pods -A', 'config get-contexts', 'config use-context <name>'. Don't include the kubectl prefix.

IMPORTANT: Do not use interactive commands. Instead:
- Use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply' instead of 'kubectl edit'
- Use 'kubectl exec' with specific commands instead of 'kubectl exec -it'
- Use service types like NodePort or LoadBalancer instead of 'kubectl port-forward'

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
assistant: # Option 1: Using patch for targeted changes
patch pod my-pod --patch '{"spec":{"containers":[{"name":"main","image":"new-image"}]}}'

# Option 2: Using get and apply for full changes
get pod my-pod -o yaml > pod.yaml
# Edit pod.yaml locally
apply -f pod.yaml

user: I need to execute a command in the pod
assistant: exec my-pod -- /bin/sh -c "your command here"""
                ),
                cluster_id: str = Field(
                    ..., description="The ID of the Kubernetes cluster to query. If specified, will auto find/create "
                                     "and switch to appropriate context. If you are not sure of cluster id, "
                                     "please use the list_clusters tool to get it first."
                ),
        ) -> KubectlOutput:
            if not cluster_id:
                raise ValueError("cluster_id is required")

            # 检查是否为交互式命令
            is_interactive, error_msg = self.is_interactive_command(command)
            if is_interactive:
                return KubectlOutput(
                    command=command,
                    stdout="",
                    stderr=error_msg,
                    exit_code=1
                )

            try:
                self._setup_cs_client(ctx)
                switch_context_for_cluster(cluster_id)

                # 检查是否为流式命令
                is_streaming, _ = self.is_streaming_command(command)
                if is_streaming:
                    result = self.run_streaming_command(command)
                else:
                    result = self.run_command(command)

                # 构建返回结果
                return KubectlOutput(
                    command=command,
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    exit_code=result.get("exit_code", 0)
                )

            except Exception as e:
                logger.exception("kubectl tool execution error")
                return KubectlOutput(
                    command=command,
                    stdout="",
                    stderr=f"Error: {str(e)}",
                    exit_code=1
                )
