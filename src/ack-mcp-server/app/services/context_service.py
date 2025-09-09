#!/usr/bin/env python3
"""
Service for providing cluster and observability context.
"""

import json
import os
from typing import Any, Dict, List, Optional

from aliyunsdkcs.request.v20151215 import (
    DescribeClusterDetailRequest,
    DescribeClustersV1Request,
)
from aliyunsdksts.request.v20150401 import GetCallerIdentityRequest
from app.config import get_logger
from app.models import ClusterDetail, ClusterInfo, ErrorContext, ObservabilityContext
from app.services.base import BaseService
from kubernetes import config
from tenacity import retry, stop_after_attempt, wait_fixed

logger = get_logger()


class ContextService(BaseService):
    """
    Service for fetching ACK cluster context and observability info.
    """

    def __init__(self, credentials: Dict[str, Any]):
        super().__init__(credentials)
        self._account_id: Optional[str] = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _get_account_id(self) -> str:
        """
        Get Account ID from Alibaba Cloud STS service. Caches the result.
        Retries up to 3 times with a 2-second wait between attempts.
        """
        if self._account_id is not None:
            return self._account_id

        logger.info("Attempting to get Account ID from Alibaba Cloud STS...")
        try:
            client = self.get_client(region_id="cn-hangzhou")
            request = GetCallerIdentityRequest.GetCallerIdentityRequest()
            request.set_accept_format("json")
            response = client.do_action_with_exception(request)
            if not response:
                logger.error("Failed to get a response from Alibaba Cloud STS")
                raise Exception("Failed to get a response from Alibaba Cloud STS")

            result = json.loads(response)
            account_id = result.get("AccountId")
            if not account_id:
                logger.error("Unable to extract Account ID from STS response")
                raise Exception("Unable to extract Account ID from response")

            logger.info(f"Successfully retrieved Account ID: {account_id}")
            self._account_id = account_id
            return str(self._account_id)
        except Exception as e:
            logger.error(f"Failed to get Account ID. Error: {e}")
            raise

    async def get_observability_context(
        self, cluster_id: str
    ) -> ObservabilityContext | ErrorContext:
        """
        Retrieve observability context for a specified Alibaba Cloud ACK cluster.
        It assumes the region_id is always provided in the credentials.
        """
        logger.info(f"Building observability context for cluster_id: {cluster_id}")

        # The region is expected to be in the credentials, injected by the middleware.
        region_id = self.credentials.get("region")
        if not region_id:
            logger.error(
                f"Region ID not found in credentials for cluster {cluster_id}. It must be provided via 'X-Aliyun-Region' header."
            )
            return ErrorContext(
                error="MissingRegionID",
                message="Region ID must be provided via 'X-Aliyun-Region' header.",
            )

        logger.info(f"Using Region ID '{region_id}' from credentials.")

        account_id = self._get_account_id()

        if not account_id:
            logger.error(f"Failed to retrieve Account ID for cluster {cluster_id}")
            return ErrorContext(
                error="FailedToRetrieveAccountID",
                message="Failed to retrieve Account ID",
            )

        return ObservabilityContext(
            cluster_id=cluster_id,
            region_id=region_id,
            sls_project=f"k8s-log-{cluster_id}",
            sls_log_store="k8s-event",
            arms_project=f"workspace-default-cms-{account_id}-{region_id}",
            arms_metric_store=f"aliyun-prom-{cluster_id}",
        )
