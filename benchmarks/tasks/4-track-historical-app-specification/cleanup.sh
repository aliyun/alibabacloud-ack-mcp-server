#!/usr/bin/env bash
NAMESPACE="4-track-historical-app-specification"
DEPLOYMENT="case4-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

