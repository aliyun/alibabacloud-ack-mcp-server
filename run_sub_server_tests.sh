#!/bin/bash
# 所有子MCP服务器的单元测试运行脚本

set -e

echo "🚀 AlibabaCloud Container Service - 子MCP服务器单元测试套件"
echo "================================================================"

# 变更到项目根目录
cd "$(dirname "$0")"

# 检查虚拟环境是否存在并激活
if [ -d "venv" ]; then
    echo "📦 激活虚拟环境..."
    source venv/bin/activate
fi

# 安装测试依赖
if ! python -c "import pytest" 2>/dev/null; then
    echo "📦 安装测试依赖..."
    pip install pytest pytest-asyncio
fi

# 定义所有子MCP服务器目录
SUB_SERVERS=(
    "ack-cluster-management-mcp-server"
    "ack-addon-management-mcp-server" 
    "ack-nodepool-management-mcp-server"
    "ack-diagnose-mcp-server"
    "kubernetes-client-mcp-server"
    "alibabacloud-o11y-prometheus-mcp-server"
    "alibabacloud-o11y-sls-apiserver-log-mcp-server"
    "alibabacloud-ack-cloudresource-monitor-mcp-server"
    "alibabacloud-o11y-sls-audit-log-analysis-mcp-server"
)

# 运行测试的函数
run_server_tests() {
    local server_dir=$1
    local server_path="src/$server_dir"
    
    echo ""
    echo "🧪 测试 $server_dir..."
    echo "----------------------------------------"
    
    if [ -d "$server_path/tests" ]; then
        # 运行该服务器的所有测试
        python -m pytest "$server_path/tests" -v --tb=short
        if [ $? -eq 0 ]; then
            echo "✅ $server_dir 测试通过"
        else
            echo "❌ $server_dir 测试失败"
            return 1
        fi
    else
        echo "⚠️  $server_dir 没有tests目录"
    fi
}

# 根据参数运行不同的测试
case "${1:-all}" in
    "cluster")
        echo "🏗️ 运行集群管理相关服务器测试..."
        run_server_tests "ack-cluster-management-mcp-server"
        run_server_tests "ack-addon-management-mcp-server"
        run_server_tests "ack-nodepool-management-mcp-server"
        run_server_tests "ack-diagnose-mcp-server"
        ;;
    "k8s"|"kubernetes")
        echo "☸️ 运行Kubernetes相关服务器测试..."
        run_server_tests "kubernetes-client-mcp-server"
        ;;
    "observability"|"o11y")
        echo "👁️ 运行可观测性相关服务器测试..."
        run_server_tests "alibabacloud-o11y-prometheus-mcp-server"
        run_server_tests "alibabacloud-o11y-sls-apiserver-log-mcp-server"
        run_server_tests "alibabacloud-ack-cloudresource-monitor-mcp-server"
        run_server_tests "alibabacloud-o11y-sls-audit-log-analysis-mcp-server"
        ;;
    "audit")
        echo "🔍 运行审计日志服务器测试..."
        run_server_tests "alibabacloud-o11y-sls-audit-log-analysis-mcp-server"
        ;;
    "fast")
        echo "⚡ 运行快速测试（跳过审计日志）..."
        for server in "${SUB_SERVERS[@]}"; do
            if [ "$server" != "alibabacloud-o11y-sls-audit-log-analysis-mcp-server" ]; then
                run_server_tests "$server"
            fi
        done
        ;;
    "all"|*)
        echo "🧪 运行所有子MCP服务器测试..."
        failed_servers=()
        
        for server in "${SUB_SERVERS[@]}"; do
            if ! run_server_tests "$server"; then
                failed_servers+=("$server")
            fi
        done
        
        echo ""
        echo "📊 测试总结"
        echo "==============================="
        total_servers=${#SUB_SERVERS[@]}
        failed_count=${#failed_servers[@]}
        passed_count=$((total_servers - failed_count))
        
        echo "总服务器数量: $total_servers"
        echo "通过测试: $passed_count"
        echo "失败测试: $failed_count"
        
        if [ $failed_count -gt 0 ]; then
            echo ""
            echo "❌ 失败的服务器:"
            for server in "${failed_servers[@]}"; do
                echo "  - $server"
            done
            exit 1
        else
            echo ""
            echo "🎉 所有子MCP服务器测试都通过了！"
        fi
        ;;
esac

echo ""
echo "✅ 子MCP服务器测试执行完成！"