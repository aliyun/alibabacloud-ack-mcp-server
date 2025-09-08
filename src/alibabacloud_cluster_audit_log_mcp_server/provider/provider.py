"""Provider implementation for Kubernetes audit log querying."""

from abc import ABC, abstractmethod
from typing import Dict, Any
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)


class Provider(ABC):
    """Abstract base class for audit log providers."""

    @abstractmethod
    def query_audit_log(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query audit logs with the given parameters.
        
        Args:
            params: Dictionary of query parameters
            
        Returns:
            Dictionary containing query results
        """
        pass


class AlibabaSLSProvider(Provider):
    """Alibaba Cloud SLS provider for audit log querying."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the provider with configuration.
        
        Args:
            config: Configuration dictionary containing endpoint, project, logstore, etc.
        """
        self.endpoint = config.get("endpoint")
        self.project = config.get("project")
        self.logstore = config.get("logstore")
        self.region = config.get("region")
        self.access_key_id = config.get("access_key_id")
        self.access_key_secret = config.get("access_key_secret")

        # Validate required configuration
        self._validate_config()

        # Initialize SLS client
        self._client = None
        self._initialize_client()

    def _validate_config(self):
        """Validate the configuration parameters."""
        required_fields = ["endpoint", "project", "logstore", "region"]
        missing_fields = [field for field in required_fields if not getattr(self, field)]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {missing_fields}")

        # Validate endpoint format
        if not self.endpoint.startswith(("http://", "https://")):
            self.endpoint = f"https://{self.endpoint}"

    def _initialize_client(self):
        """Initialize the SLS client."""
        try:
            from aliyun.log import LogClient

            # Initialize the client with correct parameters
            if self.access_key_id and self.access_key_secret:
                self._client = LogClient(
                    endpoint=self.endpoint,
                    accessKeyId=self.access_key_id,
                    accessKey=self.access_key_secret
                )
            else:
                raise ValueError("Access Key ID and Access Key Secret are required.")

            logger.info(f"SLS client initialized successfully for project: {self.project}")
        except Exception as e:
            logger.error(f"Failed to initialize SLS client: {e}")
            raise e

    def query_audit_log(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query audit logs from Alibaba Cloud SLS (synchronous version).
        
        Args:
            params: Dictionary of query parameters
            
        Returns:
            Dictionary containing query results
        """
        # Build query string based on params
        query = self._build_query(params)

        # Parse time parameters
        start_time, end_time = self._parse_time_params(params)

        try:
            if not self._client:
                raise RuntimeError("SLS client not properly initialized")

            # Use real SLS client - 直接调用同步方法
            return self._query_logs(query, start_time, end_time, params)

        except Exception as e:
            logger.error(f"Failed to query audit logs: {e}")
            return {
                "provider_query": query,
                "entries": [],
                "total": 0,
                "params": params,
                "error": str(e)
            }

    def _parse_time_params(self, params: Dict[str, Any]) -> tuple[int, int]:
        """Parse time parameters to Unix timestamps.
        
        Args:
            params: Query parameters
            
        Returns:
            Tuple of (start_time, end_time) as Unix timestamps
        """
        from datetime import datetime, timedelta

        # Parse start time
        start_time_str = params.get("start_time", "24h")
        if isinstance(start_time_str, str):
            if start_time_str.endswith('h'):
                hours = int(start_time_str[:-1])
                start_time = datetime.utcnow() - timedelta(hours=hours)
            elif start_time_str.endswith('d'):
                days = int(start_time_str[:-1])
                start_time = datetime.utcnow() - timedelta(days=days)
            else:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                except ValueError:
                    start_time = datetime.utcnow() - timedelta(hours=24)
        else:
            start_time = datetime.utcnow() - timedelta(hours=24)

        # Parse end time
        end_time_str = params.get("end_time")
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                end_time = datetime.utcnow()
        else:
            end_time = datetime.utcnow()

        return int(start_time.timestamp()), int(end_time.timestamp())

    def _query_logs(self, query: str, start_time: int, end_time: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query using real SLS client with get_log_all_v2 API."""
        try:
            # 直接调用SLS API - 使用get_log方法
            response = self._client.get_log(
                project=self.project,
                logstore=self.logstore,
                from_time=start_time,
                to_time=end_time,
                query=query,  # 查询条件
                size=params.get("limit", 10),
                offset=0,  # 从第一条开始
                reverse=False  # 按时间正序
            )

            # Parse response - get_log 返回的是 GetLogsResponse 对象
            entries = []

            # 从response.body获取日志数据
            try:
                if hasattr(response, 'body') and response.body and isinstance(response.body,
                                                                              dict) and 'data' in response.body:
                    for log_entry in response.body['data']:
                        # 解析日志条目，字段都是字符串格式的JSON
                        log_data = {}

                        # 解析各个字段 - 根据真实SLS数据结构，包含所有字段

                        # 解析JSON字符串字段
                        if 'user' in log_entry:
                            try:
                                user_data = json.loads(log_entry['user'])
                                log_data['user'] = user_data
                            except json.JSONDecodeError:
                                log_data['user'] = {"username": log_entry['user']}

                        if 'objectRef' in log_entry:
                            try:
                                object_ref_data = json.loads(log_entry['objectRef'])
                                log_data['objectRef'] = object_ref_data
                            except json.JSONDecodeError:
                                log_data['objectRef'] = {"resource": log_entry['objectRef']}

                        if 'responseStatus' in log_entry:
                            try:
                                response_status_data = json.loads(log_entry['responseStatus'])
                                log_data['responseStatus'] = response_status_data
                            except json.JSONDecodeError:
                                log_data['responseStatus'] = {"code": 0}

                        if 'annotations' in log_entry:
                            try:
                                annotations_data = json.loads(log_entry['annotations'])
                                log_data['annotations'] = annotations_data
                            except json.JSONDecodeError:
                                log_data['annotations'] = log_entry['annotations']

                        if 'sourceIPs' in log_entry:
                            try:
                                source_ips_data = json.loads(log_entry['sourceIPs'])
                                log_data['sourceIPs'] = source_ips_data
                            except json.JSONDecodeError:
                                log_data['sourceIPs'] = [log_entry['sourceIPs']]

                        if 'requestObject' in log_entry:
                            try:
                                request_object_data = json.loads(log_entry['requestObject'])
                                log_data['requestObject'] = request_object_data
                            except json.JSONDecodeError:
                                log_data['requestObject'] = log_entry['requestObject']

                        if 'responseObject' in log_entry:
                            try:
                                response_object_data = json.loads(log_entry['responseObject'])
                                log_data['responseObject'] = response_object_data
                            except json.JSONDecodeError:
                                log_data['responseObject'] = log_entry['responseObject']

                        # 添加所有其他字段
                        log_data['verb'] = log_entry.get('verb', '')
                        log_data['timestamp'] = log_entry.get('requestReceivedTimestamp', '')
                        log_data['kind'] = log_entry.get('kind', '')
                        log_data['apiVersion'] = log_entry.get('apiVersion', '')
                        log_data['auditID'] = log_entry.get('auditID', '')
                        log_data['level'] = log_entry.get('level', '')
                        log_data['requestURI'] = log_entry.get('requestURI', '')
                        log_data['userAgent'] = log_entry.get('userAgent', '')
                        log_data['stage'] = log_entry.get('stage', '')
                        log_data['stageTimestamp'] = log_entry.get('stageTimestamp', '')

                        entries.append(log_data)
            except Exception as e:
                logger.warning(f"Failed to parse response body: {e}")

            return {
                "provider_query": query,
                "entries": entries,
                "total": len(entries),
                "params": params
            }

        except Exception as e:
            logger.error(f"SLS query failed: {e}")
            raise

    def _build_query(self, params: Dict[str, Any]) -> str:
        """Build SLS query string from parameters.
        
        Args:
            params: Dictionary of query parameters
            
        Returns:
            Query string for SLS
        """
        query = "*"

        if params.get("user") and params["user"] != "*":
            query += f" and user.username: {params['user']}"

        if params.get("namespace") and params["namespace"] != "*":
            query += f" and objectRef.namespace: {params['namespace']}"

        if params.get("verbs") and len(params["verbs"]) > 0:
            verbs = [f"verb: \"{verb}\"" for verb in params["verbs"]]
            query += f" and ({' or '.join(verbs)})"

        if params.get("resource_types") and len(params["resource_types"]) > 0:
            resource_types = [f"objectRef.resource: \"{rt}\"" for rt in params["resource_types"]]
            query += f" and ({' or '.join(resource_types)})"

        if params.get("resource_name") and params["resource_name"] != "*":
            query += f" and objectRef.name: {params['resource_name']}"

        return query


