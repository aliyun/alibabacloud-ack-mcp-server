#!/usr/bin/env bash

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE="case3-cluster-health-diagnose-inspect"
DEPLOYMENT="case3-app"
ARTIFACT_FILE="$SCRIPT_DIR/artifacts/ugly_deployment.yaml"

kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the deployment from artifacts
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

# Wait for the deployment to be created
kubectl rollout status deployment/$DEPLOYMENT -n $NAMESPACE --timeout=30s || true

# Get all nodes and mark one as unschedulable for cluster health diagnosis
echo "Getting node list..."
NODES=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}')
if [ -n "$NODES" ]; then
    # Convert to array and select first node
    NODE_ARRAY=($NODES)
    SELECTED_NODE=${NODE_ARRAY[0]}
    echo "Selected node for unschedulable test: $SELECTED_NODE"
    
    # Mark the node as unschedulable
    kubectl patch node "$SELECTED_NODE" -p '{"spec":{"unschedulable":true}}'
    echo "Node $SELECTED_NODE marked as unschedulable"
else
    echo "No nodes found in cluster"
    exit 1
fi

