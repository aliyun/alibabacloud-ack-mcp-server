"""Pytest configuration and shared fixtures."""

import asyncio
import tempfile
from unittest.mock import Mock

import pytest
import yaml


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "default_cluster": "test-cluster",
        "clusters": [
            {
                "name": "test-cluster",
                "description": "Test cluster",
                "provider": {
                    "name": "alibaba-sls",
                    "alibaba_sls": {
                        "endpoint": "test.log.aliyuncs.com",
                        "project": "test-project",
                        "logstore": "test-logstore",
                        "region": "test-region",
                    },
                },
            }
        ],
    }


@pytest.fixture
def mock_alibaba_config():
    """Mock Alibaba SLS configuration."""
    return {
        "endpoint": "cn-hangzhou.log.aliyuncs.com",
        "project": "test-project",
        "logstore": "test-logstore",
        "region": "cn-hangzhou",
        "access_key_id": "test-access-key",
        "access_key_secret": "test-secret-key",
    }


@pytest.fixture
def mock_query_params():
    """Mock query parameters for testing."""
    return {
        "namespace": "default",
        "verbs": ["get", "list"],
        "resource_types": ["pods"],
        "resource_name": "test-pod",
        "user": "test-user",
        "start_time": "1h",
        "end_time": None,
        "limit": 10,
        "cluster_name": "test-cluster",
    }


@pytest.fixture
def mock_audit_log_entry():
    """Mock audit log entry."""
    return {
        "timestamp": "2024-01-01T10:00:00Z",
        "user": {"username": "test-user"},
        "verb": "get",
        "objectRef": {"namespace": "default", "resource": "pods", "name": "test-pod"},
        "responseStatus": {"code": 200},
    }


@pytest.fixture
def mock_audit_log_result():
    """Mock audit log query result."""
    return {
        "provider_query": "test query",
        "entries": [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "user": {"username": "test-user"},
                "verb": "get",
                "objectRef": {
                    "namespace": "default",
                    "resource": "pods",
                    "name": "test-pod",
                },
                "responseStatus": {"code": 200},
            }
        ],
        "total": 1,
    }


@pytest.fixture
def temp_config_file(mock_config):
    """Create a temporary configuration file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(mock_config, f)
        yield f.name


@pytest.fixture
def mock_sls_client():
    """Mock Alibaba SLS client."""
    client = Mock()
    client.get_logs = Mock()
    return client


@pytest.fixture
def mock_context():
    """Mock FastMCP Context."""
    context = Mock()
    context.lifespan_context = {
        "providers": {"test-cluster": Mock()},
        "default_cluster": "test-cluster",
        "config": {},
    }
    return context
