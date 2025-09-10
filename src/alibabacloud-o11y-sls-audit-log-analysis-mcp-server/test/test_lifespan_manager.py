"""Unit tests for runtime provider implementation."""

import pytest
import asyncio
import tempfile
import yaml
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from ..context.lifespan_manager import KubeAuditRuntimeProvider


class TestKubeAuditRuntimeProvider:
    """Test cases for KubeAuditRuntimeProvider."""

    def test_init_with_config_path(self, temp_config_file):
        """Test initialization with config file path."""
        manager = KubeAuditRuntimeProvider(config_path=temp_config_file)
        
        assert manager._config is not None
        assert "default_cluster" in manager._config
        assert "clusters" in manager._config

    def test_init_with_config_dict(self, mock_config):
        """Test initialization with config dictionary."""
        manager = KubeAuditRuntimeProvider(config=mock_config)
        
        assert manager._config == mock_config
        assert manager._default_cluster == "default"

    def test_init_without_config(self):
        """Test initialization without config raises error."""
        with pytest.raises(ValueError, match="Either config_path or config must be provided"):
            KubeAuditRuntimeProvider()

    def test_load_config_from_file(self, mock_config, temp_config_file):
        """Test loading configuration from file."""
        manager = KubeAuditRuntimeProvider(config={"clusters": []})
        manager._load_config_from_file(temp_config_file)
        
        assert manager._config == mock_config

    def test_load_config_from_invalid_file(self):
        """Test loading configuration from invalid file."""
        manager = KubeAuditRuntimeProvider(config={"clusters": []})
        
        with pytest.raises(Exception):
            manager._load_config_from_file("nonexistent.yaml")

    def test_get_default_cluster(self, mock_config):
        """Test getting default cluster from config."""
        manager = KubeAuditRuntimeProvider(config=mock_config)
        default_cluster = manager.get_default_cluster(mock_config)
        
        assert default_cluster == "test-cluster"

    def test_get_default_cluster_without_config(self):
        """Test getting default cluster without config."""
        manager = KubeAuditRuntimeProvider(config={"clusters": []})
        default_cluster = manager.get_default_cluster({})
        
        assert default_cluster == "default"

    @patch('..provider.provider.AlibabaSLSProvider')
    def test_initialize_providers_alibaba(self, mock_provider_class, mock_config):
        """Test provider initialization for Alibaba SLS."""
        mock_provider_instance = Mock()
        mock_provider_class.return_value = mock_provider_instance
        
        manager = KubeAuditRuntimeProvider(config=mock_config)
        clients = manager.initialize_providers(mock_config)
        
        assert "test-cluster" in clients
        assert clients["test-cluster"] == mock_provider_instance
        mock_provider_class.assert_called_once()


    def test_initialize_providers_unknown_type(self, mock_config):
        """Test provider initialization with unknown provider type."""
        config = {
            "clusters": [
                {
                    "name": "unknown-cluster",
                    "provider": {
                        "name": "unknown-provider",
                        "config": {}
                    }
                }
            ]
        }
        
        manager = KubeAuditRuntimeProvider(config=config)
        clients = manager.initialize_providers(config)
        
        assert "unknown-cluster" not in clients

    def test_initialize_providers_missing_cluster_name(self, mock_config):
        """Test provider initialization with missing cluster name."""
        config = {
            "clusters": [
                {
                    "provider": {
                        "name": "alibaba-sls",
                        "alibaba_sls": {}
                    }
                }
            ]
        }
        
        manager = KubeAuditRuntimeProvider(config=config)
        clients = manager.initialize_providers(config)
        
        assert len(clients) == 0

    def test_initialize_providers_missing_provider_name(self, mock_config):
        """Test provider initialization with missing provider name."""
        config = {
            "clusters": [
                {
                    "name": "test-cluster",
                    "provider": {
                        "alibaba_sls": {}
                    }
                }
            ]
        }
        
        manager = KubeAuditRuntimeProvider(config=config)
        clients = manager.initialize_providers(config)
        
        assert len(clients) == 0

    def test_initialize_providers_empty_config(self):
        """Test provider initialization with empty config."""
        manager = KubeAuditRuntimeProvider(config={"clusters": []})
        clients = manager.initialize_providers({})
        
        assert clients == {}

    @pytest.mark.asyncio
    async def test_init_runtime_context_creation(self, mock_config):
        """Test init_runtime context creation."""
        manager = KubeAuditRuntimeProvider(config=mock_config)
        mock_app = Mock()
        
        with patch.object(manager, 'initialize_providers') as mock_init_providers:
            mock_init_providers.return_value = {"test-cluster": Mock()}
            
            async with manager.init_runtime(mock_app) as context:
                assert "providers" in context
                assert "default_cluster" in context
                assert "config" in context
                assert context["default_cluster"] == "test-cluster"
                assert "test-cluster" in context["providers"]

    @pytest.mark.asyncio
    async def test_init_runtime_startup_shutdown_messages(self, mock_config, capsys):
        """Test init_runtime startup and shutdown messages."""
        manager = KubeAuditRuntimeProvider(config=mock_config)
        mock_app = Mock()
        
        with patch.object(manager, 'initialize_providers') as mock_init_providers:
            mock_init_providers.return_value = {}
            
            async with manager.init_runtime(mock_app):
                pass
            
            captured = capsys.readouterr()
            assert "KubeAudit server starting..." in captured.out

    @pytest.mark.asyncio
    async def test_init_runtime_provider_initialization_error(self, mock_config):
        """Test init_runtime with provider initialization error."""
        manager = KubeAuditRuntimeProvider(config=mock_config)
        mock_app = Mock()
        
        with patch.object(manager, 'initialize_providers') as mock_init_providers:
            mock_init_providers.side_effect = Exception("Provider init error")
            
            # Should not raise exception, but handle gracefully
            async with manager.init_runtime(mock_app) as context:
                assert "providers" in context
                assert context["providers"] == {}

    def test_runtime_provider_inheritance(self):
        """Test that KubeAuditRuntimeProvider inherits from RuntimeProvider."""
        from ..context.lifespan_manager import KubeAuditRuntimeProvider
        from src.runtime_provider import RuntimeProvider
        
        assert issubclass(KubeAuditRuntimeProvider, RuntimeProvider)

    def test_runtime_provider_abstract_methods_implemented(self):
        """Test that all abstract methods are implemented."""
        manager = KubeAuditRuntimeProvider(config={"clusters": [], "default_cluster": "test"})
        
        # Check that all required methods exist
        assert hasattr(manager, 'init_runtime')
        assert hasattr(manager, 'initialize_providers')
        assert hasattr(manager, 'get_default_cluster')
        
        # Check that methods are callable
        assert callable(manager.init_runtime)
        assert callable(manager.initialize_providers)
        assert callable(manager.get_default_cluster)
