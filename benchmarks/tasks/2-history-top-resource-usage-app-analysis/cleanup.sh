#!/usr/bin/env bash

NAMESPACE="case2-history-top-resource-usage-app-analysis"
DEPLOYMENT="case2-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

