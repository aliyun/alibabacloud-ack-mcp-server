"""ACK 集群相关工具的纯逻辑：字段过滤、时间解析、任务过滤、分页信息抽取。"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
import json
import re

from loguru import logger

def filter_nodepool(d: Dict[str, Any]) -> Dict[str, Any]:
    """仅保留节点池白名单字段。从 nodepool_info、status 抽取并扁平化。"""
    if not isinstance(d, dict):
        return {}
    ni = d.get("nodepool_info") or d.get("NodepoolInfo") or {}
    st = d.get("status") or d.get("Status") or {}
    ni = ni if isinstance(ni, dict) else {}
    st = st if isinstance(st, dict) else {}
    out = {
        "nodepool_id": ni.get("nodepool_id") or ni.get("nodepoolId") or d.get("nodepool_id") or d.get("nodepoolId"),
        "name": ni.get("name") or d.get("name"),
        "type": ni.get("type") or d.get("type"),
        "is_default": ni.get("is_default") or d.get("is_default"),
        "state": st.get("state") or d.get("state"),
        "total_nodes": st.get("total_nodes") or d.get("total_nodes"),
        "healthy_nodes": st.get("healthy_nodes") or d.get("healthy_nodes"),
        "created": ni.get("created") or d.get("created"),
        "updated": ni.get("updated") or d.get("updated"),
        "region_id": ni.get("region_id") or d.get("region_id"),
    }
    return {k: v for k, v in out.items() if v is not None}


def filter_node(d: Dict[str, Any]) -> Dict[str, Any]:
    """仅保留节点白名单字段。支持 snake_case 与 camelCase。"""
    if not isinstance(d, dict):
        return {}
    map_ = (
        ("instance_id", ("instance_id", "instanceId")),
        ("node_name", ("node_name", "nodeName")),
        ("node_status", ("node_status", "nodeStatus")),
        ("state", ("state",)),
        ("ip_address", ("ip_address", "ipAddress")),
        ("nodepool_id", ("nodepool_id", "nodepoolId")),
        ("instance_type", ("instance_type", "instanceType")),
        ("created", ("created",)),
        ("host_name", ("host_name", "hostName")),
    )
    out = {}
    for out_k, keys in map_:
        v = next((d.get(k) for k in keys if d.get(k) is not None), None)
        if v is not None:
            out[out_k] = v
    return out


def filter_task(d: Dict[str, Any]) -> Dict[str, Any]:
    """保留任务第一层结构，并额外返回 target、parameters、stages。"""
    if not isinstance(d, dict):
        return {}
    
    err = (d.get("error") or {}) if isinstance(d.get("error"), dict) else {}

    out = {
        "task_id": d.get("task_id") or d.get("taskId"),
        "state": d.get("state"),
        "created": d.get("created") or d.get("create_time"),
        "updated": d.get("updated"),
        "task_type": d.get("task_type") or d.get("taskType"),
        "cluster_id": d.get("cluster_id") or d.get("clusterId"),
        "error_code": err.get("code") or err.get("Code"),
        "error_message": err.get("message") or err.get("Message"),
    }
    
    # 获取嵌套的 task 对象
    task_obj = d.get("task")
    task_obj = task_obj if isinstance(task_obj, dict) else {}
    
    # 额外返回 target、parameters、stages（优先从顶阶获取，如果没有则从嵌套的 task 中获取）
    target = task_obj.get("target")
    if target:
        out["target"] = target
    
    parameters = task_obj.get("parameters")
    if parameters:
        out["parameters"] = parameters
    
    stages = task_obj.get("stages")
    if stages:
        out["stages"] = stages
    
    # 过滤掉 None 值
    return {k: v for k, v in out.items() if v is not None}


def parse_task_time(val: Any) -> Optional[int]:
    """将任务时间字段解析为 Unix 秒（UTC）。支持毫秒、秒、ISO 字符串（带时区）。"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v = int(val)
        return v // 1000 if v > 1e12 else v
    if isinstance(val, str):
        try:
            s = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                # 如果没有时区信息，假设是 UTC
                dt = dt.replace(tzinfo=timezone.utc)
            # 转换为 UTC 时间戳
            return int(dt.timestamp())
        except Exception as e:
            logger.warning(f"parse_task_time error: {e}")
    return None


def parse_time_range(
    start_time: Optional[str],
    end_time: Optional[str],
    default_minutes: int = 30,
) -> tuple[Optional[int], Optional[int]]:
    """解析开始、结束时间为 Unix 秒（UTC）。只有指定时才生效，不设置默认值。"""
    start_sec = None
    end_sec = None
    
    if end_time:
        try:
            end_dt_str = str(end_time).replace("Z", "+00:00")
            end_dt = datetime.fromisoformat(end_dt_str)
            # 如果没有时区信息，假设是 UTC
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            end_sec = int(end_dt.timestamp())
        except Exception as e:
            logger.warning(f"parse_time_range error: {e}")
            pass
    
    if start_time:
        try:
            # 使用 end_sec 作为基准，如果没有 end_sec 则使用当前时间
            base_dt = datetime.fromtimestamp(end_sec, tz=timezone.utc) if end_sec else datetime.now(timezone.utc)
            
            s = str(start_time).strip().lower()
            if s.endswith("m"):
                start_dt = base_dt - timedelta(minutes=int(s[:-1]) or default_minutes)
            elif s.endswith("h"):
                start_dt = base_dt - timedelta(hours=int(s[:-1]) or 1)
            elif s.endswith("d"):
                start_dt = base_dt - timedelta(days=int(s[:-1]) or 1)
            else:
                start_dt_str = str(start_time).replace("Z", "+00:00")
                start_dt = datetime.fromisoformat(start_dt_str)
                # 如果没有时区信息，假设是 UTC
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
            start_sec = int(start_dt.timestamp())
        except Exception as e:
            logger.warning(f"parse_time_range error: {e}")
            pass
    
    return start_sec, end_sec


def _task_matches_node_name(t: Dict[str, Any], node_name: str) -> bool:
    """直接对整个 task 对象进行正则匹配 node_name"""
    if not node_name:
        return False
    try:
        # 将整个 task 对象序列化为 JSON 字符串
        task_str = json.dumps(t, ensure_ascii=False)
        # 使用正则表达式匹配 node_name（精确匹配，避免部分匹配）
        # 转义特殊字符，确保精确匹配
        escaped_name = re.escape(str(node_name))
        pattern = rf'"{escaped_name}"'
        return bool(re.search(pattern, task_str))
    except Exception:
        return False


def _task_matches_instance_id(t: Dict[str, Any], instance_id: str) -> bool:
    """直接对整个 task 对象进行正则匹配 instance_id"""
    if not instance_id:
        return False
    try:
        # 将整个 task 对象序列化为 JSON 字符串
        task_str = json.dumps(t, ensure_ascii=False)
        # 使用正则表达式匹配 instance_id（精确匹配，避免部分匹配）
        # 转义特殊字符，确保精确匹配
        escaped_id = re.escape(str(instance_id))
        pattern = rf'"{escaped_id}"'
        return bool(re.search(pattern, task_str))
    except Exception:
        return False


def task_matches_filters(
    t: Dict[str, Any],
    start_sec: Optional[int],
    end_sec: Optional[int],
    instance_id: Optional[str],
    node_name: Optional[str],
) -> bool:
    """判断任务是否通过时间、instance_id、node_name 过滤。node_name 与 instance_id 同时传入时取并集（匹配其一即可）。"""
    if not isinstance(t, dict):
        return False
    ts = parse_task_time(t.get("created"))
    # 如果时间解析成功，检查是否在时间范围内；如果解析失败（ts为None），跳过时间过滤
    # 如果 start_sec 或 end_sec 为 None，则跳过对应的时间过滤
    if ts is not None:
        if start_sec is not None and ts < start_sec:
            return False
        if end_sec is not None and ts > end_sec:
            return False
    # node_name 与 instance_id：仅其一则要求匹配；同时传入时取并集（匹配其一即可）
    match_node_name, match_instance_id = False, False
    if node_name or instance_id:
        if _task_matches_node_name(t, node_name):
            match_node_name = True
        if _task_matches_instance_id(t, instance_id):
            match_instance_id = True
        if not match_node_name and not match_instance_id:
            return False
    return True


def extract_page_info(body: Any, serialize_fn: Callable[[Any], Any]) -> Dict[str, Any]:
    """从 response.body 抽取 page_info 或 page，序列化后返回。支持 body 为 dict（call_api 返回）或对象。"""
    if body is None:
        return {}
    if isinstance(body, dict):
        pi = body.get("page_info") or body.get("pageInfo") or body.get("page")
    else:
        pi = getattr(body, "page_info", None) or getattr(body, "page", None)
    return serialize_fn(pi) if pi else {}
