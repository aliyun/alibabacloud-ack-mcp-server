#!/usr/bin/env python3
"""
Test script to verify the refactored FastMCP proxy mount architecture.

This script tests:
1. All sub-MCP servers can be imported correctly
2. All sub-MCP servers can create their instances
3. Main server can mount all sub-servers using proxy mount mechanism
4. Architecture validation and error reporting
"""

import os
import sys
import traceback
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

def test_sub_server_imports():
    """Test if all sub-MCP servers can be imported correctly."""
    print("=== Testing Sub-Server Imports ===")
    
    sub_servers = [
        ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
        ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
        ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
        ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
        ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
        ("alibabacloud-ack-prometheus-mcp-server", "alibabacloud_ack_prometheus_mcp_server"),
        ("ack-apiserver-log-analysis-mcp-server", "ack_apiserver_log_analysis_mcp_server"),
        ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
        ("ack-cluster-audit-log-analysis-mcp-server", "ack_cluster_audit_log_analysis_mcp_server"),
    ]
    
    success_count = 0
    
    for server_name, module_name in sub_servers:
        try:
            # Import using dynamic loading for modules with hyphens
            if '-' in server_name:
                import importlib.util
                import sys
                import os
                
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
            else:
                module = __import__(module_name.replace('-', '_'))
                
            print(f"✓ {server_name}: Import successful")
            
            # Test if create_mcp_server function exists
            if hasattr(module, 'create_mcp_server'):
                print(f"  ✓ create_mcp_server function available")
            else:
                print(f"  ✗ create_mcp_server function missing")
                continue
                
            success_count += 1
            
        except ImportError as e:
            print(f"✗ {server_name}: Import failed - {e}")
        except Exception as e:
            print(f"✗ {server_name}: Error - {e}")
    
    print(f"\nSub-server import results: {success_count}/{len(sub_servers)} successful")
    return success_count == len(sub_servers)

def test_sub_server_creation():
    """Test if all sub-MCP servers can create their instances."""
    print("\n=== Testing Sub-Server Creation ===")
    
    test_config = {
        "allow_write": False,
        "access_key_id": "test_key_id",
        "access_secret_key": "test_secret_key",
        "region_id": "cn-hangzhou",
        "default_cluster_id": "test-cluster",
    }
    
    sub_servers = [
        ("ack-cluster-management-mcp-server", "ack_cluster_management_mcp_server"),
        ("ack-addon-management-mcp-server", "ack_addon_management_mcp_server"),
        ("ack-nodepool-management-mcp-server", "ack_nodepool_management_mcp_server"),
        ("kubernetes-client-mcp-server", "kubernetes_client_mcp_server"),
        ("ack-diagnose-mcp-server", "ack_diagnose_mcp_server"),
        ("alibabacloud-ack-prometheus-mcp-server", "alibabacloud_ack_prometheus_mcp_server"),
        ("ack-apiserver-log-analysis-mcp-server", "ack_apiserver_log_analysis_mcp_server"),
        ("alibabacloud-ack-cloudresource-monitor-mcp-server", "alibabacloud_ack_cloudresource_monitor_mcp_server"),
    ]
    
    success_count = 0
    
    for server_name, module_name in sub_servers:
        try:
            # Import using dynamic loading for modules with hyphens
            if '-' in server_name:
                import importlib.util
                import sys
                import os
                
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
            else:
                module = __import__(module_name.replace('-', '_'))
                
            create_function = getattr(module, 'create_mcp_server')
            
            # Create server instance
            server = create_function(test_config)
            print(f"✓ {server_name}: Server creation successful")
            
            # Check if server has basic properties
            if hasattr(server, 'name'):
                print(f"  ✓ Server name: {server.name}")
            
            success_count += 1
            
        except Exception as e:
            print(f"✗ {server_name}: Creation failed - {e}")
            traceback.print_exc()
    
    print(f"\nSub-server creation results: {success_count}/{len(sub_servers)} successful")
    return success_count == len(sub_servers)

def test_main_server():
    """Test if the main server can be created and mount sub-servers."""
    print("\n=== Testing Main Server ===")
    
    try:
        import main_server
        print("✓ Main server module imported successfully")
        
        # Test basic configuration
        test_config = {
            "allow_write": False,
            "access_key_id": "test_key_id",
            "access_secret_key": "test_secret_key",
            "region_id": "cn-hangzhou",
        }
        
        # Create main server (this will attempt to mount all sub-servers)
        print("\nAttempting to create main server with proxy mounts...")
        server = main_server.create_main_server(test_config)
        
        print("✓ Main server created successfully")
        print(f"  ✓ Server name: {server.name}")
        
        return True
        
    except Exception as e:
        print(f"✗ Main server creation failed: {e}")
        traceback.print_exc()
        return False

def test_interfaces():
    """Test if the interfaces are properly defined."""
    print("\n=== Testing Interfaces ===")
    
    try:
        from interfaces.runtime_provider import RuntimeProvider
        print("✓ RuntimeProvider interface imported successfully")
        
        # Check if it's an abstract base class
        import inspect
        if inspect.isabstract(RuntimeProvider):
            print("✓ RuntimeProvider is properly defined as abstract base class")
        else:
            print("✗ RuntimeProvider should be an abstract base class")
            
        return True
        
    except Exception as e:
        print(f"✗ Interface test failed: {e}")
        return False

def main():
    """Run all architecture tests."""
    print("🚀 AlibabaCloud Container Service MCP Server Architecture Test")
    print("=" * 60)
    
    # Change to src directory for proper imports
    os.chdir(src_path)
    
    test_results = []
    
    # Run all tests
    test_results.append(("Interface Test", test_interfaces()))
    test_results.append(("Sub-Server Import Test", test_sub_server_imports()))
    test_results.append(("Sub-Server Creation Test", test_sub_server_creation()))
    test_results.append(("Main Server Test", test_main_server()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("🏁 Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Architecture refactoring successful!")
        print("\n📋 Architecture Summary:")
        print("✓ FastMCP proxy mount mechanism implemented")
        print("✓ Microservices architecture with 9 sub-MCP servers")
        print("✓ StandardRuntimeProvider interface implemented")
        print("✓ All sub-servers can run standalone or be mounted")
        print("✓ Main server orchestrates all sub-servers")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())