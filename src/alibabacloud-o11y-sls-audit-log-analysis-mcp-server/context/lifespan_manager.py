"""Runtime provider implementation for Kubernetes audit log querying."""

import yaml
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional, List
from pathlib import Path
from fastmcp import FastMCP
from interfaces.runtime_provider import RuntimeProvider


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigLoader:
    """Configuration loader with validation and error handling."""

    def __init__(self):
        self.required_fields = {
            "clusters": list
        }

        self.required_cluster_fields = {
            "name": str,
            "provider": dict
        }

        self.supported_providers = {
            "alibaba_sls": ["endpoint", "project", "logstore", "region"],
        }

    def load_config_from_file(self, config_path: str) -> Dict[str, Any]:
        """Load and validate configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Validated configuration dictionary
            
        Raises:
            ConfigValidationError: If configuration is invalid
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        config_path = Path(config_path)

        # Check if file exists
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Check if file is readable
        if not config_path.is_file():
            raise ConfigValidationError(f"Path is not a file: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML format in {config_path}: {e}")
        except PermissionError as e:
            raise ConfigValidationError(f"Permission denied reading {config_path}: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Failed to read configuration file {config_path}: {e}")

        # Validate configuration
        self.validate_config(config)

        return config

    def validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure and content.
        
        Args:
            config: Configuration dictionary to validate
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ConfigValidationError("Configuration must be a dictionary")

        # Check required top-level fields
        for field, expected_type in self.required_fields.items():
            if field not in config:
                raise ConfigValidationError(f"Missing required field: {field}")

            if not isinstance(config[field], expected_type):
                raise ConfigValidationError(
                    f"Field '{field}' must be of type {expected_type.__name__}, "
                    f"got {type(config[field]).__name__}"
                )

        # Validate clusters
        self._validate_clusters(config["clusters"])

        # Validate default cluster exists (if specified)
        if "default_cluster" in config:
            default_cluster = config["default_cluster"]
            cluster_names = [cluster["name"] for cluster in config["clusters"]]
            if default_cluster not in cluster_names:
                raise ConfigValidationError(
                    f"Default cluster '{default_cluster}' not found in clusters list. "
                    f"Available clusters: {cluster_names}"
                )

    def _validate_clusters(self, clusters: List[Dict[str, Any]]) -> None:
        """Validate clusters configuration.
        
        Args:
            clusters: List of cluster configurations
            
        Raises:
            ConfigValidationError: If clusters configuration is invalid
        """
        if not clusters:
            raise ConfigValidationError("At least one cluster must be configured")

        cluster_names = set()

        for i, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                raise ConfigValidationError(f"Cluster {i} must be a dictionary")

            # Check required cluster fields
            for field, expected_type in self.required_cluster_fields.items():
                if field not in cluster:
                    raise ConfigValidationError(f"Cluster {i} missing required field: {field}")

                if not isinstance(cluster[field], expected_type):
                    raise ConfigValidationError(
                        f"Cluster {i} field '{field}' must be of type {expected_type.__name__}, "
                        f"got {type(cluster[field]).__name__}"
                    )

            # Check for duplicate cluster names
            cluster_name = cluster["name"]
            if cluster_name in cluster_names:
                raise ConfigValidationError(f"Duplicate cluster name: {cluster_name}")
            cluster_names.add(cluster_name)

            # Validate provider
            self._validate_provider(cluster["provider"], cluster_name)

    def _validate_provider(self, provider: Dict[str, Any], cluster_name: str) -> None:
        """Validate provider configuration.
        
        Args:
            provider: Provider configuration dictionary
            cluster_name: Name of the cluster (for error messages)
            
        Raises:
            ConfigValidationError: If provider configuration is invalid
        """
        if not isinstance(provider, dict):
            raise ConfigValidationError(f"Provider for cluster '{cluster_name}' must be a dictionary")

        # Find the provider type by checking which supported provider config is present
        provider_type = None
        for supported_provider in self.supported_providers.keys():
            if supported_provider in provider:
                provider_type = supported_provider
                break

        if not provider_type:
            raise ConfigValidationError(
                f"No supported provider configuration found for cluster '{cluster_name}'. "
                f"Supported providers: {list(self.supported_providers.keys())}"
            )

        # Validate provider-specific configuration
        self._validate_provider_config(provider, provider_type, cluster_name)

    def _validate_provider_config(self, provider: Dict[str, Any], provider_name: str, cluster_name: str) -> None:
        """Validate provider-specific configuration.
        
        Args:
            provider: Provider configuration dictionary
            provider_name: Name of the provider
            cluster_name: Name of the cluster
            
        Raises:
            ConfigValidationError: If provider configuration is invalid
        """
        required_fields = self.supported_providers[provider_name]

        # Get provider-specific config section
        config_section = provider.get(provider_name, {})

        if not config_section:
            raise ConfigValidationError(
                f"Missing provider configuration section for '{provider_name}' in cluster '{cluster_name}'"
            )

        if not isinstance(config_section, dict):
            raise ConfigValidationError(
                f"Provider configuration section for '{provider_name}' in cluster '{cluster_name}' must be a dictionary"
            )

        # Check required fields for this provider
        missing_fields = []
        for field in required_fields:
            if field not in config_section or not config_section[field]:
                missing_fields.append(field)

        if missing_fields:
            raise ConfigValidationError(
                f"Missing required fields for provider '{provider_name}' in cluster '{cluster_name}': {missing_fields}"
            )


class KubeAuditRuntimeProvider(RuntimeProvider):
    """Implementation of RuntimeProvider for Kubernetes audit log querying."""

    def __init__(self, config_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the lifespan manager with configuration.
        
        Args:
            config_path: Path to configuration file (YAML format)
            config: Configuration dictionary (alternative to config_path)
            
        Raises:
            ConfigValidationError: If configuration is invalid
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If neither config_path nor config is provided
        """
        self._clients: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}
        self._default_cluster: str = "default"
        self._config_loader = ConfigLoader()
        self.supported_providers = self._config_loader.supported_providers

        # Load configuration
        if config_path:
            self._config = self._config_loader.load_config_from_file(config_path)
        elif config:
            self._config_loader.validate_config(config)
            self._config = config
        else:
            raise ValueError("Either config_path or config must be provided")

    def _load_config_from_file(self, config_path: str):
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
        """
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")
            raise e

    @asynccontextmanager
    async def init_runtime(self, app: FastMCP) -> AsyncIterator[Dict[str, Any]]:
        """Simple runtime initialization implementation with provider initialization."""
        print("KubeAudit server starting...")

        # Initialize clients based on configuration
        self._clients = self.initialize_providers(self._config)

        # Set default cluster
        self._default_cluster = self.get_default_cluster(self._config)

        # Create context with providers
        context = {
            "providers": self._clients,
            "default_cluster": self._default_cluster,
            "config": self._config
        }

        yield context

    def initialize_providers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize all provider clients based on configuration."""
        clients = {}
        if not config:
            return clients

        # Initialize providers based on configuration
        clusters = config.get("clusters", [])
        for cluster in clusters:
            cluster_name = cluster.get("name")
            provider_config = cluster.get("provider", {})

            if not cluster_name or not provider_config:
                continue

            # Find the provider type by checking which supported provider config is present
            provider_type = None
            for supported_provider in self.supported_providers.keys():
                if supported_provider in provider_config:
                    provider_type = supported_provider
                    break

            if not provider_type:
                print(f"Warning: No supported provider configuration found for cluster '{cluster_name}'")
                continue

            # Create provider instance based on provider type
            try:
                if provider_type == "alibaba_sls":
                    sls_config = provider_config.get("alibaba_sls", {})
                    # Load credentials from environment variables
                    import os
                    access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
                    access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")

                    if not access_key_id or not access_key_secret:
                        raise ConfigValidationError(
                            f"Missing Alibaba Cloud credentials for cluster '{cluster_name}'. "
                            f"Please set ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET environment variables."
                        )

                    sls_config["access_key_id"] = access_key_id
                    sls_config["access_key_secret"] = access_key_secret

                    # Import here to avoid circular imports
                    from ..provider.provider import AlibabaSLSProvider
                    clients[cluster_name] = AlibabaSLSProvider(sls_config)
                else:
                    print(f"Warning: Unknown provider type: {provider_type}")
            except Exception as e:
                print(f"Warning: Failed to initialize provider {provider_type} for cluster {cluster_name}: {e}")

        return clients

    def get_default_cluster(self, config: Dict[str, Any]) -> str:
        """Get the default cluster name from configuration.
        
        If default_cluster is not specified, use the first cluster.
        """
        if "default_cluster" in config:
            return config["default_cluster"]

        # If no default_cluster specified, use the first cluster
        clusters = config.get("clusters", [])
        if clusters:
            return clusters[0]["name"]

        return "default"
