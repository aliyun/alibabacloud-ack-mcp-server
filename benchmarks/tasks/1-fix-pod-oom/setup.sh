#!/usr/bin/env bash
kubectl delete namespace case1-fix-pod-oom --ignore-not-found

# Create namespace
kubectl create namespace case1-fix-pod-oom

# Apply the deployment from artifacts
kubectl apply -f artifacts/oom_demo_deployment.yaml -n case1-fix-pod-oom

# Wait for the deployment to be created
kubectl rollout status deployment/case1-app -n case1-fix-pod-oom --timeout=60s || true

# Wait until an OOMKilled event is detected (timeout after 30s)
echo "Waiting for OOMKilled event to occur..."
for i in {1..15}; do
  OOMKILLED_COUNT=$(kubectl get events -n case1-fix-pod-oom --field-selector reason=OOMKilling -o json | jq '.items | length')
  if [ "$OOMKILLED_COUNT" -gt 0 ]; then
    echo "OOMKilled event detected."
    break
  fi
  sleep 2
done
