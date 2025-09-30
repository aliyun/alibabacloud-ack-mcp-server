#!/usr/bin/env bash

NAMESPACE="case4"
DEPLOYMENT="case4-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true --force --grace-period=0
