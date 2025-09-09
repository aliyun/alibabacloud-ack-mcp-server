"""
定义所有与 Kubectl 相关的 MCP 工具。
"""

import re
from typing import Annotated, Literal, Tuple

from app.services.kubectl_service import KubectlError, KubectlService
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field


def is_interactive_command(command: str) -> Tuple[bool, str]:
    """
    检查命令是否为交互式命令。

    Args:
        command: 要检查的 kubectl 命令

    Returns:
        Tuple[bool, str]: (是否为交互式命令, 错误信息)
    """
    interactive_patterns = [
        r"kubectl exec.*-it",
        r"kubectl edit",
        r"kubectl port-forward",
    ]

    for pattern in interactive_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True, f"交互式命令不支持: {pattern}"

    return False, ""


def is_dangerous_command(command: str) -> Tuple[bool, str]:
    """
    检查命令是否包含危险操作。

    Args:
        command: 要检查的 kubectl 命令

    Returns:
        Tuple[bool, str]: (是否为危险命令, 错误信息)
    """
    dangerous_patterns = [
        # 文件系统操作
        r"\brm\b",
        r"\bmv\b",
        r"\bcp\b",
        r"\btouch\b",
        r"\becho\b.*>",
        r"\bcat\b.*>",
        # 命令连接符
        r"&&",
        r"\|\|",
        r";",
        r"\|",
        # 系统命令
        r"\bsudo\b",
        r"\bsu\b",
        r"\bchmod\b",
        r"\bchown\b",
        r"\bmount\b",
        r"\bumount\b",
        # 网络工具
        r"\bcurl\b",
        r"\bwget\b",
        r"\bssh\b",
        r"\bscp\b",
        # 进程管理
        r"\bkill\b",
        r"\bpkill\b",
        r"\bkillall\b",
        # 包管理
        r"\bapt\b",
        r"\byum\b",
        r"\bdnf\b",
        r"\bpacman\b",
        r"\bbrew\b",
        # 危险的 kubectl 命令
        r"kubectl.*delete.*--all",
        r"kubectl.*delete.*--force",
        r"kubectl.*delete.*--grace-period=0",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True, f"检测到潜在的危险命令模式: {pattern}"

    return False, ""


def register_kubectl_tools(mcp_server: FastMCP, kubectl_svc: KubectlService):
    """注册所有 Kubectl 相关的工具到 MCP 服务器。"""

    @mcp_server.tool("kubectl")
    async def kubectl(
        command: Annotated[
            str,
            Field(
                description="要执行的完整 kubectl 命令，必须以 'kubectl' 开头。对于多行命令，建议使用 heredoc 语法。",
                min_length=1,
                max_length=5000,
            ),
        ],
        modifies_resource: Annotated[
            Literal["yes", "no", "unknown"],
            Field(
                description="命令是否会修改 Kubernetes 资源。'yes' 表示会修改（如 apply, delete），'no' 表示只读（如 get, describe），'unknown' 表示不确定。"
            ),
        ] = "unknown",
    ) -> str:
        """
        在用户的 Kubernetes 集群上执行 kubectl 命令。

        成功时，此工具返回命令的标准输出 (stdout)。
        失败时，此工具会引发一个 ToolError，其中包含标准错误 (stderr) 的详细信息。

        重要提示：此环境不支持交互式命令，例如：
        - `kubectl exec -it ...` (请使用非交互式 exec)
        - `kubectl edit ...` (请使用 `get -o yaml` 结合 `apply` 或 `patch`)
        - `kubectl port-forward ...` (请使用 NodePort 或 LoadBalancer 服务)

        Returns:
            命令的标准输出 (stdout) 字符串。

        Raises:
            ToolError: 如果命令执行失败、包含不允许的模式或为交互式命令。
        """
        # 1. 检查是否为交互式命令
        is_interactive, interactive_error = is_interactive_command(command)
        if is_interactive:
            raise ToolError(interactive_error)

        # 2. 检查是否为危险命令
        is_dangerous, dangerous_error = is_dangerous_command(command)
        if is_dangerous:
            raise ToolError(dangerous_error)

        # 3. 执行 kubectl 命令
        try:
            return await kubectl_svc.execute(command=command)
        except KubectlError as e:
            # 将底层的 KubectlError 转换为 ToolError，以便将详细的 stderr 返回给用户
            error_message = f"Kubectl command failed with exit code {e.return_code}.\nStderr: {e.stderr}"
            raise ToolError(error_message) from e
        except ValueError as e:
            # 捕获服务层可能抛出的其他验证错误
            raise ToolError(str(e)) from e
