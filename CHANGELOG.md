
# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [1.0.0] - 2025-10-20

first release of ack-mcp-server.

### Added

support tools：

    Tools:
    - ack_kubectl
    - diagnose_resource
    - get_current_time
    - list_clusters
    - query_audit_log
    - query_controlplane_logs
    - query_inspect_report
    - query_prometheus
    - query_prometheus_metric_guidance

benchmark senators:

    Senators:
    - 1-fix-pod-oom
    - 2-history-top-resource-usage-app-analysis
    - 3-cluster-health-inspect
    - 4-exception-resource-diagnose
    - 5-track-historical-svc-specification