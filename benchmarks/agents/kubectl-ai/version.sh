#!/usr/bin/env bash
kubectl-ai version 2>/dev/null | grep "version:" | awk '{print $2}'