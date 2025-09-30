#!/usr/bin/env bash

echo "开始验证集群所有节点的可调度状态..."

# 获取集群中所有节点
echo "获取集群中所有节点..."
ALL_NODES=$(kubectl get nodes --no-headers -o custom-columns=":metadata.name")

if [ -z "$ALL_NODES" ]; then
    echo "错误: 未找到任何节点"
    exit 1
fi

echo "找到的节点:"
echo "$ALL_NODES"

# 计数器
TOTAL_NODES=0
SCHEDULABLE_NODES=0
UNSCHEDULABLE_NODES=0
UNSCHEDULABLE_NODE_LIST=()

echo "检查每个节点的调度状态..."
echo "========================================"

# 逐个检查节点的可调度状态
for node in $ALL_NODES; do
    TOTAL_NODES=$((TOTAL_NODES + 1))
    
    # 检查节点是否为不可调度状态
    UNSCHEDULABLE=$(kubectl get node $node -o jsonpath='{.spec.unschedulable}' 2>/dev/null)
    
    # 获取节点的条件信息
    NODE_STATUS=$(kubectl get node $node -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    NODE_REASON=$(kubectl get node $node -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null)
    
    # 检查节点是否有 NoSchedule taint
    TAINTS=$(kubectl get node $node -o jsonpath='{.spec.taints[*].effect}' 2>/dev/null)
    HAS_NO_SCHEDULE_TAINT=false
    if echo "$TAINTS" | grep -q "NoSchedule"; then
        HAS_NO_SCHEDULE_TAINT=true
    fi
    
    echo "节点: $node"
    echo "  Ready 状态: $NODE_STATUS"
    
    if [ "$UNSCHEDULABLE" = "true" ]; then
        UNSCHEDULABLE_NODES=$((UNSCHEDULABLE_NODES + 1))
        UNSCHEDULABLE_NODE_LIST+=("$node")
        echo "  调度状态: ✗ 不可调度 (Unschedulable)"
    elif [ "$HAS_NO_SCHEDULE_TAINT" = "true" ]; then
        UNSCHEDULABLE_NODES=$((UNSCHEDULABLE_NODES + 1))
        UNSCHEDULABLE_NODE_LIST+=("$node")
        echo "  调度状态: ✗ 不可调度 (NoSchedule Taint)"
        echo "  Taints: $TAINTS"
    elif [ "$NODE_STATUS" != "True" ]; then
        UNSCHEDULABLE_NODES=$((UNSCHEDULABLE_NODES + 1))
        UNSCHEDULABLE_NODE_LIST+=("$node")
        echo "  调度状态: ✗ 不可调度 (Not Ready: $NODE_REASON)"
    else
        SCHEDULABLE_NODES=$((SCHEDULABLE_NODES + 1))
        echo "  调度状态: ✓ 可调度"
    fi
    echo "----------------------------------------"
done

echo ""
echo "========================================"
echo "节点状态统计:"
echo "  总节点数: $TOTAL_NODES"
echo "  可调度节点: $SCHEDULABLE_NODES"
echo "  不可调度节点: $UNSCHEDULABLE_NODES"

if [ $UNSCHEDULABLE_NODES -gt 0 ]; then
    echo ""
    echo "不可调度的节点列表:"
    for unschedulable_node in "${UNSCHEDULABLE_NODE_LIST[@]}"; do
        echo "  - $unschedulable_node"
    done
fi

echo "========================================"

# 显示详细的节点信息
echo "详细节点信息:"
kubectl get nodes -o wide

echo ""
echo "========================================"

# 验证结果
if [ $UNSCHEDULABLE_NODES -eq 0 ]; then
    echo "✓ 验证成功: 所有节点都处于可调度状态"
    echo "  - 总节点数: $TOTAL_NODES"
    echo "  - 可调度节点数: $SCHEDULABLE_NODES"
    exit 0
else
    echo "✗ 验证失败: 发现 $UNSCHEDULABLE_NODES 个不可调度的节点"
    echo "  - 总节点数: $TOTAL_NODES"
    echo "  - 可调度节点数: $SCHEDULABLE_NODES"
    echo "  - 不可调度节点数: $UNSCHEDULABLE_NODES"
    echo ""
    echo "请检查以下不可调度的节点:"
    for unschedulable_node in "${UNSCHEDULABLE_NODE_LIST[@]}"; do
        echo "  - $unschedulable_node"
        # 显示详细信息
        echo "    详细信息:"
        kubectl describe node "$unschedulable_node" | grep -E "(Unschedulable|Taints|Conditions)" -A 3
        echo ""
    done
    exit 1
fi
