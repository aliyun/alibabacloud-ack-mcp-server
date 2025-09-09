"""
使用 Pydantic 进行强类型配置管理，并提供日志记录器实例。
"""

import logging
import sys
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configs(BaseSettings):
    """
    应用配置模型，从环境变量或 .env 文件加载。
    """

    # .env 文件路径
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 服务监听的端口
    HTTP_PORT: int = 8080
    # 默认的阿里云区域
    ALIYUN_REGION: str = "cn-beijing"
    # 用于客户端认证的 Bearer Token (可选)
    MCP_AUTH_TOKEN: Optional[str] = None

    def __init__(self, args_dict: dict, values=None):
        super().__init__(**values)


@lru_cache
def get_settings() -> Configs:
    """
    返回一个缓存的 Settings 实例。
    """
    return Configs()


@lru_cache
def get_logger() -> logging.Logger:
    """
    配置并返回一个全局日志记录器。
    """
    logger = logging.getLogger("mcp_server")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
