"""
Middleware for injecting observability context into the application context.
"""
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.config import get_logger

logger = get_logger()


class ContextInjectionMiddleware(Middleware):
    """
    This middleware is a placeholder and currently does not perform any action.
    The context injection logic has been moved directly into the tools
    that require it for a more direct and clear data flow.
    """

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        """
        This middleware currently does nothing and just passes the request along.
        """
        # The logic is now handled within the tools themselves.
        return await call_next(context)
