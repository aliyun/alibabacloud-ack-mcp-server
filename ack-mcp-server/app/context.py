"""
定义一个全局的 ContextVar，用于在整个应用中传递请求相关的上下文信息。
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from starlette.requests import Request

from app.models import ObservabilityContext


@dataclass
class AppContext:
    """
    存储与单个请求相关的上下文信息。
    """
    request: Optional[Request] = None
    observability: Optional[ObservabilityContext] = None
    # 可以扩展以包含其他上下文信息
    extra: Dict[str, Any] = field(default_factory=dict)


# 这个 ContextVar 将在中间件中被设置，并在服务的任何地方被访问
app_context: ContextVar[AppContext] = ContextVar(
    "app_context", default=AppContext()
)
