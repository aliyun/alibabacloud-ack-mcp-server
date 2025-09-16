#!/usr/bin/env python3
"""
全局测试覆盖率验证脚本。

此脚本检查所有子MCP服务器的测试覆盖率，
确保每个handler.py中的tool方法都有对应的测试用例。
"""

import os
import sys
import subprocess
from typing import Dict, List, Tuple


def get_all_mcp_servers() -> List[str]:
    """获取所有子MCP服务器目录。"""
    src_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_servers = []
    
    for item in os.listdir(src_dir):
        item_path = os.path.join(src_dir, item)
        if os.path.isdir(item_path) and item.endswith('-mcp-server'):
            tests_dir = os.path.join(item_path, 'tests')
            verify_script = os.path.join(tests_dir, 'verify_test_coverage.py')
            
            if os.path.exists(verify_script):
                mcp_servers.append(item)
    
    return sorted(mcp_servers)


def run_coverage_check(server_dir: str) -> Tuple[bool, str, str]:
    """运行单个服务器的测试覆盖率检查。"""
    script_path = os.path.join(server_dir, 'tests', 'verify_test_coverage.py')
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=server_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        success = result.returncode == 0
        return success, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "测试超时"
    except Exception as e:
        return False, "", f"执行错误: {str(e)}"


def main():
    """主函数：验证所有子MCP服务器的测试覆盖率。"""
    print("🔍 全局MCP服务器测试覆盖率验证")
    print("=" * 80)
    
    # 获取所有子MCP服务器
    mcp_servers = get_all_mcp_servers()
    
    if not mcp_servers:
        print("❌ 未找到任何子MCP服务器")
        sys.exit(1)
    
    print(f"📋 发现 {len(mcp_servers)} 个子MCP服务器:")
    for server in mcp_servers:
        print(f"  • {server}")
    
    print("\n" + "=" * 80)
    
    # 统计信息
    total_servers = len(mcp_servers)
    passed_servers = 0
    failed_servers = []
    coverage_summary = {}
    
    # 逐个检查每个服务器
    for i, server in enumerate(mcp_servers, 1):
        print(f"\n[{i}/{total_servers}] 🔍 检查 {server}")
        print("-" * 60)
        
        server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), server)
        success, stdout, stderr = run_coverage_check(server_path)
        
        if success:
            print("✅ 测试覆盖率检查通过")
            passed_servers += 1
            
            # 提取覆盖率信息
            lines = stdout.split('\n')
            for line in lines:
                if '测试覆盖率:' in line:
                    coverage = line.split('测试覆盖率:')[1].strip()
                    coverage_summary[server] = coverage
                    break
            else:
                coverage_summary[server] = "100.0%"
        else:
            print("❌ 测试覆盖率检查失败")
            failed_servers.append(server)
            coverage_summary[server] = "0.0%"
            
            if stderr:
                print(f"错误信息: {stderr}")
    
    # 显示总结
    print("\n" + "=" * 80)
    print("📊 测试覆盖率总结")
    print("=" * 80)
    
    print(f"总计子MCP服务器: {total_servers}")
    print(f"测试覆盖率检查通过: {passed_servers}")
    print(f"测试覆盖率检查失败: {len(failed_servers)}")
    
    if coverage_summary:
        print("\n📋 各服务器测试覆盖率:")
        for server, coverage in coverage_summary.items():
            status = "✅" if server not in failed_servers else "❌"
            print(f"  {status} {server:<45} {coverage}")
    
    if failed_servers:
        print(f"\n❌ 需要完善测试的服务器:")
        for server in failed_servers:
            print(f"  • {server}")
    
    # 返回状态码
    if failed_servers:
        print(f"\n❌ {len(failed_servers)} 个服务器需要完善测试覆盖率")
        sys.exit(1)
    else:
        print("\n🎉 所有子MCP服务器都已有完整的测试覆盖！")
        sys.exit(0)


if __name__ == "__main__":
    main()