#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORDONED_NODE_FILE="$SCRIPT_DIR/cordoned_node.txt"

echo "开始清理 exception-resource-diagnose 任务..."

# 恢复被设置为不可调度的节点
if [ -f "$CORDONED_NODE_FILE" ]; then
    CORDONED_NODE=$(cat "$CORDONED_NODE_FILE")
    
    if [ -n "$CORDONED_NODE" ]; then
        echo "正在恢复节点 $CORDONED_NODE 的可调度状态..."
        
        # 检查节点是否存在
        if kubectl get node "$CORDONED_NODE" >/dev/null 2>&1; then
            # 显示节点恢复前的状态
            echo "节点恢复前的状态:"
            kubectl get node "$CORDONED_NODE" -o wide
            
            # 恢复节点的可调度状态
            if kubectl uncordon "$CORDONED_NODE"; then
                echo "✓ 成功恢复节点 $CORDONED_NODE 的可调度状态"
                
                # 显示节点恢复后的状态
                echo "节点恢复后的状态:"
                kubectl get node "$CORDONED_NODE" -o wide
            else
                echo "✗ 恢复节点 $CORDONED_NODE 的可调度状态失败"
            fi
        else
            echo "警告: 节点 $CORDONED_NODE 不存在，可能已被删除"
        fi
        
        # 删除保存节点名称的文件
        rm -f "$CORDONED_NODE_FILE"
        echo "已删除节点记录文件: $CORDONED_NODE_FILE"
    else
        echo "警告: cordoned_node.txt 文件为空"
    fi
else
    echo "未找到 cordoned_node.txt 文件，无需恢复节点状态"
fi

# 显示所有节点的最终状态
echo "清理后集群所有节点状态:"
kubectl get nodes -o wide

echo "========================================"
echo "✓ cleanup 完成：节点可调度状态已恢复"
echo "========================================"
