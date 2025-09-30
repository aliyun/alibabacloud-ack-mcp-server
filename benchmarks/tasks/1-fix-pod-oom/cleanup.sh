#!/usr/bin/env bash

NAMESPACE="case1"
DEPLOYMENT="case1-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true
