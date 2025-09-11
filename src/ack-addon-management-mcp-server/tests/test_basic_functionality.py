#!/usr/bin/env python3
"""Simple test script to verify the addon management functionality."""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock

# Add the current directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_basic_functionality():
    """Test basic functionality of the handler."""
    print("Testing ACK Addon Management Handler...")
    
    try:
        from handler import ACKAddonManagementHandler
        from server import create_mcp_server
        print("✅ Successfully imported modules")
    except Exception as e:
        print(f"❌ Failed to import modules: {e}")
        return False
    
    # Test server creation
    try:
        config = {
            "allow_write": True,
            "access_key_id": "test_key",
            "access_key_secret": "test_secret",
            "region_id": "cn-hangzhou"
        }
        server = create_mcp_server(config)
        print("✅ Successfully created MCP server")
    except Exception as e:
        print(f"❌ Failed to create server: {e}")
        return False
    
    # Test handler initialization
    try:
        mock_server = Mock()
        tools = {}
        
        def mock_tool(**kwargs):
            def decorator(func):
                tool_name = kwargs.get('name', func.__name__)
                tools[tool_name] = func
                return func
            return decorator
        
        mock_server.tool = mock_tool
        handler = ACKAddonManagementHandler(mock_server, allow_write=True)
        
        print(f"✅ Successfully created handler with {len(tools)} tools")
        print(f"   Tools: {list(tools.keys())}")
        
        # Expected tools
        expected_tools = {
            "list_addons",
            "list_cluster_addon_instances", 
            "get_cluster_addon_instance",
            "describe_addon",
            "install_cluster_addons",
            "uninstall_cluster_addons",
            "modify_cluster_addon",
            "upgrade_cluster_addons"
        }
        
        actual_tools = set(tools.keys())
        if actual_tools == expected_tools:
            print("✅ All expected tools are registered")
        else:
            missing = expected_tools - actual_tools
            extra = actual_tools - expected_tools
            if missing:
                print(f"❌ Missing tools: {missing}")
            if extra:
                print(f"⚠️  Extra tools: {extra}")
                
    except Exception as e:
        print(f"❌ Failed to create handler: {e}")
        return False
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_basic_functionality())
    if result:
        print("\n🎉 All basic tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)