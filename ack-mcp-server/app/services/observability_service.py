"""
封装与阿里云可观测性（SLS）API 的所有交互。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from alibabacloud_sls20201230.client import Client as SlsClient
from alibabacloud_sls20201230 import models as sls_models
from alibabacloud_tea_util import models as util_models

from app.config import get_logger, get_settings
from app.services.base import BaseAliyunService

logger = get_logger()
settings = get_settings()


class CMSSPLContainer:
    """
    一个辅助类，用于存储和格式化执行 PromQL 查询所需的特定 SPL/SQL 模板。
    """

    def __init__(self):
        self.spls = {}
        self.spls[
            "raw-promql-template"
        ] = r"""
.set "sql.session.velox_support_row_constructor_enabled" = 'true';
.set "sql.session.presto_velox_mix_run_not_check_linked_agg_enabled" = 'true';
.set "sql.session.presto_velox_mix_run_support_complex_type_enabled" = 'true';
.set "sql.session.velox_sanity_limit_enabled" = 'false';
.metricstore with(promql_query='<PROMQL>',range='1m')| extend latest_ts = element_at(__ts__,cardinality(__ts__)), latest_val = element_at(__value__,cardinality(__value__))
|  stats arr_ts = array_agg(__ts__), arr_val = array_agg(__value__), title_agg = array_agg(json_format(cast(__labels__ as json))), anomalies_score_series = array_agg(array[0.0]), anomalies_type_series = array_agg(array['']), cnt = count(*), latest_ts = array_agg(latest_ts), latest_val = array_agg(latest_val)
| extend cluster_res = cluster(arr_val,'kmeans') | extend params = concat('{"n_col": ', cast(cnt as varchar), ',"subplot":true}')
| extend image = series_anomalies_plot(arr_ts, arr_val, anomalies_score_series, anomalies_type_series, title_agg, params)| project title_agg,cnt,latest_ts,latest_val,image
"""

    def get_spl(self, key) -> str:
        return self.spls.get(key, "Key not found")


class ObservabilityService(BaseAliyunService):
    """
    一个封装了阿里云日志服务（SLS）客户端操作的服务类。
    继承自 BaseAliyunService，重写了 endpoint 格式以适配 SLS 服务。
    """

    def __init__(self):
        """
        初始化可观测性服务。
        """
        super().__init__()
        self._spl_container = CMSSPLContainer()

    def _get_client_class(self) -> Type[SlsClient]:
        """
        返回日志服务的客户端类。

        Returns:
            SlsClient: 阿里云日志服务客户端类
        """
        return SlsClient

    def _get_endpoint_format(self) -> str:
        """
        返回 SLS 服务的 endpoint 格式。

        Returns:
            SLS endpoint 格式字符串
        """
        return "{region}.log.aliyuncs.com"

    def translate_text_to_promql(
        self,
        text: str,
        project: str,
        metric_store: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        将自然语言文本转换为 PromQL 查询语句。
        """
        creds = credentials or {}
        target_region = creds.get("region", settings.ALIYUN_REGION)
        logger.info(
            f"Translating text to PromQL for project='{project}' in region '{target_region}'"
        )

        # AI Tool API is in a fixed region 'cn-shanghai'.
        # We create a client specifically for it, while passing the target region as a parameter.
        ai_tool_creds = creds.copy()
        ai_tool_creds["region"] = "cn-shanghai"
        sls_client = self._create_client(ai_tool_creds)

        params: dict[str, Any] = {
            "project": project,
            "metricstore": metric_store,
            "sys.query": text,
        }
        request = sls_models.CallAiToolsRequest(
            tool_name="text_to_promql",
            params=params,
            # The region of the target metric store must be passed in the request body.
            region_id=target_region
        )
        runtime = util_models.RuntimeOptions(
            read_timeout=60000, connect_timeout=60000)

        try:
            response = sls_client.call_ai_tools_with_options(
                request=request, headers={}, runtime=runtime
            )
            data = response.body
            if not isinstance(data, str):
                raise ValueError(
                    f"Failed to get a valid PromQL query from AI tool, response: {data}")
            if "------answer------\n" in data:
                data = data.split("------answer------\n")[1]
            logger.info(f"Successfully translated text to PromQL: {data}")
            return data.strip()
        except Exception as e:
            logger.error(
                f"Failed to call CMS AI tool 'text_to_promql': {e}", exc_info=True)
            raise

    def execute_promql_query(
        self,
        project: str,
        metric_store: str,
        query: str,
        from_timestamp: int,
        to_timestamp: int,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行 PromQL 查询。
        """
        logger.info(
            f"Executing PromQL query for project='{project}', metric_store='{metric_store}'"
        )
        sls_client = self._create_client(credentials)

        formatted_query = self._spl_container.get_spl(
            "raw-promql-template").replace("<PROMQL>", query)

        request = sls_models.GetLogsRequest(
            query=formatted_query,
            from_=from_timestamp,
            to=to_timestamp,
        )
        runtime = util_models.RuntimeOptions(
            read_timeout=60000, connect_timeout=60000)

        try:
            response = sls_client.get_logs_with_options(
                project, metric_store, request, headers={}, runtime=runtime
            )
            response_body: List[Dict[str, Any]] = response.body or []
            logger.info("Successfully executed PromQL query.")
            return response_body
        except Exception as e:
            logger.error(f"Failed to execute PromQL query: {e}", exc_info=True)
            raise

    def _get_current_time(self) -> Dict[str, Any]:
        """获取当前时间信息"""
        now = datetime.now()
        return {
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "current_timestamp": int(now.timestamp()),
        }

    def _append_current_time(self, text: str) -> str:
        """为文本附加当前时间信息"""
        time_info = self._get_current_time()
        return f"当前时间: {time_info['current_time']}, 问题:{text}"

    def translate_text_to_sql(
        self,
        text: str,
        project: str,
        logstore: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        将自然语言文本转换为 SLS SQL 查询语句。
        """
        creds = credentials or {}
        target_region = creds.get("region", settings.ALIYUN_REGION)
        logger.info(
            f"Translating text to SQL for project='{project}' in region '{target_region}'"
        )

        # AI Tool API is in a fixed region 'cn-shanghai'.
        ai_tool_creds = creds.copy()
        ai_tool_creds["region"] = "cn-shanghai"
        sls_client = self._create_client(ai_tool_creds)

        params: dict[str, Any] = {
            "project": project,
            "logstore": logstore,
            "sys.query": self._append_current_time(text),
        }
        request = sls_models.CallAiToolsRequest(
            tool_name="text_to_sql",
            params=params,
            region_id=target_region
        )
        runtime = util_models.RuntimeOptions(
            read_timeout=60000, connect_timeout=60000)

        try:
            response = sls_client.call_ai_tools_with_options(
                request=request, headers={}, runtime=runtime
            )
            data = response.body
            if not isinstance(data, str):
                raise ValueError(
                    f"Failed to get a valid SQL query from AI tool, response: {data}")
            if "------answer------\n" in data:
                data = data.split("------answer------\n")[1]
            logger.info(f"Successfully translated text to SQL: {data}")
            return data.strip()
        except Exception as e:
            logger.error(
                f"Failed to call AI tool 'text_to_sql': {e}", exc_info=True)
            raise

    def execute_sql(
        self,
        project: str,
        logstore: str,
        query: str,
        from_timestamp: int,
        to_timestamp: int,
        limit: int = 100,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行 SLS SQL 查询。
        """
        logger.info(
            f"Executing SQL query for project='{project}', logstore='{logstore}'"
        )
        sls_client = self._create_client(credentials)

        request = sls_models.GetLogsRequest(
            query=query,
            from_=from_timestamp,
            to=to_timestamp,
            line=limit,
        )
        runtime = util_models.RuntimeOptions(
            read_timeout=60000, connect_timeout=60000)

        try:
            response = sls_client.get_logs_with_options(
                project, logstore, request, headers={}, runtime=runtime
            )
            response_body: List[Dict[str, Any]] = response.body or []
            return response_body
        except Exception as e:
            logger.error(f"Failed to execute SQL query: {e}", exc_info=True)
            raise

    def diagnose_query(
        self,
        query: str,
        error_message: str,
        project: str,
        logstore: str,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        诊断 SLS 查询语句。
        """
        creds = credentials or {}
        target_region = creds.get("region", settings.ALIYUN_REGION)
        logger.info(
            f"Diagnosing query for project='{project}' in region '{target_region}'"
        )

        # AI Tool API is in a fixed region 'cn-shanghai'.
        ai_tool_creds = creds.copy()
        ai_tool_creds["region"] = "cn-shanghai"
        sls_client = self._create_client(ai_tool_creds)

        query_to_diagnose = self._append_current_time(
            f"帮我诊断下 {query} 的日志查询语句,错误信息为 {error_message}"
        )

        params: dict[str, Any] = {
            "project": project,
            "logstore": logstore,
            "sys.query": query_to_diagnose,
        }
        request = sls_models.CallAiToolsRequest(
            tool_name="diagnosis_sql",
            params=params,
            region_id=target_region
        )
        runtime = util_models.RuntimeOptions(
            read_timeout=60000, connect_timeout=60000)

        try:
            response = sls_client.call_ai_tools_with_options(
                request=request, headers={}, runtime=runtime
            )
            data = response.body
            if not isinstance(data, str):
                raise ValueError(
                    f"Failed to get a valid diagnosis from AI tool, response: {data}")
            if "------answer------\n" in data:
                data = data.split("------answer------\n")[1]
            logger.info("Successfully diagnosed query.")
            return data.strip()
        except Exception as e:
            logger.error(
                f"Failed to call AI tool 'diagnosis_sql': {e}", exc_info=True)
            raise
