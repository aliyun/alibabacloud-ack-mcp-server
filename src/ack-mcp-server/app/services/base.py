"""
阿里云服务的基础类，封装通用的客户端创建和认证逻辑。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from alibabacloud_credentials.client import Client as CredentialsClient
from alibabacloud_credentials.models import Config as CredentialsConfig
from alibabacloud_tea_openapi import models as openapi_models
from aliyunsdkcore.client import AcsClient
from app.config import get_logger, get_settings

logger = get_logger()
settings_dict = get_settings()


class BaseService(ABC):
    """
    A base class for services that require credentials.
    """

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
        self.ak_id = credentials.get("ak_id")
        self.ak_secret = credentials.get("ak_secret")
        self.region = credentials.get("region")

    def get_client(self, region_id: Optional[str] = None) -> "AcsClient":
        """
        Creates and returns an AcsClient instance.
        """
        # Use the provided region_id, fallback to self.region, then to a default
        final_region = region_id or self.region or "cn-hangzhou"

        # Ensure credentials are provided
        if not self.ak_id or not self.ak_secret:
            raise ValueError("AccessKey ID and Secret are required to create a client.")

        return AcsClient(self.ak_id, self.ak_secret, final_region)


class BaseAliyunService(ABC):
    """
    阿里云服务的基础类，提供通用的客户端创建和认证逻辑。

    默认使用 Container Service (CS) 的 endpoint 格式: cs.{region}.aliyuncs.com
    子类可以通过重写相应方法来定制特定服务的需求。
    """

    def __init__(self):
        """
        初始化基础阿里云服务。
        """
        logger.info(f"Initializing {self.__class__.__name__} with client caching.")
        self._client_cache: Dict[tuple, Any] = {}

    @abstractmethod
    def _get_client_class(self) -> Type:
        """
        获取具体的客户端类。
        子类必须实现此方法来返回对应的阿里云客户端类。

        Returns:
            客户端类，如 CsClient 或 SlsClient
        """
        pass

    def _get_endpoint_format(self) -> str:
        """
        获取 endpoint 格式字符串。
        默认返回 Container Service 的格式。
        子类可以重写此方法来支持其他服务的 endpoint 格式。

        Returns:
            endpoint 格式字符串，用于 format(region=region)
        """
        return "cs.{region}.aliyuncs.com"

    def _create_client(self, credentials: Optional[Dict[str, Any]] = None):
        """
        根据提供的凭证创建或从缓存中检索阿里云客户端。

        对于 AK/SK 和默认凭证链，客户端将被缓存和重用。
        对于 STS Token，由于其临时性，每次都会创建一个新的客户端。

        Args:
            credentials: 包含认证信息的字典。

        Returns:
            阿里云客户端实例。
        """
        creds = credentials or {}
        ak_id = creds.get("ak_id", "").strip()
        ak_secret = creds.get("ak_secret", "").strip()
        sts_token = creds.get("sts_token", "").strip()
        region = creds.get("region", "").strip() or settings_dict.ALIYUN_REGION

        # 如果存在 STS token，则不使用缓存，因为它会过期
        if sts_token:
            logger.info(
                "STS token provided. Bypassing cache and creating a new client."
            )
            return self._build_new_client(creds)

        # 使用 AK ID 和区域作为缓存键
        # 注意：如果 ak_id 为空，则表示使用默认凭证链（如 RAM 角色）
        cache_key = (ak_id, region)
        if cache_key in self._client_cache:
            logger.info(
                f"Client for key (ak_id: '...{ak_id[-4:] if ak_id else ''}', region: '{region}') found in cache."
            )
            return self._client_cache[cache_key]

        logger.info(
            f"Client for key (ak_id: '...{ak_id[-4:] if ak_id else ''}', region: '{region}') not in cache. Creating a new one."
        )
        new_client = self._build_new_client(creds)
        self._client_cache[cache_key] = new_client
        return new_client

    def _build_new_client(self, credentials: Dict[str, Any]):
        """
        根据给定的凭证构建一个新的客户端实例。
        此私有方法封装了实际的客户端创建逻辑。
        """
        # 提取凭证信息
        ak_id = credentials.get("ak_id", "").strip()
        ak_secret = credentials.get("ak_secret", "").strip()
        sts_token = credentials.get("sts_token", "").strip()
        region = credentials.get("region", "").strip() or settings_dict.ALIYUN_REGION

        logger.info(f"Building new Aliyun client for region: {region}")

        # 创建凭证客户端，按照优先级
        credential_client = None
        try:
            # 1. 最高优先级：检查是否存在 STS Token
            if sts_token:
                if not ak_id or not ak_secret:
                    raise ValueError(
                        "STS token is provided, but access key ID or secret is missing"
                    )

                logger.info("Using STS token credentials")
                credentials_config = CredentialsConfig(
                    type="sts",
                    access_key_id=ak_id,
                    access_key_secret=ak_secret,
                    security_token=sts_token,
                )
                credential_client = CredentialsClient(credentials_config)

            elif ak_id and ak_secret:
                # 2. 第二优先级：使用 AccessKey 凭证
                logger.info("Using AccessKey credentials")
                credentials_config = CredentialsConfig(
                    type="access_key", access_key_id=ak_id, access_key_secret=ak_secret
                )
                credential_client = CredentialsClient(credentials_config)

            else:
                # 3. 最低优先级：回退到默认凭证链
                logger.info("Using default credential chain")
                credential_client = CredentialsClient()

            if credential_client is None:
                raise RuntimeError("Failed to create credential client")

            # 构建 Endpoint
            endpoint = self._get_endpoint_format().format(region=region)

            # 配置 Open API 客户端
            config = openapi_models.Config(
                credential=credential_client,
                endpoint=endpoint,
                region_id=region,
            )

            # 创建客户端
            client_class = self._get_client_class()
            client = client_class(config)
            if client is None:
                raise RuntimeError(f"Failed to create {client_class.__name__}")

            logger.info(f"Successfully built new Aliyun {client_class.__name__}")
            return client

        except Exception as e:
            logger.error(f"Failed to build Aliyun client: {e}", exc_info=True)
            raise RuntimeError(f"Failed to build Aliyun client: {e}") from e
