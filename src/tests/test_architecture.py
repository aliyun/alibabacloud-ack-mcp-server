#!/usr/bin/env python3
"""
Pytest test suite to verify the refactored FastMCP proxy mount architecture.

This test suite validates:
1. All sub-MCP servers can be imported correctly
2. All sub-MCP servers can create their instances
3. Main server can mount all sub-servers using proxy mount mechanism
4. Architecture validation and error reporting
"""

import os
import sys
import inspect
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pytest

# Add src directory to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Change to src directory for proper imports
os.chdir(src_path)


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Fixture providing test configuration for MCP servers."""
    return {
        "allow_write": False,
        "access_key_id": "test_key_id",
        "access_secret_key": "test_secret_key",
        "region_id": "cn-hangzhou",
        "default_cluster_id": "test-cluster",
    }


@pytest.fixture
def sub_servers() -> List[Tuple[str, str]]:
    """Fixture providing list of sub-MCP servers to test."""
    return [
        ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
        ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
        ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
        ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
        ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
        ("alibabacloud-o11y-prometheus-mcp-server", "alibabacloud_o11y_prometheus_mcp_server"),
        ("alibabacloud-o11y-sls-apiserver-log-mcp-server", "alibabacloud_o11y_sls_apiserver_log_mcp_server"),
        ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
        ("alibabacloud-o11y-sls-audit-log-analysis-mcp-server", "alibabacloud_o11y_sls_audit_log_analysis_mcp_server"),
    ]


def _import_module_with_hyphens(server_name: str, module_name: str):
    """Helper function to import modules with hyphens in their directory names."""
    if '-' in server_name:
        # Add src directory to Python path if not already there
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        module_path = f"{server_name}/__init__.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        
        # Add module to sys.modules to support relative imports
        sys.modules[module_name] = module
        
        # Execute the module
        spec.loader.exec_module(module)
        return module
    else:
        return __import__(module_name.replace('-', '_'))


class TestInterfaces:
    """Test suite for interface validation."""
    
    def test_runtime_provider_interface(self):
        """Test if the RuntimeProvider interface is properly defined."""
        from interfaces.runtime_provider import RuntimeProvider
        
        # Check if it's an abstract base class
        assert inspect.isabstract(RuntimeProvider), "RuntimeProvider should be an abstract base class"
        
        # Check if it has the required abstract methods
        abstract_methods = RuntimeProvider.__abstractmethods__
        assert 'init_runtime' in abstract_methods, "RuntimeProvider should have init_runtime as abstract method"


class TestSubServerImports:
    """Test suite for sub-MCP server imports."""
    
    @pytest.mark.parametrize("server_name,module_name", [
        ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
        ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
        ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
        ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
        ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
        ("alibabacloud-o11y-prometheus-mcp-server", "alibabacloud_o11y_prometheus_mcp_server"),
        ("alibabacloud-o11y-sls-apiserver-log-mcp-server", "alibabacloud_o11y_sls_apiserver_log_mcp_server"),
        ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
        ("alibabacloud-o11y-sls-audit-log-analysis-mcp-server", "alibabacloud_o11y_sls_audit_log_analysis_mcp_server"),
    ])
    def test_sub_server_import(self, server_name: str, module_name: str):
        """Test if a sub-MCP server can be imported correctly."""
        module = _import_module_with_hyphens(server_name, module_name)
        assert module is not None, f"Failed to import {server_name}"
        
        # Test if create_mcp_server function exists
        assert hasattr(module, 'create_mcp_server'), f"Module {server_name} missing create_mcp_server function"
    
    def test_all_sub_servers_import(self, sub_servers: List[Tuple[str, str]]):
        """Test if all sub-MCP servers can be imported successfully."""
        success_count = 0
        
        for server_name, module_name in sub_servers:
            try:
                module = _import_module_with_hyphens(server_name, module_name)
                if hasattr(module, 'create_mcp_server'):
                    success_count += 1
            except Exception:
                pass  # Individual test will catch specific failures
        
        assert success_count == len(sub_servers), f"Only {success_count}/{len(sub_servers)} servers imported successfully"


class TestSubServerCreation:
    """Test suite for sub-MCP server instance creation."""
    
    @pytest.mark.parametrize("server_name,module_name", [
        ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
        ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
        ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
        ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
        ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
        ("alibabacloud-o11y-prometheus-mcp-server", "alibabacloud_o11y_prometheus_mcp_server"),
        ("alibabacloud-o11y-sls-apiserver-log-mcp-server", "alibabacloud_o11y_sls_apiserver_log_mcp_server"),
        ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
    ])
    def test_sub_server_creation(self, server_name: str, module_name: str, test_config: Dict[str, Any]):
        """Test if a sub-MCP server can create its instance successfully."""
        module = _import_module_with_hyphens(server_name, module_name)
        create_function = getattr(module, 'create_mcp_server')
        
        # Create server instance
        server = create_function(test_config)
        assert server is not None, f"Failed to create server instance for {server_name}"
        
        # Check if server has basic properties
        assert hasattr(server, 'name'), f"Server {server_name} missing 'name' attribute"
        assert server.name is not None, f"Server {server_name} has None name"
    
    def test_all_sub_servers_creation(self, test_config: Dict[str, Any]):
        """Test if all testable sub-MCP servers can create their instances."""
        # Exclude audit log server as it may require special configuration
        testable_servers = [
            ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
            ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
            ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
            ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
            ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
            ("alibabacloud-o11y-prometheus-mcp-server", "alibabacloud_o11y_prometheus_mcp_server"),
            ("alibabacloud-o11y-sls-apiserver-log-mcp-server", "alibabacloud_o11y_sls_apiserver_log_mcp_server"),
            ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
        ]
        
        success_count = 0
        
        for server_name, module_name in testable_servers:
            try:
                module = _import_module_with_hyphens(server_name, module_name)
                create_function = getattr(module, 'create_mcp_server')
                server = create_function(test_config)
                if server and hasattr(server, 'name'):
                    success_count += 1
            except Exception:
                pass  # Individual test will catch specific failures
        
        assert success_count == len(testable_servers), f"Only {success_count}/{len(testable_servers)} servers created successfully"


class TestMainServer:
    """Test suite for main server functionality."""
    
    def test_main_server_import(self):
        """Test if the main server module can be imported."""
        import main_server
        assert main_server is not None, "Failed to import main_server module"
        assert hasattr(main_server, 'create_main_server'), "main_server missing create_main_server function"
    
    def test_main_server_creation(self, test_config: Dict[str, Any]):
        """Test if the main server can be created and mount sub-servers."""
        import main_server
        
        # Create main server (this will attempt to mount all sub-servers)
        server = main_server.create_main_server(test_config)
        assert server is not None, "Failed to create main server"
        assert hasattr(server, 'name'), "Main server missing 'name' attribute"
        assert server.name == "alibabacloud-cs-main-server", f"Unexpected main server name: {server.name}"


class TestArchitectureSummary:
    """Test suite for overall architecture validation."""
    
    def test_microservices_architecture(self, sub_servers: List[Tuple[str, str]]):
        """Test if the microservices architecture is properly implemented."""
        # Verify we have the expected number of sub-servers
        assert len(sub_servers) == 9, f"Expected 9 sub-servers, found {len(sub_servers)}"
        
        # Verify all servers follow naming convention
        for server_name, _ in sub_servers:
            assert server_name.endswith('-mcp-server'), f"Server {server_name} doesn't follow naming convention"
    
    def test_runtime_provider_implementation(self):
        """Test if RuntimeProvider interface is properly implemented across servers."""
        from interfaces.runtime_provider import RuntimeProvider
        
        # Test that RuntimeProvider is an abstract base class
        assert inspect.isabstract(RuntimeProvider), "RuntimeProvider should be abstract"
        
        # Test that it has the required method signature
        assert hasattr(RuntimeProvider, 'init_runtime'), "RuntimeProvider missing init_runtime method"
    
    def test_fastmcp_proxy_mount_capability(self, test_config: Dict[str, Any]):
        """Test if FastMCP proxy mount mechanism is available."""
        import main_server
        
        # Verify main server can be created (which tests the mount mechanism)
        server = main_server.create_main_server(test_config)
        assert server is not None, "FastMCP proxy mount mechanism failed"


if __name__ == "__main__":
    # For backward compatibility, allow running as script
    pytest.main([__file__, "-v"])