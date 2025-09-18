#!/usr/bin/env bash
NAMESPACE="4-track-historical-app-specification"
DEPLOYMENT="case4-app"
ARTIFACT_FILE=artifacts/demo_deployment.yaml

kubectl delete namespace $NAMESPACE --ignore-not-found

# Create namespace
kubectl create namespace $NAMESPACE

# Apply the deployment from artifacts
kubectl apply -f $ARTIFACT_FILE -n $NAMESPACE

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

echo "Setup completed: app was created, ran for 15 seconds, then deleted"