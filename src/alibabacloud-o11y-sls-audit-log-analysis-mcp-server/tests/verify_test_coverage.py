#!/usr/bin/env python3
"""
验证阿里云可观测性SLS审计日志分析MCP服务器的测试覆盖率脚本。

此脚本检查toolkits中的所有tool方法是否在测试文件中都有对应的测试用例。
由于这个服务器的架构稍有不同，tool方法可能在toolkits目录中。
"""

import re
import os
import sys
from typing import Set, List


def extract_tool_methods_from_toolkits() -> Set[str]:
    """从toolkits目录中提取所有的tool方法名称。"""
    # 获取当前脚本的绝对路径，然后构建toolkits目录的路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    toolkits_dir = os.path.join(parent_dir, "toolkits")
    tool_methods = set()
    
    if not os.path.exists(toolkits_dir):
        print(f"❌ 未找到 {toolkits_dir} 目录")
        return tool_methods
    
    # 检查toolkits目录中的所有Python文件
    for filename in os.listdir(toolkits_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            file_path = os.path.join(toolkits_dir, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找所有@server.tool装饰器后的name参数
            pattern = r'@server\.tool\(\s*name="([^"]+)"'
            matches = re.findall(pattern, content)
            
            for match in matches:
                tool_methods.add(match)
                print(f"✓ 发现tool方法: {match} (在 {filename})")
    
    return tool_methods


def extract_test_methods_from_test_file() -> Set[str]:
    """从测试文件中提取所有测试的tool方法。"""
    # 获取当前脚本所在目录中的测试文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tested_methods = set()
    
    # 检查多个可能的测试文件
    test_files = [
        "test_tool_methods.py",
        "test_kube_audit_tool.py", 
        "test_lifespan_manager.py",
        "test_basic_functionality.py"
    ]
    
    for test_file_name in test_files:
        test_file = os.path.join(script_dir, test_file_name)
        
        if not os.path.exists(test_file):
            continue
            
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 从测试函数中查找tool方法调用
        # 查找类似 tools["method_name"] 或直接方法调用的模式
        patterns = [
            r'tools\["([^"]+)"\]',
            r'test_([a-z_]+_tool)',  # 测试方法名模式
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                tested_methods.add(match)
    
    return tested_methods


def main():
    """主函数：验证测试覆盖率。"""
    print("🔍 阿里云可观测性SLS审计日志分析MCP服务器测试覆盖率验证")
    print("=" * 50)
    
    # 提取toolkits中的tool方法
    print("\n📋 扫描toolkits目录中的tool方法...")
    tool_methods = extract_tool_methods_from_toolkits()
    
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
        print("⚠️  未发现任何tool方法，请检查toolkits目录")
    
    # 返回状态码
    if untested:
        print(f"\n❌ 发现 {len(untested)} 个未测试的方法")
        sys.exit(1)
    else:
        print("\n✅ 所有方法都已有测试覆盖")
        sys.exit(0)


if __name__ == "__main__":
    main()