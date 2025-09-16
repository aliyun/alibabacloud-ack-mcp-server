from typing import Dict, Any, Optional, List
import subprocess
import shlex
import tempfile
import os
from fastmcp import FastMCP, Context
from loguru import logger
from pydantic import Field

# 导入模型
try:
    from .models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel
except ImportError:
    from models import KubectlInput, KubectlOutput, KubectlErrorCodes, ErrorModel


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

    def _register_tools(self):
        """Register kubectl tool."""

        @self.server.tool(
            name="kubectl",
            description="Execute kubectl command. Pass the arguments after 'kubectl'. Optionally specify cluster_id to use ACK API kubeconfig."
        )
        async def kubectl(
                ctx: Context,
                command: str = Field(
                    ..., description="Arguments after 'kubectl', e.g. 'get pods -A'"
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
                    # 获取 region_id
                    lifespan_context = ctx.request_context.lifespan_context
                    if isinstance(lifespan_context, dict):
                        region_id = lifespan_context.get("config", {}).get("region_id", "cn-hangzhou")
                    else:
                        region_id = getattr(lifespan_context, "config", {}).get("region_id", "cn-hangzhou")
                    
                    # 获取 kubeconfig
                    kubeconfig_content = self._get_kubeconfig_from_ack(ctx, cluster_id, region_id)
                    
                    if kubeconfig_content:
                        # 创建临时文件存储 kubeconfig
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                            f.write(kubeconfig_content)
                            kubeconfig_path = f.name
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
                args = ["kubectl"] + shlex.split(command)
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
            finally:
                # 清理临时 kubeconfig 文件
                if kubeconfig_path and os.path.exists(kubeconfig_path):
                    try:
                        os.unlink(kubeconfig_path)
                        logger.debug(f"Cleaned up temporary kubeconfig file: {kubeconfig_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary kubeconfig file: {e}")
