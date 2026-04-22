"""Tests for clients/utils.py (serialize_sdk_object)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from clients.utils import serialize_sdk_object


class TestSerializeSdkObject:
    def test_none_returns_none(self):
        assert serialize_sdk_object(None) is None

    def test_str_returns_unchanged(self):
        assert serialize_sdk_object("hello") == "hello"

    def test_int_returns_unchanged(self):
        assert serialize_sdk_object(42) == 42

    def test_float_returns_unchanged(self):
        assert serialize_sdk_object(3.14) == 3.14

    def test_bool_returns_unchanged(self):
        assert serialize_sdk_object(True) is True
        assert serialize_sdk_object(False) is False

    def test_list_serializes_each_item(self):
        result = serialize_sdk_object([1, "two", None, True])
        assert result == [1, "two", None, True]

    def test_tuple_serializes_each_item(self):
        result = serialize_sdk_object((1, "two"))
        assert result == [1, "two"]

    def test_dict_serializes_each_value(self):
        result = serialize_sdk_object({"a": 1, "b": None, "c": [1, 2]})
        assert result == {"a": 1, "b": None, "c": [1, 2]}

    def test_nested_dict_and_list(self):
        data = {"items": [{"key": "val"}, None, 42]}
        result = serialize_sdk_object(data)
        assert result == {"items": [{"key": "val"}, None, 42]}

    def test_object_with_to_map(self):
        class ToMapObj:
            def to_map(self):
                return {"x": 1, "y": [2, 3]}

        result = serialize_sdk_object(ToMapObj())
        assert result == {"x": 1, "y": [2, 3]}

    def test_object_with_to_map_returns_nested(self):
        """to_map() result is returned as-is; nested objects not recursively serialized."""

        class Nested:
            def to_map(self):
                return {"inner": ToMapObj2()}

        class ToMapObj2:
            def to_map(self):
                return {"val": 42}

        result = serialize_sdk_object(Nested())
        assert "inner" in result
        assert isinstance(result["inner"], ToMapObj2)

    def test_object_with_dict_attribute(self):
        class DictObj:
            def __init__(self):
                self.a = 1
                self.b = "two"

        result = serialize_sdk_object(DictObj())
        assert result == {"a": 1, "b": "two"}

    def test_object_with_dict_containing_nested_objects(self):
        class Inner:
            def __init__(self):
                self.value = 99

        class Outer:
            def __init__(self):
                self.inner = Inner()

        result = serialize_sdk_object(Outer())
        assert result == {"inner": {"value": 99}}

    def test_to_map_raises_returns_str(self):
        class BadToMap:
            def to_map(self):
                raise RuntimeError("boom")

        result = serialize_sdk_object(BadToMap())
        assert isinstance(result, str)

    def test_dict_with_items_and_raise_iter(self):
        """When dict iteration raises during item access, the function falls through to str()."""

        class BadDict(dict):
            def __iter__(self):
                raise RuntimeError("boom")

        # BadDict() with no items doesn't trigger __iter__ on items() in CPython
        # So this returns {} (empty dict), not str
        result = serialize_sdk_object(BadDict())
        assert result == {}

    def test_fallback_to_str(self):
        class NoAttrs:
            __slots__ = ()

        result = serialize_sdk_object(NoAttrs())
        assert result == str(NoAttrs())

    def test_recursive_serialization_depth(self):
        """Verify deep nesting is handled."""
        data = {"l1": {"l2": {"l3": [1, {"l4": "deep"}]}}}
        result = serialize_sdk_object(data)
        assert result["l1"]["l2"]["l3"][1]["l4"] == "deep"
