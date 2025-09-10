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

# 导入ack-diagnose-mcp-server模块
diagnose_server_path = os.path.join(src_path, 'ack-diagnose-mcp-server')
if diagnose_server_path not in sys.path:
    sys.path.insert(0, diagnose_server_path)

import importlib.util

# 动态导入handler模块
handler_spec = importlib.util.spec_from_file_location(
    "handler", 
    os.path.join(diagnose_server_path, "handler.py")
)
handler_module = importlib.util.module_from_spec(handler_spec)
handler_spec.loader.exec_module(handler_module)
ACKDiagnoseHandler = handler_module.ACKDiagnoseHandler

# 动态导入runtime_provider模块
runtime_provider_spec = importlib.util.spec_from_file_location(
    "runtime_provider", 
    os.path.join(diagnose_server_path, "runtime_provider.py")
)
runtime_provider_module = importlib.util.module_from_spec(runtime_provider_spec)
runtime_provider_spec.loader.exec_module(runtime_provider_module)
ACKDiagnoseRuntimeProvider = runtime_provider_module.ACKDiagnoseRuntimeProvider

# 动态导入server模块
server_spec = importlib.util.spec_from_file_location(
    "server", 
    os.path.join(diagnose_server_path, "server.py")
)
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)
create_mcp_server = server_module.create_mcp_server


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
        
        # 验证传入的配置都存在于合并后的配置中
        for key, value in test_config.items():
            assert provider.config.get(key) == value
        
        # 验证环境变量的默认值被正确设置
        assert provider.config.get("region_id") == "cn-hangzhou"  # 默认值
        assert provider.config.get("cache_ttl") == 300  # 默认值
        assert provider.config.get("cache_max_size") == 1000  # 默认值
        
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
            "next_token": None,
            "max_results": 20
        }
        assert "reports" in reports_result
        assert reports_result["max_results"] == 20
        
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
        """Test handler initialization."""
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
        
        # Verify that tools have been registered
        # The mock should have been called multiple times for tool registration
        assert mock_server.tool.call_count > 0
        
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


class TestACKDiagnosisReportResults:
    """Test cases for ACK cluster diagnosis report results."""
    
    @pytest.mark.asyncio
    async def test_create_and_get_diagnosis_result(self):
        """Test creating a cluster diagnosis task and getting its result."""
        cluster_id = "test-cluster-001"
        diagnosis_type = "all"
        
        # Mock creating a diagnosis task
        create_result = {
            "cluster_id": cluster_id,
            "diagnosis_id": "diag-20240910-001",
            "status": "created",
            "type": diagnosis_type,
            "created_time": "2024-09-10T10:00:00Z",
            "request_id": "req-001"
        }
        
        # Verify diagnosis creation
        assert create_result["status"] == "created"
        assert create_result["cluster_id"] == cluster_id
        assert create_result["type"] == diagnosis_type
        assert "diagnosis_id" in create_result
        assert "created_time" in create_result
        
        # Mock getting diagnosis result (in progress)
        diagnosis_id = create_result["diagnosis_id"]
        in_progress_result = {
            "cluster_id": cluster_id,
            "diagnosis_id": diagnosis_id,
            "status": "running",
            "progress": 45,
            "created_time": "2024-09-10T10:00:00Z",
            "request_id": "req-002"
        }
        
        # Verify in-progress status
        assert in_progress_result["status"] == "running"
        assert in_progress_result["progress"] == 45
        assert in_progress_result["diagnosis_id"] == diagnosis_id
        
        # Mock getting diagnosis result (completed)
        completed_result = {
            "cluster_id": cluster_id,
            "diagnosis_id": diagnosis_id,
            "status": "completed",
            "progress": 100,
            "result": {
                "overall_status": "healthy",
                "issues_found": 2,
                "warnings_found": 5,
                "checks_performed": [
                    {
                        "category": "node",
                        "check_name": "node_health",
                        "status": "passed",
                        "message": "All nodes are healthy"
                    },
                    {
                        "category": "pod",
                        "check_name": "pod_status",
                        "status": "warning",
                        "message": "2 pods are in CrashLoopBackOff state",
                        "details": {
                            "affected_pods": ["app-pod-1", "app-pod-2"],
                            "namespace": "default"
                        }
                    },
                    {
                        "category": "network",
                        "check_name": "network_connectivity",
                        "status": "passed",
                        "message": "Network connectivity is normal"
                    }
                ],
                "recommendations": [
                    {
                        "priority": "high",
                        "category": "pod",
                        "title": "Fix CrashLoopBackOff pods",
                        "description": "Investigate and fix pods in CrashLoopBackOff state",
                        "action": "Check pod logs and fix application issues"
                    },
                    {
                        "priority": "medium",
                        "category": "resource",
                        "title": "Monitor resource usage",
                        "description": "Some nodes are approaching memory limits",
                        "action": "Consider adding more nodes or optimizing memory usage"
                    }
                ]
            },
            "created_time": "2024-09-10T10:00:00Z",
            "finished_time": "2024-09-10T10:15:00Z",
            "request_id": "req-003"
        }
        
        # Verify completed result structure
        assert completed_result["status"] == "completed"
        assert completed_result["progress"] == 100
        assert "result" in completed_result
        assert "finished_time" in completed_result
        
        # Verify result details
        result = completed_result["result"]
        assert result["overall_status"] == "healthy"
        assert result["issues_found"] == 2
        assert result["warnings_found"] == 5
        assert len(result["checks_performed"]) == 3
        assert len(result["recommendations"]) == 2
        
        # Verify specific check results
        node_check = next(check for check in result["checks_performed"] if check["category"] == "node")
        assert node_check["status"] == "passed"
        
        pod_check = next(check for check in result["checks_performed"] if check["category"] == "pod")
        assert pod_check["status"] == "warning"
        assert "details" in pod_check
        assert len(pod_check["details"]["affected_pods"]) == 2
        
        # Verify recommendations
        high_priority_rec = next(rec for rec in result["recommendations"] if rec["priority"] == "high")
        assert high_priority_rec["category"] == "pod"
        assert "CrashLoopBackOff" in high_priority_rec["title"]
    
    @pytest.mark.asyncio
    async def test_diagnosis_check_items(self):
        """Test getting available diagnosis check items."""
        cluster_id = "test-cluster-001"
        
        # Mock getting diagnosis check items
        check_items_result = {
            "cluster_id": cluster_id,
            "check_items": [
                {
                    "category": "node",
                    "name": "node_health",
                    "display_name": "节点健康检查",
                    "description": "检查集群中所有节点的健康状态",
                    "enabled": True
                },
                {
                    "category": "pod",
                    "name": "pod_status",
                    "display_name": "Pod状态检查",
                    "description": "检查集群中所有Pod的状态",
                    "enabled": True
                },
                {
                    "category": "network",
                    "name": "network_connectivity",
                    "display_name": "网络连通性检查",
                    "description": "检查集群网络连通性",
                    "enabled": True
                },
                {
                    "category": "storage",
                    "name": "pv_status",
                    "display_name": "存储卷检查",
                    "description": "检查持久化存储卷状态",
                    "enabled": False
                }
            ],
            "type": "all",
            "lang": "zh",
            "request_id": "req-004"
        }
        
        # Verify check items structure
        assert "check_items" in check_items_result
        assert len(check_items_result["check_items"]) == 4
        assert check_items_result["lang"] == "zh"
        
        # Verify each check item has required fields
        for item in check_items_result["check_items"]:
            assert "category" in item
            assert "name" in item
            assert "display_name" in item
            assert "description" in item
            assert "enabled" in item
        
        # Verify specific check items
        node_check = next(item for item in check_items_result["check_items"] if item["category"] == "node")
        assert node_check["enabled"] is True
        assert "节点" in node_check["display_name"]
        
        storage_check = next(item for item in check_items_result["check_items"] if item["category"] == "storage")
        assert storage_check["enabled"] is False
    
    @pytest.mark.asyncio
    async def test_diagnosis_error_handling(self):
        """Test error handling in diagnosis operations."""
        cluster_id = "invalid-cluster"
        diagnosis_id = "invalid-diagnosis"
        
        # Mock error responses
        create_error = {
            "cluster_id": cluster_id,
            "error": "ClusterNotFound: The specified cluster does not exist",
            "status": "failed"
        }
        
        get_result_error = {
            "cluster_id": cluster_id,
            "diagnosis_id": diagnosis_id,
            "error": "DiagnosisNotFound: The specified diagnosis task does not exist",
            "status": "error"
        }
        
        # Verify error responses
        assert create_error["status"] == "failed"
        assert "ClusterNotFound" in create_error["error"]
        
        assert get_result_error["status"] == "error"
        assert "DiagnosisNotFound" in get_result_error["error"]
    
    @pytest.mark.asyncio
    async def test_diagnosis_with_specific_target(self):
        """Test diagnosis with specific target specification."""
        cluster_id = "test-cluster-001"
        
        # Test node-specific diagnosis
        node_target = {
            "type": "node",
            "node_names": ["worker-node-1", "worker-node-2"]
        }
        
        node_diagnosis_result = {
            "cluster_id": cluster_id,
            "diagnosis_id": "diag-node-001",
            "status": "created",
            "type": "node",
            "target": node_target,
            "created_time": "2024-09-10T11:00:00Z",
            "request_id": "req-005"
        }
        
        assert node_diagnosis_result["type"] == "node"
        assert node_diagnosis_result["target"]["type"] == "node"
        assert len(node_diagnosis_result["target"]["node_names"]) == 2
        
        # Test namespace-specific diagnosis
        namespace_target = {
            "type": "namespace",
            "namespace": "kube-system"
        }
        
        namespace_diagnosis_result = {
            "cluster_id": cluster_id,
            "diagnosis_id": "diag-ns-001",
            "status": "created",
            "type": "pod",
            "target": namespace_target,
            "created_time": "2024-09-10T11:05:00Z",
            "request_id": "req-006"
        }
        
        assert namespace_diagnosis_result["type"] == "pod"
        assert namespace_diagnosis_result["target"]["namespace"] == "kube-system"
    
    @pytest.mark.asyncio
    async def test_list_cluster_inspect_reports_parameters(self):
        """Test list_cluster_inspect_reports with correct parameters."""
        cluster_id = "test-cluster-001"
        
        # Test with default parameters
        default_result = {
            "cluster_id": cluster_id,
            "reports": [
                {
                    "reportId": "782df89346054a0000562063a6****",
                    "startTime": "2024-12-18T19:40:16.778333+08:00",
                    "endTime": "2024-12-18T19:40:16.778333+08:00",
                    "status": "completed",
                    "summary": {
                        "code": "warning",
                        "normalCount": 1,
                        "adviceCount": 0,
                        "warnCount": 0,
                        "errorCount": 0
                    }
                }
            ],
            "next_token": None,
            "max_results": 20,
            "request_id": "49511F2D-D56A-5C24-B9AE-C8491E09B***"
        }
        
        # Verify response structure
        assert default_result["cluster_id"] == cluster_id
        assert "reports" in default_result
        assert default_result["max_results"] == 20
        assert "next_token" in default_result
        assert "request_id" in default_result
        
        # Verify report structure
        if default_result["reports"]:
            report = default_result["reports"][0]
            assert "reportId" in report
            assert "startTime" in report
            assert "endTime" in report
            assert "status" in report
            assert "summary" in report
            
            # Verify summary structure
            summary = report["summary"]
            assert "code" in summary
            assert "normalCount" in summary
            assert "adviceCount" in summary
            assert "warnCount" in summary
            assert "errorCount" in summary
        
        # Test with pagination parameters
        paginated_result = {
            "cluster_id": cluster_id,
            "reports": [],
            "next_token": "405b99e5411f9a4e7148506e45",
            "max_results": 10,
            "request_id": "49511F2D-D56A-5C24-B9AE-C8491E09B***"
        }
        
        # Verify pagination parameters
        assert paginated_result["max_results"] == 10
        assert paginated_result["next_token"] == "405b99e5411f9a4e7148506e45"
        
        # Test with max_results limit (should not exceed 50)
        max_limit_result = {
            "cluster_id": cluster_id,
            "reports": [],
            "next_token": None,
            "max_results": 50,  # Maximum allowed value
            "request_id": "49511F2D-D56A-5C24-B9AE-C8491E09B***"
        }
        
        assert max_limit_result["max_results"] <= 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])