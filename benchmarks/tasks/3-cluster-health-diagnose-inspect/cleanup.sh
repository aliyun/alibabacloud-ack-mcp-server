#!/usr/bin/env bash

NAMESPACE="case3-cluster-health-diagnose-inspect"
DEPLOYMENT="case3-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true
