#!/usr/bin/env python3
"""Simple test to verify the addon management handler."""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    try:
        from handler import ACKAddonManagementHandler
        print("✅ handler module imported successfully")
    except Exception as e:
        print(f"❌ Failed to import handler: {e}")
        return False
    
    try:
        from runtime_provider import ACKAddonManagementRuntimeProvider
        print("✅ runtime_provider module imported successfully")
    except Exception as e:
        print(f"❌ Failed to import runtime_provider: {e}")
        return False
    
    try:
        from server import create_mcp_server
        print("✅ server module imported successfully")
    except Exception as e:
        print(f"❌ Failed to import server: {e}")
        return False
    
    return True

def test_tool_methods():
    """Test that tool methods are correctly defined."""
    try:
        from handler import ACKAddonManagementHandler
        import inspect
        
        # 检查handler类是否存在
        if not hasattr(ACKAddonManagementHandler, '_register_tools'):
            print("❌ _register_tools method not found")
            return False
            
        print("✅ All imports and basic structure verified")
        return True
        
    except Exception as e:
        print(f"❌ Error testing tool methods: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing ACK Addon Management MCP Server...")
    
    if test_imports() and test_tool_methods():
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)