#!/usr/bin/env bash

NAMESPACE="case3-cluster-health-diagnose-inspect"
DEPLOYMENT="case3-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

# Restore all nodes to schedulable state
echo "Restoring all nodes to schedulable state..."
NODES=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}')
if [ -n "$NODES" ]; then
    for NODE in $NODES; do
        echo "Restoring node: $NODE"
        kubectl patch node "$NODE" -p '{"spec":{"unschedulable":false}}'
    done
    echo "All nodes restored to schedulable state"
else
    echo "No nodes found in cluster"
fi
