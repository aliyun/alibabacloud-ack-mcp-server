#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="case6-workload-cost-analysis"
DEPLOYMENT="cost-demo-app"
ARTIFACT_FILE="$SCRIPT_DIR/artifacts/cost_demo_deployment.yaml"

# 删除已存在的 namespace（如果有）
kubectl delete namespace $NAMESPACE --ignore-not-found

# 创建 namespace
kubectl create namespace $NAMESPACE

# 部署测试应用
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

# 等待 deployment 就绪
echo "等待 deployment 就绪..."
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=60s || true

# 等待一段时间让应用生成一些 metrics 数据
echo "等待60秒让应用生成指标数据..."
sleep 60

echo "Setup 完成！"
