# prometheus metrics dictionary

reference doc: https://help.aliyun.com/zh/arms/prometheus-monitoring/container-cluster-metrics

# how to use

## gain the guidance's key fields

each guidance's metric definition is for pattern:
    pod's cpu
    coredns's state
    node's state
    node's cpu

so the key fields are:

- 1. resource label (not exactly prometheus metric label)
    this is what target resource entity you want to query from the guidance, to get your metric definition.
    enum is: node, pod, container, deployment, daemonset, job, coredns, ingress, hpa, persistentvolume, mountpoint

- 2. category
    this is the metric category you want to query from the guidance, to get your metric definition.
    enum is: cpu, memory, network, disk, state