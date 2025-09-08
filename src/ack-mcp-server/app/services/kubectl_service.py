"""
封装执行 kubectl 命令的逻辑。
"""
import asyncio
import shlex
from typing import Any

from app.config import get_logger

logger = get_logger()


class KubectlError(Exception):
    """自定义 Kubectl 命令执行错误。"""

    def __init__(self, message: str, stderr: str = "", return_code: int = -1):
        super().__init__(message)
        self.stderr = stderr
        self.return_code = return_code


class KubectlService:
    """
    一个封装了 kubectl 命令执行的服务类。
    """

    async def execute(self, command: str) -> str:
        """
        安全地执行一个 kubectl 命令。

        Args:
            command: 完整的 kubectl 命令字符串，例如 "get pods -n default"。

        Returns:
            命令的标准输出 (stdout)。

        Raises:
            KubectlError: 如果命令执行失败。
        """
        # 为安全起见，确保命令以 "kubectl" 开头
        if not command.strip().startswith("kubectl"):
            raise ValueError("Invalid command: must start with 'kubectl'.")

        # 使用 shlex 分割命令以防止注入攻击
        args = shlex.split(command)
        logger.info(f"Executing kubectl command: {' '.join(args)}")

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        return_code = process.returncode if process.returncode is not None else -1
        if return_code != 0:
            error_message = f"Kubectl command failed with exit code {return_code}."
            stderr_str = stderr.decode("utf-8").strip()
            logger.error(f"{error_message}\nStderr: {stderr_str}")
            raise KubectlError(
                message=error_message,
                stderr=stderr_str,
                return_code=return_code,
            )

        stdout_str = stdout.decode("utf-8").strip()
        logger.info(
            f"Kubectl command executed successfully. Stdout length: {len(stdout_str)}")
        return stdout_str
