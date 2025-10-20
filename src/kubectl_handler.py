from typing import Any
from fastmcp import FastMCP, Context
from pydantic import Field
import os
import subprocess
from typing import Dict, Optional
from loguru import logger
from models import KubectlOutput


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

    def _get_kubeconfig_path(self) -> str:
        """获取本机kubeconfig文件路径"""
        # 优先使用KUBECONFIG环境变量
        kubeconfig_path = os.environ.get('KUBECONFIG')
        if kubeconfig_path and os.path.exists(kubeconfig_path):
            return kubeconfig_path
        
        # 使用默认路径
        default_path = os.path.expanduser("~/.kube/config")
        if os.path.exists(default_path):
            return default_path
        
        # 如果都不存在，返回默认路径让kubectl处理
        return default_path

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
        ) -> KubectlOutput:

            try:
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

                # 获取本机 kubeconfig 文件路径
                kubeconfig_path = self._get_kubeconfig_path()

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
