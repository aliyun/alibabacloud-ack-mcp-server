#!/usr/bin/env bash

# 获取集群中的所有节点
echo "Getting node list..."
NODES=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}')
if [ -z "$NODES" ]; then
    echo "No nodes found in cluster"
    exit 1
fi

# 转换为数组并选择第一个节点
NODE_ARRAY=($NODES)
SELECTED_NODE=${NODE_ARRAY[0]}
echo "Selected node for coredns scheduling: $SELECTED_NODE"

# 为coredns deployment移除podAntiAffinity和topologySpreadConstraints并添加nodeselector，使其调度到选定节点
echo "Patching coredns deployment to remove podAntiAffinity and topologySpreadConstraints, and schedule on node: $SELECTED_NODE"
kubectl patch deployment coredns -n kube-system -p '{
  "spec": {
    "template": {
      "spec": {
        "affinity": {
          "podAntiAffinity": null,
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
          }
        },
        "topologySpreadConstraints": null,
        "nodeSelector": {
          "kubernetes.io/hostname": "'$SELECTED_NODE'",
          "kubernetes.io/os": "linux"
        }
      }
    }
  }
}'

kubectl scale deployment coredns -n kube-system --replicas=0
kubectl scale deployment coredns -n kube-system --replicas=2

# 等待coredns deployment状态更新成功
echo "Waiting for coredns deployment to be updated..."
kubectl rollout status deployment/coredns -n kube-system --timeout=60s || true

echo "Setup completed successfully"