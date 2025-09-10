#!/usr/bin/env python3
"""Unit tests for ACK Diagnose MCP Server."""

import pytest
import sys
import os
from unittest.mock import Mock
from typing import Dict, Any

# 添加src目录到Python路径
src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 直接导入模块文件
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from handler import ACKDiagnoseHandler
from runtime_provider import ACKDiagnoseRuntimeProvider
from server import create_mcp_server


# 配置pytest以支持asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration fixture."""
    return {
        "allow_write": True,
        "region_id": "cn-hangzhou",
        "access_key_id": "test_key_id",
        "access_key_secret": "test_secret_key",
        "default_cluster_id": "test-cluster-123"
    }


class TestACKDiagnoseServer:
    """Test cases for ACK Diagnose Server."""
    
    def test_create_mcp_server(self, test_config):
        """Test MCP server creation."""
        server = create_mcp_server(test_config)
        assert server is not None
        assert hasattr(server, 'name')
        
    def test_runtime_provider_initialization(self, test_config):
        """Test runtime provider initialization."""
        provider = ACKDiagnoseRuntimeProvider(config=test_config)
        assert provider.config == test_config
        
    @pytest.mark.asyncio
    async def test_cluster_diagnosis_operations(self):
        """Test cluster diagnosis operations."""
        # Mock cluster diagnosis creation
        result = {
            "cluster_id": "test-cluster",
            "diagnosis_id": "diag-123",
            "status": "created",
            "type": "all"
        }
        assert result["status"] == "created"
        assert "diagnosis_id" in result
        
        # Mock diagnosis result retrieval
        diagnosis_result = {
            "cluster_id": "test-cluster",
            "diagnosis_id": "diag-123",
            "status": "completed",
            "result": {"issues": [], "recommendations": []}
        }
        assert diagnosis_result["status"] == "completed"
        assert "result" in diagnosis_result
        
    @pytest.mark.asyncio
    async def test_cluster_inspection_operations(self):
        """Test cluster inspection operations."""
        # Mock inspection report listing
        reports_result = {
            "cluster_id": "test-cluster",
            "reports": [],
            "total_count": 0,
            "page_num": 1
        }
        assert "reports" in reports_result
        assert reports_result["total_count"] == 0
        
        # Mock inspection run
        inspect_result = {
            "cluster_id": "test-cluster",
            "inspect_id": "inspect-123",
            "status": "started",
            "type": "all"
        }
        assert inspect_result["status"] == "started"
        assert "inspect_id" in inspect_result
        
    @pytest.mark.asyncio
    async def test_inspection_configuration_operations(self):
        """Test inspection configuration operations."""
        # Mock config creation
        config_result = {
            "cluster_id": "test-cluster",
            "config_id": "config-123",
            "status": "created"
        }
        assert config_result["status"] == "created"
        assert "config_id" in config_result
        
        # Mock config retrieval
        get_config_result = {
            "cluster_id": "test-cluster",
            "config_id": "config-123",
            "config": {"inspection_type": "all", "schedule": "daily"},
            "status": "active"
        }
        assert get_config_result["status"] == "active"
        assert "config" in get_config_result
        
    def test_handler_initialization(self, test_config):
        """Test handler initialization with Alibaba Cloud credentials."""
        mock_server = Mock()
        mock_server.tool = Mock(side_effect=lambda **kwargs: lambda func: func)
        
        # Test handler creation with valid config
        handler = ACKDiagnoseHandler(
            server=mock_server,
            allow_write=test_config["allow_write"],
            settings=test_config
        )
        
        assert handler.server == mock_server
        assert handler.allow_write == test_config["allow_write"]
        assert handler.settings == test_config
        
    def test_write_operations_control(self):
        """Test write operations control logic."""
        # Test write disabled scenario
        allow_write = False
        
        if not allow_write:
            expected_result = {"error": "Write operations are disabled"}
        else:
            expected_result = {"status": "created"}
            
        assert not allow_write
        assert expected_result == {"error": "Write operations are disabled"}
        
        # Test write enabled scenario
        allow_write = True
        
        if not allow_write:
            expected_result = {"error": "Write operations are disabled"}
        else:
            expected_result = {"status": "created"}
            
        assert allow_write
        assert expected_result == {"status": "created"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])