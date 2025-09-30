#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "开始设置集群节点为不可调度状态..."

# 获取集群中所有的可调度节点
echo "获取集群中所有可调度的节点..."
SCHEDULABLE_NODES=$(kubectl get nodes --no-headers -o custom-columns=":metadata.name,:spec.unschedulable" | grep -v "true" | awk '{print $1}' | grep -v "<none>")

if [ -z "$SCHEDULABLE_NODES" ]; then
    echo "错误: 未找到可调度的节点"
    echo "当前集群节点状态:"
    kubectl get nodes -o wide
    exit 1
fi

echo "找到的可调度节点:"
echo "$SCHEDULABLE_NODES"

# 选择第一个可调度的节点
SELECTED_NODE=$(echo "$SCHEDULABLE_NODES" | head -1)

if [ -z "$SELECTED_NODE" ]; then
    echo "错误: 无法选择节点"
    exit 1
fi

echo "选中的节点: $SELECTED_NODE"

# 显示节点修改前的状态
echo "节点修改前的状态:"
kubectl get node $SELECTED_NODE -o wide

# 将选中的节点设置为不可调度
echo "正在将节点 $SELECTED_NODE 设置为不可调度..."
if kubectl cordon $SELECTED_NODE; then
    echo "✓ 成功将节点 $SELECTED_NODE 设置为不可调度"
else
    echo "✗ 将节点 $SELECTED_NODE 设置为不可调度失败"
    exit 1
fi

# 显示节点修改后的状态
echo "节点修改后的状态:"
kubectl get node $SELECTED_NODE -o wide

# 显示所有节点的状态
echo "当前集群所有节点状态:"
kubectl get nodes -o wide

# 保存被修改的节点名称到文件，供 cleanup脚本使用
echo "$SELECTED_NODE" > "$SCRIPT_DIR/cordoned_node.txt"
echo "已将被修改的节点名称保存到 $SCRIPT_DIR/cordoned_node.txt"

echo "========================================"
echo "✓ setup 完成：节点 $SELECTED_NODE 已设置为不可调度"
echo "  - 新 pod 将不会被调度到该节点上"
echo "  - 现有 pod 仍将继续在该节点上运行"
echo "  - 请使用 cleanup.sh 恢复节点的可调度状态"
echo "========================================"
