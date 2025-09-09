"""
应用主入口，负责组装和启动服务。
"""
import uvicorn
from fastapi import FastAPI, Request
from fastmcp import FastMCP

from app.config import get_logger, get_settings
from app.context import app_context, AppContext
from app.middleware.auth import AuthAndContextMiddleware
from app.middleware.context_injection import ContextInjectionMiddleware
from app.services.aliyun_service import AliyunService
from app.services.kubectl_service import KubectlService
from app.services.observability_service import ObservabilityService
from app.tools.registry import register_all_tools

# 1. 初始化配置和日志
settings_dict = get_settings()
logger = get_logger()

# 2. 在应用启动时创建服务实例
# 注意：在真实应用中，你可能希望 AliyunService 也是按需创建的，
# 但对于这个架构，在启动时创建是清晰且可行的。
# 我们的 Auth 中间件仍然可以为每次请求动态注入凭证。
aliyun_service = AliyunService()  # 使用默认凭证链初始化
kubectl_service = KubectlService()
observability_service = ObservabilityService()
logger.info("Services initialized.")

# 3. 创建 FastMCP 服务器实例
mcp_server = FastMCP(
    name="CloudOperatorServer",
)

# 4. 将我们的核心认证和上下文注入中间件添加到 MCP 服务器
mcp_server.add_middleware(AuthAndContextMiddleware())
mcp_server.add_middleware(ContextInjectionMiddleware())
logger.info("AuthAndContextMiddleware added to MCP server.")

# 5. 注册所有定义的工具，并注入服务实例
register_all_tools(mcp_server, aliyun_service,
                   kubectl_service, observability_service)
logger.info("All tools have been registered.")

# 5. 创建 MCP 服务器的 ASGI 应用
# 这里的 path 是 MCP 协议的端点，将挂载在 FastAPI 的 /mcp 路径下
mcp_app = mcp_server.http_app(path="/v1")
logger.info("MCP server has been converted to an ASGI app.")

# 6. 创建 FastAPI 应用实例
# 关键：将 mcp_app 的生命周期管理函数传递给 FastAPI
app = FastAPI(
    title="Cloud Operator API",
    version="1.0.0",
    lifespan=mcp_app.lifespan,
)

# 7. 添加用于捕获请求的 ASGI 中间件


@app.middleware("http")
async def set_request_context_middleware(request: Request, call_next):
    """
    这个 ASGI 中间件在请求处理期间将 request 对象存入 ContextVar，
    以便 fastmcp 中间件可以访问它。
    """
    # 创建一个新的 AppContext 实例并设置请求对象
    ctx = AppContext(request=request)
    app_context.set(ctx)
    response = await call_next(request)
    return response

# 8. 将 MCP 应用挂载到 FastAPI 应用的特定路径下
app.mount("/mcp", mcp_app)
logger.info("MCP ASGI app mounted on /mcp.")


@app.get("/", summary="Health Check")
def health_check():
    """
    一个简单的健康检查端点。
    """
    return {"status": "ok"}


if __name__ == "__main__":
    logger.info(f"Starting server on port {settings_dict.HTTP_PORT}...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings_dict.HTTP_PORT,
        reload=True,
        log_level="info",
    )
