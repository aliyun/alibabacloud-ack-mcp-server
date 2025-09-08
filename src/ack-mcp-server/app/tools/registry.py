"""
统一注册所有可用的 MCP 工具。
"""
from fastmcp import FastMCP

from app.services.aliyun_service import AliyunService
from app.services.kubectl_service import KubectlService
from app.services.observability_service import ObservabilityService

from . import aliyun_tools, kubectl_tools, observability_tools


def register_all_tools(
    mcp: FastMCP,
    aliyun_svc: AliyunService,
    kubectl_svc: KubectlService,
    obs_svc: ObservabilityService,
):
    """
    将所有定义的工具及其处理器注册到 FastMCP 实例。

    Args:
        mcp: The FastMCP server instance.
        aliyun_svc: The Aliyun service instance.
        kubectl_svc: The Kubectl service instance.
        obs_svc: The Observability service instance.
    """
    # 注册阿里云工具
    aliyun_tools.register_aliyun_tools(mcp, aliyun_svc)

    # 注册 Kubectl 工具
    kubectl_tools.register_kubectl_tools(mcp, kubectl_svc)

    # 注册可观测性工具
    observability_tools.register_observability_tools(mcp, obs_svc)
