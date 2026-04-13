"""CS client factory for Alibaba Cloud Container Service."""

from fastmcp import Context


def get_cs_client(ctx: Context, region: str):
    """
    从 lifespan providers 中获取指定区域的 CS 客户端。

    Args:
        ctx: FastMCP context
        region: Region ID

    Returns:
        CS client instance

    Raises:
        RuntimeError: If cs_client_factory is not available
    """
    lifespan_context = ctx.lifespan_context or {}
    providers = lifespan_context.get("providers", {})
    config = lifespan_context.get("config", {})

    cs_client_factory = providers.get("cs_client_factory")
    if not cs_client_factory:
        raise RuntimeError("cs_client_factory not available in runtime providers")
    return cs_client_factory(region, config)
