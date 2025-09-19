#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="case2-history-top-resource-usage-app-analysis"
DEPLOYMENT="case2-app"
ARTIFACT_FILE="$SCRIPT_DIR/artifacts/eat_memory_deployment.yaml"


kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the deployment from artifacts
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

# Wait for the deployment to be created
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=30s || true
