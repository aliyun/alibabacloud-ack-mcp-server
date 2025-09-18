#!/usr/bin/env bash
kubectl delete namespace case1-fix-pod-oom --ignore-not-found

# Create namespace
kubectl create namespace case1-fix-pod-oom

# Apply the deployment from artifacts
kubectl apply -f artifacts/oom_demo_deployment.yaml -n case1-fix-pod-oom

# Wait for the deployment to be created
kubectl rollout status deployment/case1-app -n case1-fix-pod-oom --timeout=30s || true

# Wait until an OOMKilled status is detected in pod containerStatuses (timeout after 30s)
echo "Waiting for OOMKilled status to occur in pod..."
for i in {1..15}; do
  OOMKILLED_STATUS=$(kubectl get pods -n case1-fix-pod-oom -o json | jq -r '.items[] | select(.status.containerStatuses[]?.lastState.terminated.reason == "OOMKilled") | .metadata.name' | head -1)
  if [ -n "$OOMKILLED_STATUS" ]; then
    echo "OOMKilled status detected in pod: $OOMKILLED_STATUS"
    break
  fi
  sleep 2
done
