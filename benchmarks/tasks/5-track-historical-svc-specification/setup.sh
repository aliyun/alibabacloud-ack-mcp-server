#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="4-track-historical-app-specification"
DEPLOYMENT="case4-app"
SERVICE="case4-service"
ARTIFACT_FILE="$SCRIPT_DIR/artifacts/demo_deployment.yaml"
SERVICE_FILE="$SCRIPT_DIR/artifacts/demo_service.yaml"

kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the deployment from artifacts
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

# Apply the service from artifacts
kubectl apply -f $SERVICE_FILE -n $NAMESPACE

# Wait for the deployment to be ready
echo "Waiting for deployment to be ready..."
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=60s || true

# Wait for pods to be ready
echo "Waiting for pods to be ready..."
kubectl wait --for=condition=Ready pod -l app=$DEPLOYMENT -n $NAMESPACE --timeout=60s || true

# Sleep for 15 seconds to simulate app running
echo "App is ready, sleeping for 15 seconds..."
sleep 15

# Delete the deployment to create historical data
echo "Deleting deployment to create historical data..."
kubectl delete deployment/$DEPLOYMENT -n $NAMESPACE

# Delete the service to create historical data
echo "Deleting service to create historical data..."
kubectl delete service/$SERVICE -n $NAMESPACE

echo "Setup completed: app was created, ran for 15 seconds, then deleted"