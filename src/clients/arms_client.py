"""ARMS client factory for Alibaba Cloud Application Real-Time Monitoring Service."""

from fastmcp import Context
from typing import Optional


def get_arms_client(ctx: Context, region_id: str):
    """
    从 lifespan providers 中获取指定区域的 ARMS 客户端。
    Args:
        ctx: FastMCP context
        region_id: Region ID for the ARMS endpoint
    Returns:
        ARMS client instance, or None if factory is not configured
    Raises:
        RuntimeError: If arms_client_factory is configured but returns None
    """
    lifespan_context = ctx.lifespan_context or {}
    providers = lifespan_context.get("providers", {})
    config = lifespan_context.get("config", {})
    arms_client_factory = providers.get("arms_client_factory")
    if not arms_client_factory:
        return None
    return arms_client_factory(region_id, config)
