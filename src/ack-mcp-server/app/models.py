#!/usr/bin/env python3
"""
Pydantic models for the application.
This file contains all the shared data models.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ObservabilityContext(BaseModel):
    """Model for the observability context response."""

    cluster_id: str = Field(description="The ACK cluster ID")
    region_id: str = Field(description="The Alibaba Cloud region ID")
    sls_project: str = Field(description=(
        "The SLS (Log Service) project name for given ACK Cluster"))
    sls_log_store: str = Field(description=(
        "The SLS (Log Service) log store name for given ACK Cluster"))
    arms_project: str = Field(
        description=(
            "The ARMS (Application Real-Time Monitoring Service) project name for given ACK Cluster")
    )
    arms_metric_store: str = Field(
        description=(
            "The ARMS (Application Real-Time Monitoring Service) metric store name for given ACK Cluster")
    )


class ErrorContext(BaseModel):
    """Model for error responses."""

    error: str = Field(description="Error type")
    message: str = Field(description="Detailed error message")


class ClusterInfo(BaseModel):
    """Model for basic cluster information."""

    cluster_id: str = Field(
        description="The unique identifier for the cluster")
    name: str = Field(description="The name of the cluster")
    region_id: str = Field(
        description="The region where the cluster is deployed")
    state: str = Field(
        description="Current state of the cluster (running, updating, etc.)")
    cluster_type: str = Field(
        description="Type of cluster (ManagedKubernetes, Kubernetes, etc.)")
    current_version: str = Field(
        description="Version of Kubernetes running on the cluster")
    created: str = Field(description="Creation timestamp")
    updated: str = Field(description="Last update timestamp")
    vpc_id: str = Field(description="VPC identifier")
    vswitch_ids: list[str] = Field(description="List of VSwitch identifiers")
    security_group_id: str = Field(description="Security group identifier")
    network_mode: str = Field(description="Network mode (vpc, classic)")
    container_cidr: str = Field(description="Container network CIDR")
    service_cidr: str = Field(description="Service network CIDR")
    resource_group_id: str = Field(description="Resource group identifier")
    cluster_spec: str = Field(description="Cluster specification")
    tags: list[dict] = Field(
        description="List of tags associated with the cluster")
    maintenance_window: dict = Field(
        description="Maintenance window configuration")
    proxy_mode: str = Field(description="Proxy mode (ipvs, iptables)")
    deletion_protection: bool = Field(description="Deletion protection flag")
    node_port_range: str = Field(description="Node port range")
    api_server_endpoints: dict = Field(
        description="The API server endpoints of the cluster")


class ClusterDetail(ClusterInfo):
    """Model for detailed cluster information."""
    pass
