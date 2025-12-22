#!/usr/bin/env bash

NAMESPACE="case6-workload-cost-analysis"

echo "清理测试环境..."
kubectl delete namespace $NAMESPACE --ignore-not-found=true

echo "Cleanup 完成！"
