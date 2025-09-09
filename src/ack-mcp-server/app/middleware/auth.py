"""
核心认证与上下文注入中间件。
"""

from typing import Any, Dict

from app.config import get_logger, get_settings
from app.context import app_context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp import ErrorData, McpError

logger = get_logger()
settings_dict = get_settings()

ALIYUN_CREDENTIALS_KEY = "aliyun_credentials"
"""MCP上下文中存储阿里云凭证的键。"""


class AuthAndContextMiddleware(Middleware):
    """
    一个 fastmcp 中间件，用于：
    1.  执行 Bearer Token 认证。
    2.  从 HTTP Headers 中提取阿里云凭证。
    3.  将凭证注入到 MCP 会话的上下文中。
    """

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        """
        在每个 MCP 请求到达时执行。
        """
        logger.info("Auth middleware: Intercepting request.")

        # 1. 从 ContextVar 中安全地读取 Request 对象
        context_obj = app_context.get()
        if not context_obj or not context_obj.request:
            logger.error("Auth middleware: Cannot access HTTP request context.")
            raise McpError(
                ErrorData(
                    code=-32001,
                    message="Server configuration error: Cannot access HTTP request context.",
                )
            )

        request = context_obj.request

        # 2. 执行 Bearer Token 认证
        self._validate_bearer_token(request.headers.get("Authorization"))

        # 3. 提取阿里云凭证
        aliyun_creds = self._extract_aliyun_credentials(request.headers)

        # 4. 将凭证直接注入到当前请求的 scope 中，以便下游工具可以访问
        if aliyun_creds:
            logger.info(
                "Auth middleware: Injecting Aliyun credentials into request scope."
            )
            request.scope["credentials"] = aliyun_creds

        # 5. 继续执行中间件链
        return await call_next(context)

    def _validate_bearer_token(self, auth_header: str | None):
        """
        校验 Bearer Token。
        """
        required_token = settings_dict.MCP_AUTH_TOKEN
        if not required_token:
            logger.info("Auth middleware: Bearer token authentication is disabled.")
            return  # 如果未配置 Token，则跳过认证

        if not auth_header:
            logger.warning("Auth middleware: Authorization header is missing.")
            raise McpError(
                ErrorData(code=401, message="Authorization header is required.")
            )

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning("Auth middleware: Invalid Authorization header format.")
            raise McpError(
                ErrorData(
                    code=401,
                    message="Authorization header format must be 'Bearer {token}'.",
                )
            )

        token = parts[1]
        if token != required_token:
            logger.warning("Auth middleware: Invalid authorization token.")
            raise McpError(ErrorData(code=401, message="Invalid authorization token."))

        logger.info("Auth middleware: Bearer token validated successfully.")

    def _extract_aliyun_credentials(self, headers: Any) -> Dict[str, str]:
        """
        从请求头中提取所有相关的阿里云凭证。
        """
        creds = {
            "ak_id": headers.get("X-Aliyun-Access-Key-Id"),
            "ak_secret": headers.get("X-Aliyun-Access-Key-Secret"),
            "sts_token": headers.get("X-Aliyun-Security-Token"),
            "region": headers.get("X-Aliyun-Region"),
        }
        # 过滤掉值为 None 的条目
        extracted_creds = {k: v for k, v in creds.items() if v}
        if extracted_creds:
            logger.info(
                f"Auth middleware: Found Aliyun credentials in headers: {list(extracted_creds.keys())}"
            )
        return extracted_creds
