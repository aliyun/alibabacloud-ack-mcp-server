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
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="allow"  # 允许额外的字段
    )

    def __init__(self, args_dict: Optional[dict] = None, **values):
        """
        初始化配置实例。
        
        Args:
            args_dict: 命令行参数字典（可选）
            **values: 其他配置值
        """
        if args_dict:
            # 将args_dict合并到values中
            values.update(args_dict)
        super().__init__(**values)


def get_settings(args_dict: Optional[dict] = None) -> Configs:
    """
    返回一个 Configs 实例。
    
    Args:
        args_dict: 命令行参数字典（可选）
        
    Returns:
        Configs 实例
    """
    return Configs(args_dict)
