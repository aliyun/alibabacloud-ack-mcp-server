#!/usr/bin/env bash

NAMESPACE="case3"
DEPLOYMENT="case3-app"

kubectl delete namespace $NAMESPACE --ignore-not-found=true

# 恢复coredns deployment的完整affinity配置，包括podAntiAffinity
echo "Restoring coredns deployment affinity configuration..."
kubectl patch deployment coredns -n kube-system -p '{
  "spec": {
    "template": {
      "spec": {
        "affinity": {
          "nodeAffinity": {
            "preferredDuringSchedulingIgnoredDuringExecution": [
              {
                "preference": {
                  "matchExpressions": [
                    {
                      "key": "k8s.aliyun.com",
                      "operator": "NotIn",
                      "values": [
                        "true"
                      ]
                    }
                  ]
                },
                "weight": 100
              }
            ],
            "requiredDuringSchedulingIgnoredDuringExecution": {
              "nodeSelectorTerms": [
                {
                  "matchExpressions": [
                    {
                      "key": "type",
                      "operator": "NotIn",
                      "values": [
                        "virtual-kubelet"
                      ]
                    },
                    {
                      "key": "alibabacloud.com/lingjun-worker",
                      "operator": "NotIn",
                      "values": [
                        "true"
                      ]
                    }
                  ]
                }
              ]
            }
          },
          "podAntiAffinity": {
            "requiredDuringSchedulingIgnoredDuringExecution": [
              {
                "labelSelector": {
                  "matchExpressions": [
                    {
                      "key": "k8s-app",
                      "operator": "In",
                      "values": [
                        "kube-dns"
                      ]
                    }
                  ]
                },
                "topologyKey": "kubernetes.io/hostname"
              }
            ]
          }
        },
        "nodeSelector": null
      }
    }
  }
}'

# 等待coredns deployment恢复正常
echo "Waiting for coredns deployment to be restored..."
kubectl rollout status deployment/coredns -n kube-system --timeout=60s || true

echo "Cleanup completed successfully"