#!/usr/bin/env bash

NAMESPACE="case1-fix-pod-oom"
DEPLOYMENT="case1-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true
