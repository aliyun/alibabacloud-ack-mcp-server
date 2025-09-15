#!/usr/bin/env python3
"""
验证ACK节点池管理MCP服务器的测试覆盖率脚本。

此脚本检查handler.py中的所有@self.server.tool装饰的方法
是否在测试文件中都有对应的测试用例。
"""

import re
import os
import sys
from typing import Set, List


def extract_tool_methods_from_handler() -> Set[str]:
    """从handler.py文件中提取所有的tool方法名称。"""
    # 获取当前脚本的绝对路径，然后构建handler.py的路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    handler_file = os.path.join(os.path.dirname(script_dir), "handler.py")
    tool_methods = set()
    
    if not os.path.exists(handler_file):
        print(f"❌ 未找到 {handler_file} 文件")
        return tool_methods
    
    with open(handler_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有@self.server.tool装饰器后的name参数
    pattern = r'@self\.server\.tool\(\s*name="([^"]+)"'
    matches = re.findall(pattern, content)
    
    for match in matches:
        tool_methods.add(match)
        print(f"✓ 发现tool方法: {match}")
    
    return tool_methods


def extract_test_methods_from_test_file() -> Set[str]:
    """从测试文件中提取所有测试的tool方法。"""
    # 获取当前脚本所在目录中的测试文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tested_methods = set()
    
    # 检查多个可能的测试文件
    test_files = [
        "test_tool_methods.py",
        "test_nodepool_management.py", 
        "test_basic_functionality.py",
        "test_api_parameters.py"
    ]
    
    for test_file_name in test_files:
        test_file = os.path.join(script_dir, test_file_name)
        
        if not os.path.exists(test_file):
            continue
            
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 从测试函数中查找tool方法调用
        # 查找类似 tools["method_name"] 的模式
        pattern = r'tools\["([^"]+)"\]'
        matches = re.findall(pattern, content)
        
        for match in matches:
            tested_methods.add(match)
            print(f"✓ 发现测试方法: {match} (在 {test_file_name})")
        
        # 同时查找直接的方法名称引用（对于我们的测试文件）
        # 查找类似 'name' == 'method_name' 的模式
        pattern2 = r"call\.kwargs\.get\('name'\)\s*==\s*'([^']+)'"
        matches2 = re.findall(pattern2, content)
        
        for match in matches2:
            tested_methods.add(match)
            print(f"✓ 发现测试方法: {match} (在 {test_file_name})")
        
        # 查找我们新的模式: mock_server._registered_tools.get('tool_name')
        pattern3 = r"mock_server\._registered_tools\.get\('([^']+)'\)"
        matches3 = re.findall(pattern3, content)
        
        for match in matches3:
            tested_methods.add(match)
            print(f"✓ 发现测试方法: {match} (在 {test_file_name})")
        
        # 查找测试函数名称模式: test_method_name
        pattern4 = r"def test_([a-zA-Z_]+)\("
        matches4 = re.findall(pattern4, content)
        
        # 尝试从测试函数名推断被测试的工具名
        tool_name_mapping = {
            "describe_cluster_node_pools": "describe_cluster_node_pools",
            "describe_cluster_node_pool_detail": "describe_cluster_node_pool_detail", 
            "scale_nodepool": "scale_nodepool",
            "remove_nodepool_nodes": "remove_nodepool_nodes",
            "create_cluster_node_pool": "create_cluster_node_pool",
            "delete_cluster_nodepool": "delete_cluster_nodepool",
            "modify_cluster_node_pool": "modify_cluster_node_pool",
            "modify_nodepool_node_config": "modify_nodepool_node_config",
            "upgrade_cluster_nodepool": "upgrade_cluster_nodepool",
            "describe_nodepool_vuls": "describe_nodepool_vuls",
            "fix_nodepool_vuls": "fix_nodepool_vuls",
            "repair_cluster_node_pool": "repair_cluster_node_pool",
            "sync_cluster_node_pool": "sync_cluster_node_pool",
            "attach_instances_to_node_pool": "attach_instances_to_node_pool",
            "create_autoscaling_config": "create_autoscaling_config",
            "describe_cluster_attach_scripts": "describe_cluster_attach_scripts"
        }
        
        for test_name in matches4:
            if test_name in tool_name_mapping:
                tool_name = tool_name_mapping[test_name]
                tested_methods.add(tool_name)
                print(f"✓ 发现测试方法: {tool_name} (从测试函数 test_{test_name} 推断, 在 {test_file_name})")
    
    return tested_methods


def main():
    """主函数：验证测试覆盖率。"""
    print("🔍 ACK节点池管理MCP服务器测试覆盖率验证")
    print("=" * 50)
    
    # 提取handler中的tool方法
    print("\n📋 扫描handler.py中的tool方法...")
    tool_methods = extract_tool_methods_from_handler()
    
    # 提取测试文件中测试的方法
    print("\n📋 扫描测试文件中的测试...")
    tested_methods = extract_test_methods_from_test_file()
    
    print(f"\n找到的tool方法: {tested_methods}")
    
    print("\n" + "=" * 50)
    print("📊 测试覆盖率分析")
    print("=" * 50)
    
    # 检查覆盖率
    total_methods = len(tool_methods)
    tested_count = len(tested_methods & tool_methods)
    
    print(f"总tool方法数: {total_methods}")
    print(f"已测试方法数: {tested_count}")
    
    if total_methods > 0:
        coverage_rate = (tested_count / total_methods) * 100
        print(f"测试覆盖率: {coverage_rate:.1f}%")
    
    # 显示详细结果
    print("\n✅ 已测试的方法:")
    for method in sorted(tested_methods & tool_methods):
        print(f"  • {method}")
    
    # 显示未测试的方法
    untested = tool_methods - tested_methods
    if untested:
        print("\n❌ 未测试的方法:")
        for method in sorted(untested):
            print(f"  • {method}")
    else:
        print("\n🎉 所有tool方法都已有测试覆盖！")
    
    # 显示多余的测试
    extra_tests = tested_methods - tool_methods
    if extra_tests:
        print("\n⚠️  额外的测试方法（可能是已删除的tool方法）:")
        for method in sorted(extra_tests):
            print(f"  • {method}")
    
    print("\n" + "=" * 50)
    
    # 根据实际发现的方法动态显示
    if tool_methods:
        print("📋 发现的tool方法列表:")
        for i, method in enumerate(sorted(tool_methods), 1):
            status = "✅" if method in tested_methods else "❌"
            print(f"  {i:2d}. {status} {method}")
    else:
        print("⚠️  未发现任何tool方法，请检查handler.py文件")
    
    # 返回状态码
    if untested:
        print(f"\n❌ 发现 {len(untested)} 个未测试的方法")
        sys.exit(1)
    else:
        print("\n✅ 所有方法都已有测试覆盖")
        sys.exit(0)


if __name__ == "__main__":
    main()