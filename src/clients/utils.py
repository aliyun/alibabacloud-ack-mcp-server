"""Common utility functions for Alibaba Cloud clients."""


def serialize_sdk_object(obj):
    """序列化阿里云 SDK 对象为可 JSON 的字典。

    Args:
        obj: 需要序列化的对象，可以是阿里云 SDK 对象、字典、列表等

    Returns:
        序列化后的 Python 原生数据类型（dict、list、str、int 等）

    Examples:
        >>> from alibabacloud_cs20151215 import models
        >>> response = client.describe_cluster(cluster_id)
        >>> serialized = serialize_sdk_object(response.body)
        >>> print(json.dumps(serialized, indent=2))
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [serialize_sdk_object(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize_sdk_object(v) for k, v in obj.items()}
    try:
        if hasattr(obj, "to_map"):
            return obj.to_map()
        if hasattr(obj, "__dict__"):
            return serialize_sdk_object(obj.__dict__)
    except Exception:
        pass
    return str(obj)
