#!/usr/bin/env bash
NAMESPACE="case5"
SERVICE="case5-service"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

echo "Deleting service to clean up..."
kubectl delete service/$SERVICE -n $NAMESPACE
