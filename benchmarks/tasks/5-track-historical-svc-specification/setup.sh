#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="case5"
SERVICE="case5-service"
SERVICE_FILE="$SCRIPT_DIR/artifacts/demo_service.yaml"

kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the service from artifacts
kubectl apply -f $SERVICE_FILE -n $NAMESPACE

# Delete the service to create historical data
echo "Deleting service to create historical data..."
kubectl delete service/$SERVICE -n $NAMESPACE

echo "Setup completed: service was created, ran for few seconds, then deleted"