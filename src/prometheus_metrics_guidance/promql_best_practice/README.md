
# promql best practice

## reference doc. https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-configuring-alert-rules-in-prometheus?spm=a2c63.p38356.0.i1#7da08e90acnpa

# how to use

## gain the guidance's key fields

each guidance's promql example is for pattern:
    pod's cpu
    coredns's state
    node's state
    node's cpu

so the key fields are:

- 1. resource label (not exactly prometheus metric label)
    this is what target resource entity you want to query from the guidance, to get your promql sample.
    enum is: node, pod, container, deployment, daemonset, job, coredns, ingress, hpa, persistentvolume, mountpoint

- 2. category
    this is the metric category you want to query from the guidance, to get your promql sample.
    enum is: cpu, memory, network, disk, state