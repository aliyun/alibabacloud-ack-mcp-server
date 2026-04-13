"""SLS client factory for Alibaba Cloud Log Service."""

from fastmcp import Context


def get_sls_client(ctx: Context, region_id: str):
    """
    从 lifespan providers 中获取指定区域的 SLS 客户端。
    Args:
        ctx: FastMCP context
        region_id: Region ID for the SLS endpoint
    Returns:
        SLS client instance
    Raises:
        RuntimeError: If sls_client_factory is not available
    """
    lifespan_context = ctx.lifespan_context or {}
    providers = lifespan_context.get("providers", {})
    config = lifespan_context.get("config", {})
    sls_client_factory = providers.get("sls_client_factory")
    if not sls_client_factory:
        raise RuntimeError("sls_client_factory not available in runtime providers")
    return sls_client_factory(region_id, config)
