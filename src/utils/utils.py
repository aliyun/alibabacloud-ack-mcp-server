from functools import wraps
from typing import Callable, TypeVar, cast

from Tea.exceptions import TeaException

from utils.api_error import TEQ_EXCEPTION_ERROR

T = TypeVar("T")

def handle_tea_exception(func: Callable[..., T]) -> Callable[..., T]:
    """
    装饰器：处理阿里云 SDK 的 TeaException 异常

    Args:
        func: 被装饰的函数

    Returns:
        装饰后的函数，会自动处理 TeaException 异常
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except TeaException as e:
            for error in TEQ_EXCEPTION_ERROR:
                if e.code == error["errorCode"]:
                    return cast(
                        T,
                        {
                            "solution": error["solution"],
                            "message": error["errorMessage"],
                        },
                    )
            message = e.message
            if "Max retries exceeded with url" in message:
                return cast(
                    T,
                    {
                        "solution": """
                        可能原因:
                            1.	当前网络不具备访问内网域名的权限（如从公网或不通阿里云 VPC 访问）；
                            2.	指定 region 错误或不可用；
                            3.	工具或网络中存在代理、防火墙限制；
                            如果你需要排查，可以从：
                            •	尝试 ping 下域名是否可联通
                            •	查看是否有 VPC endpoint 配置错误等，如果是非VPC 环境，请配置公网入口端点，一般公网端点不会包含-intranet 等字样
                            """,
                        "message": e.message,
                    },
                )
            raise e

    return wrapper
