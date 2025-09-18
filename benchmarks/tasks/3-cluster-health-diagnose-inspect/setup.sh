#!/usr/bin/env bash
kubectl delete namespace case2-history-top-resource-usage-app-analysis --ignore-not-found

# Create namespace
kubectl create namespace case2-history-top-resource-usage-app-analysis

# Apply the deployment from artifacts
kubectl apply -f artifacts/oom_demo_deployment.yaml -n case2-history-top-resource-usage-app-analysis

# Wait for the deployment to be created
kubectl rollout status deployment/case1-app -n case2-history-top-resource-usage-app-analysis --timeout=30s || true

