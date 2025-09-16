from typing import Dict, Any, Optional, List
import subprocess
import shlex
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field


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

        self._register_tools()
        logger.info("Kubectl Handler initialized")

    def run_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Run a kubectl command and return structured result."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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

    def _register_tools(self):
        """Register kubectl tool."""

        @self.server.tool(
            name="kubectl",
            description="Execute kubectl command. Pass the arguments after 'kubectl'."
        )
        async def kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description="Arguments after 'kubectl', e.g. 'get pods -A'"
                ),
        ) -> Dict[str, Any]:
            try:
                args = ["kubectl"] + shlex.split(command)
                result = self.run_command(args)
                status = "success" if result.get("exit_code") == 0 else "error"
                return {"status": status, **result}
            except Exception as e:
                logger.exception("kubectl tool execution error")
                return {"status": "error", "error": str(e)}
