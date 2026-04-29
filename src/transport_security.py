"""DNS rebinding protection for MCP server transports."""

from typing import Any
from loguru import logger
from pydantic import BaseModel, Field
from starlette.requests import Request
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
import mcp.types as mt
from fastmcp.server.dependencies import get_http_headers, get_http_request
from fastmcp.exceptions import ValidationError

# logger = logging.getLogger(__name__)


class TransportSecuritySettings(BaseModel):
    """Settings for MCP transport security features.

    These settings help protect against DNS rebinding attacks by validating
    incoming request headers.
    """

    enable_dns_rebinding_protection: bool = Field(
        default=True,
        description="Enable DNS rebinding protection (recommended for production)",
    )

    allowed_hosts: list[str] = Field(
        default=[],
        description="List of allowed Host header values. Only applies when "
        + "enable_dns_rebinding_protection is True.",
    )

    allowed_origins: list[str] = Field(
        default=[],
        description="List of allowed Origin header values. Only applies when "
        + "enable_dns_rebinding_protection is True.",
    )


class TransportSecurityMiddleware(Middleware):
    """Middleware to enforce DNS rebinding protection for MCP transport endpoints."""

    def __init__(self, settings: TransportSecuritySettings | None = None):
        # If not specified, disable DNS rebinding protection by default
        # for backwards compatibility
        self.settings = settings or TransportSecuritySettings(enable_dns_rebinding_protection=False)

    def _validate_origin(self, origin: str | None) -> bool:
        """Validate the Origin header against allowed values."""
        # Origin can be absent for same-origin requests
        if not origin:
            return True

        # Check exact match first
        if origin in self.settings.allowed_origins:
            return True

        # Check wildcard port patterns
        for allowed in self.settings.allowed_origins:
            if allowed.endswith(":*"):
                # Extract base origin from pattern
                base_origin = allowed[:-2]
                # Check if the actual origin starts with base origin and has a port
                if origin.startswith(base_origin + ":"):
                    return True

        logger.warning(f"Invalid Origin header: {origin}")
        return False

    async def validate_request(self, request: Request) -> str | None:
        """Validate request headers for DNS rebinding protection.

        Returns None if validation passes, or an error message if validation fails.
        """
        # Skip remaining validation if DNS rebinding protection is disabled
        if not self.settings.enable_dns_rebinding_protection:
            return None

        # Validate Origin header
        origin = request.headers.get("origin")
        if not self._validate_origin(origin):
            return "Invalid Origin header"

        return None

    async def on_request(
        self,
        context: MiddlewareContext[mt.Request[Any, Any]],
        call_next: CallNext[mt.Request[Any, Any], Any],
    ) -> Any:
        request = get_http_request()
        logger.debug(f"Request Headers: {request.headers}")
        err = await self.validate_request(request)
        if err:
            raise ValidationError(err)
        return await call_next(context)
