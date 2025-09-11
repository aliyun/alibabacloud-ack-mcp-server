#!/bin/bash

# ACK Cluster Management MCP Server 测试运行脚本

set -e

echo "🔍 运行 ACK Cluster Management MCP Server 单元测试..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 设置Python路径
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# 切换到测试目录
cd "$SCRIPT_DIR"

# 检查.env文件
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "✅ 发现 .env 文件，将加载环境变量"
    source "$PROJECT_ROOT/.env"
else
    echo "⚠️  未发现 .env 文件，将使用默认配置"
fi

# 检查必要的环境变量
if [ -z "$ACCESS_KEY_ID" ] && [ -z "$ACCESS_SECRET_KEY" ]; then
    echo "⚠️  警告: 未设置阿里云认证环境变量 ACCESS_KEY_ID 和 ACCESS_SECRET_KEY"
    echo "   部分集成测试可能会跳过"
fi

# 运行测试的函数
run_tests() {
    local test_pattern="$1"
    local description="$2"
    
    echo ""
    echo "📋 运行 $description..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if pytest $test_pattern -v --tb=short; then
        echo "✅ $description 通过"
    else
        echo "❌ $description 失败"
        return 1
    fi
}

# 默认运行所有测试
TEST_PATTERN="${1:-tests/}"

case "$TEST_PATTERN" in
    "basic")
        run_tests "tests/test_basic_functionality.py" "基础功能测试"
        ;;
    "tools")
        run_tests "tests/test_tool_methods.py" "工具方法测试"
        ;;
    "api")
        run_tests "tests/test_api_parameters.py" "API参数测试"
        ;;
    "verify")
        echo "🔍 运行测试覆盖率验证..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        python tests/verify_test_coverage.py
        ;;
    "all"|"")
        echo "🚀 运行所有测试..."
        
        # 运行基础功能测试
        run_tests "tests/test_basic_functionality.py" "基础功能测试"
        
        # 运行工具方法测试
        run_tests "tests/test_tool_methods.py" "工具方法测试"
        
        # 运行API参数测试  
        run_tests "tests/test_api_parameters.py" "API参数测试"
        
        echo ""
        echo "🎉 所有测试完成！"
        ;;
    *)
        run_tests "$TEST_PATTERN" "自定义测试"
        ;;
esac

echo ""
echo "📊 测试总结:"
echo "   - 基础功能测试: test_basic_functionality.py"
echo "   - 工具方法测试: test_tool_methods.py (针对每个handler tool方法)"
echo "   - API参数测试: test_api_parameters.py"
echo ""
echo "🔧 使用方法:"
echo "   $0              # 运行所有测试"
echo "   $0 basic        # 只运行基础功能测试"
echo "   $0 tools        # 只运行工具方法测试"
echo "   $0 api          # 只运行API参数测试"
echo "   $0 verify       # 运行测试覆盖率验证"
echo "   $0 pattern      # 运行自定义测试模式"