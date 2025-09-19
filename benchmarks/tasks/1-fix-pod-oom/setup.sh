#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="case1-fix-pod-oom"
DEPLOYMENT="case1-app"
ARTIFACT_FILE="$SCRIPT_DIR/artifacts/oom_demo_deployment.yaml"

kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the deployment from artifacts
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

# Wait for the deployment to be created
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=30s || true

# Wait until an OOMKilled status is detected in pod containerStatuses (timeout after 30s)
echo "Waiting for OOMKilled status to occur in pod..."
for i in {1..15}; do
  OOMKILLED_STATUS=$(kubectl get pods -n $NAMESPACE -o json | jq -r '.items[] | select(.status.containerStatuses[]?.lastState.terminated.reason == "OOMKilled") | .metadata.name' | head -1)
  if [ -n "$OOMKILLED_STATUS" ]; then
    echo "OOMKilled status detected in pod: $OOMKILLED_STATUS"
    break
  fi
  sleep 2
done
