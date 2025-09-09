#!/usr/bin/env python3
"""Setup script for alibabacloud-cluster-audit-log-mcp-server"""

from setuptools import setup, find_packages

setup(
    name="alibabacloud-cluster-audit-log-mcp-server",
    version="0.1.0",
    description="AlibabaCloud ACK MCP Server for Kubernetes audit log querying",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="AlibabaCloud",
    author_email="support@alibabacloud.com",
    url="https://github.com/alibabacloud/alibabacloud-ack-mcp-server",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "mcp>=1.0.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "aliyun": ["aliyun-log-python-sdk>=0.8.0"],
        "all": ["aliyun-log-python-sdk>=0.8.0"],
    },
    entry_points={
        "console_scripts": [
            "alibabacloud-cluster-audit-log-mcp-server=alibabacloud_cluster_audit_log_mcp_server.server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
