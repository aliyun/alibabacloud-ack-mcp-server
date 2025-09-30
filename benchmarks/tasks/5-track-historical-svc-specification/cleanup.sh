#!/usr/bin/env bash
NAMESPACE="4-track-historical-app-specification"
DEPLOYMENT="case4-app"
SERVICE="case4-service"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

# Delete the service to create historical data
echo "Deleting service to create historical data..."
kubectl delete service/$SERVICE -n $NAMESPACE
