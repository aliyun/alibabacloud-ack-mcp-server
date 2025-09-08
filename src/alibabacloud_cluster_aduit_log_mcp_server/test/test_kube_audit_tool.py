"""Unit tests for KubeAuditTool implementation."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from alibabacloud_cluster_aduit_log_mcp_server.toolkits.kube_aduit_tool import KubeAuditTool


class TestKubeAuditTool:
    """Test cases for KubeAuditTool."""

    def test_init_without_server(self):
        """Test initialization without server."""
        tool = KubeAuditTool()
        
        assert tool.server is None
        assert tool.resource_mapping is not None
        assert tool.provider_registry is not None
        assert "alibaba-sls" in tool.provider_registry

    def test_init_with_server(self):
        """Test initialization with server."""
        mock_server = Mock()
        tool = KubeAuditTool(server=mock_server)
        
        assert tool.server == mock_server

    def test_resource_mapping(self):
        """Test resource mapping functionality."""
        tool = KubeAuditTool()
        
        # Test common mappings
        assert tool.resource_mapping["pod"] == "pods"
        assert tool.resource_mapping["deployment"] == "deployments"
        assert tool.resource_mapping["service"] == "services"
        assert tool.resource_mapping["svc"] == "services"
        assert tool.resource_mapping["configmap"] == "configmaps"
        assert tool.resource_mapping["cm"] == "configmaps"
        assert tool.resource_mapping["secret"] == "secrets"
        assert tool.resource_mapping["sec"] == "secrets"

    def test_normalize_params_defaults(self):
        """Test parameter normalization with defaults."""
        tool = KubeAuditTool()
        
        params = {}
        normalized = tool._normalize_params(params)
        
        assert normalized["cluster_name"] == "default"
        assert normalized["start_time"] is not None
        assert normalized["end_time"] is not None
        assert normalized["limit"] == 10

    def test_normalize_params_limit_validation(self):
        """Test parameter normalization with limit validation."""
        tool = KubeAuditTool()
        
        # Test negative limit
        params = {"limit": -5}
        normalized = tool._normalize_params(params)
        assert normalized["limit"] == 10
        
        # Test zero limit
        params = {"limit": 0}
        normalized = tool._normalize_params(params)
        assert normalized["limit"] == 10
        
        # Test excessive limit
        params = {"limit": 200}
        normalized = tool._normalize_params(params)
        assert normalized["limit"] == 100
        
        # Test valid limit
        params = {"limit": 50}
        normalized = tool._normalize_params(params)
        assert normalized["limit"] == 50

    def test_normalize_params_resource_types_string(self):
        """Test parameter normalization with string resource types."""
        tool = KubeAuditTool()
        
        params = {"resource_types": "pod"}
        normalized = tool._normalize_params(params)
        
        assert normalized["resource_types"] == ["pods"]

    def test_normalize_params_resource_types_list(self):
        """Test parameter normalization with list resource types."""
        tool = KubeAuditTool()
        
        params = {"resource_types": ["pod", "deployment", "service"]}
        normalized = tool._normalize_params(params)
        
        assert normalized["resource_types"] == ["pods", "deployments", "services"]

    def test_normalize_params_resource_types_mixed(self):
        """Test parameter normalization with mixed resource types."""
        tool = KubeAuditTool()
        
        params = {"resource_types": ["pod", "unknown-resource", "deployment"]}
        normalized = tool._normalize_params(params)
        
        assert "pods" in normalized["resource_types"]
        assert "unknown-resource" in normalized["resource_types"]
        assert "deployments" in normalized["resource_types"]

    def test_parse_time_iso_format(self):
        """Test time parsing with ISO format."""
        tool = KubeAuditTool()
        
        time_str = "2024-01-01T10:00:00Z"
        parsed_time = tool._parse_time(time_str)
        
        expected = datetime(2024, 1, 1, 10, 0, 0)
        assert parsed_time == expected

    def test_parse_time_relative_hours(self):
        """Test time parsing with relative hours."""
        tool = KubeAuditTool()
        
        time_str = "2h"
        parsed_time = tool._parse_time(time_str)
        
        # Should be approximately 2 hours ago
        now = datetime.utcnow()
        expected = now - timedelta(hours=2)
        assert abs((parsed_time - expected).total_seconds()) < 60  # Within 1 minute

    def test_parse_time_relative_days(self):
        """Test time parsing with relative days."""
        tool = KubeAuditTool()
        
        time_str = "3d"
        parsed_time = tool._parse_time(time_str)
        
        # Should be approximately 3 days ago
        now = datetime.utcnow()
        expected = now - timedelta(days=3)
        assert abs((parsed_time - expected).total_seconds()) < 60  # Within 1 minute

    def test_parse_time_relative_weeks(self):
        """Test time parsing with relative weeks."""
        tool = KubeAuditTool()
        
        time_str = "1w"
        parsed_time = tool._parse_time(time_str)
        
        # Should be approximately 1 week ago
        now = datetime.utcnow()
        expected = now - timedelta(weeks=1)
        assert abs((parsed_time - expected).total_seconds()) < 60  # Within 1 minute

    def test_parse_time_invalid_format(self):
        """Test time parsing with invalid format."""
        tool = KubeAuditTool()
        
        time_str = "invalid-time"
        parsed_time = tool._parse_time(time_str)
        
        # Should return current time
        now = datetime.utcnow()
        assert abs((parsed_time - now).total_seconds()) < 60  # Within 1 minute

    def test_parse_time_empty_string(self):
        """Test time parsing with empty string."""
        tool = KubeAuditTool()
        
        time_str = ""
        parsed_time = tool._parse_time(time_str)
        
        # Should return current time
        now = datetime.utcnow()
        assert abs((parsed_time - now).total_seconds()) < 60  # Within 1 minute

    def test_get_provider_from_context_success(self, mock_context):
        """Test getting provider from context successfully."""
        tool = KubeAuditTool()
        
        provider = tool._get_provider_from_context(mock_context, "test-cluster")
        
        assert provider is not None

    def test_get_provider_from_context_default_cluster(self, mock_context):
        """Test getting provider from context with default cluster."""
        tool = KubeAuditTool()
        
        provider = tool._get_provider_from_context(mock_context, "default")
        
        assert provider is not None

    def test_get_provider_from_context_fallback(self, mock_context):
        """Test getting provider from context with fallback."""
        tool = KubeAuditTool()
        
        # Test with non-existent cluster
        provider = tool._get_provider_from_context(mock_context, "non-existent")
        
        # Should fallback to any available provider
        assert provider is not None

    def test_get_provider_from_context_no_context(self):
        """Test getting provider from context without context."""
        tool = KubeAuditTool()
        mock_context = Mock()
        mock_context.lifespan_context = None
        
        provider = tool._get_provider_from_context(mock_context)
        
        assert provider is None

    def test_get_provider_from_context_exception(self):
        """Test getting provider from context with exception."""
        tool = KubeAuditTool()
        mock_context = Mock()
        mock_context.lifespan_context = {"providers": "invalid"}  # Invalid format
        
        provider = tool._get_provider_from_context(mock_context)
        
        assert provider is None

    @pytest.mark.asyncio
    async def test_query_audit_log_success(self, mock_context, mock_query_params):
        """Test successful audit log query."""
        tool = KubeAuditTool()
        
        # Mock provider
        mock_provider = Mock()
        mock_provider.query_audit_log = AsyncMock(return_value={
            "entries": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "user": {"username": "test-user"},
                    "verb": "get",
                    "objectRef": {
                        "namespace": "default",
                        "resource": "pods",
                        "name": "test-pod"
                    },
                    "responseStatus": {"code": 200}
                }
            ]
        })
        
        with patch.object(tool, '_get_provider_from_context', return_value=mock_provider):
            result = await tool._register_tools()
            
            # Get the registered function
            query_func = tool.server.tool.call_args[0][0]
            
            # Call the function
            audit_result = await query_func(
                mock_context,
                namespace="default",
                verbs=["get"],
                resource_types=["pods"],
                resource_name="test-pod",
                user="test-user",
                start_time="1h",
                end_time=None,
                limit=10,
                cluster_name="test-cluster"
            )
            
            assert "params" in audit_result
            assert "logs" in audit_result
            assert len(audit_result["logs"]) == 1
            assert audit_result["logs"][0]["user"] == "test-user"
            assert audit_result["logs"][0]["verb"] == "get"

    @pytest.mark.asyncio
    async def test_query_audit_log_no_provider(self, mock_context, mock_query_params):
        """Test audit log query with no provider."""
        tool = KubeAuditTool()
        
        with patch.object(tool, '_get_provider_from_context', return_value=None):
            result = await tool._register_tools()
            
            # Get the registered function
            query_func = tool.server.tool.call_args[0][0]
            
            # Call the function
            audit_result = await query_func(
                mock_context,
                namespace="default",
                verbs=["get"],
                resource_types=["pods"],
                resource_name="test-pod",
                user="test-user",
                start_time="1h",
                end_time=None,
                limit=10,
                cluster_name="test-cluster"
            )
            
            assert "error" in audit_result
            assert "no provider found" in audit_result["error"]

    @pytest.mark.asyncio
    async def test_query_audit_log_provider_error(self, mock_context, mock_query_params):
        """Test audit log query with provider error."""
        tool = KubeAuditTool()
        
        # Mock provider that raises exception
        mock_provider = Mock()
        mock_provider.query_audit_log = AsyncMock(side_effect=Exception("Provider error"))
        
        with patch.object(tool, '_get_provider_from_context', return_value=mock_provider):
            result = await tool._register_tools()
            
            # Get the registered function
            query_func = tool.server.tool.call_args[0][0]
            
            # Call the function
            audit_result = await query_func(
                mock_context,
                namespace="default",
                verbs=["get"],
                resource_types=["pods"],
                resource_name="test-pod",
                user="test-user",
                start_time="1h",
                end_time=None,
                limit=10,
                cluster_name="test-cluster"
            )
            
            assert "error" in audit_result
            assert "Provider error" in audit_result["error"]

    def test_register_tools_without_server(self):
        """Test tool registration without server."""
        tool = KubeAuditTool()
        
        # Should not raise exception
        tool._register_tools()

    def test_register_tools_with_server(self):
        """Test tool registration with server."""
        mock_server = Mock()
        tool = KubeAuditTool(server=mock_server)
        
        tool._register_tools()
        
        # Should call server.tool decorator
        mock_server.tool.assert_called_once()

    def test_provider_registry(self):
        """Test provider registry contains expected providers."""
        tool = KubeAuditTool()
        
        from alibabacloud_cluster_aduit_log_mcp_server.provider.provider import (
            AlibabaSLSProvider,
        )
        
        assert tool.provider_registry["alibaba-sls"] == AlibabaSLSProvider
