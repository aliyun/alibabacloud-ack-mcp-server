"""Tests for OAuth 2.1 integration in main_server.py."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# Helper: build a minimal settings_dict that satisfies create_main_server
# without triggering real cloud SDK calls.
def _base_settings(**overrides):
    settings = {
        "allow_write": False,
        "transport": "stdio",
        "host": "127.0.0.1",
        "port": 8000,
        "enable_execution_log": False,
        "region_id": "cn-hangzhou",
        "access_key_id": "fake-ak-id",
        "access_key_secret": "fake-ak-secret",
        "access_secret_key": "fake-ak-secret",
        "audit_config_path": None,
        "audit_config_dict": None,
        "cache_ttl": 300,
        "cache_max_size": 1000,
        "fastmcp_log_level": "INFO",
        "development": False,
        "diagnose_timeout": 600,
        "diagnose_poll_interval": 15,
        "kubectl_timeout": 30,
        "api_timeout": 60,
        "kubeconfig_mode": "ACK_PUBLIC",
        "kubeconfig_path": "~/.kube/config",
        "prometheus_endpoint_mode": "ARMS_PUBLIC",
        "original_settings": MagicMock(),
        # OAuth defaults – disabled
        "enable_oauth": False,
        "oauth_jwks_uri": None,
        "oauth_issuer": None,
        "oauth_audience": None,
        "oauth_base_url": None,
        "oauth_required_scopes": None,
    }
    settings.update(overrides)
    return settings


# We need to mock heavy external dependencies that create_main_server
# pulls in (cloud SDK clients, kubeconfig, etc.) so tests run without
# network / credentials.
_HANDLER_PATCHES = [
    "main_server.ACKClusterRuntimeProvider",
    "main_server.ACKClusterHandler",
    "main_server.KubectlHandler",
    "main_server.PrometheusHandler",
    "main_server.DiagnoseHandler",
    "main_server.InspectHandler",
    "main_server.ACKAuditLogHandler",
    "main_server.ACKControlPlaneLogHandler",
    "main_server.ACKCostAnalysisHandler",
]


def _apply_handler_mocks(monkeypatch):
    """Monkeypatch all heavy handler/provider classes so they become no-ops."""
    import main_server as ms
    for attr in [
        "ACKClusterRuntimeProvider",
        "ACKClusterHandler",
        "KubectlHandler",
        "PrometheusHandler",
        "DiagnoseHandler",
        "InspectHandler",
        "ACKAuditLogHandler",
        "ACKControlPlaneLogHandler",
        "ACKCostAnalysisHandler",
    ]:
        monkeypatch.setattr(ms, attr, MagicMock())


class TestOAuthConfiguration:
    """Test OAuth configuration and server creation."""

    def test_create_server_without_oauth(self, monkeypatch):
        """OAuth 未启用时，create_main_server 正常工作，auth 为 None。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        settings = _base_settings(enable_oauth=False)
        server = ms.create_main_server(settings_dict=settings)

        # FastMCP stores auth on settings; when None is passed the server
        # should not have an auth provider configured.
        assert server is not None
        # The auth kwarg we passed was None, so _auth_server_provider should
        # reflect that (FastMCP stores it internally).
        assert getattr(server, "_auth_server_provider", None) is None

    def test_create_server_with_oauth_missing_jwks_uri(self, monkeypatch):
        """OAuth 启用但缺少 jwks_uri 时，应抛出 ValueError。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri=None,
            oauth_issuer="https://issuer.example.com",
        )
        with pytest.raises(ValueError, match="oauth-jwks-uri"):
            ms.create_main_server(settings_dict=settings)

    def test_create_server_with_oauth_missing_issuer(self, monkeypatch):
        """OAuth 启用但缺少 issuer 时，应抛出 ValueError。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer=None,
        )
        with pytest.raises(ValueError, match="oauth-issuer"):
            ms.create_main_server(settings_dict=settings)

    def test_create_server_with_oauth_valid_config(self, monkeypatch):
        """OAuth 配置完整时，create_main_server 应创建带 auth 的 FastMCP 实例。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_audience="ack-mcp",
        )
        server = ms.create_main_server(settings_dict=settings)

        assert server is not None
        # JWTVerifier should have been instantiated
        mock_jwt_verifier_cls.assert_called_once()
        call_kwargs = mock_jwt_verifier_cls.call_args
        assert call_kwargs.kwargs.get("jwks_uri") == "https://issuer.example.com/.well-known/jwks.json"
        assert call_kwargs.kwargs.get("issuer") == "https://issuer.example.com"
        assert call_kwargs.kwargs.get("audience") == "ack-mcp"

        # RemoteAuthProvider should have been instantiated with the verifier
        mock_remote_auth_cls.assert_called_once()

    def test_create_server_oauth_with_required_scopes(self, monkeypatch):
        """OAuth 配置了 required_scopes 时，应正确解析逗号分隔的作用域。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_required_scopes="ack:read,ack:write",
        )
        server = ms.create_main_server(settings_dict=settings)

        assert server is not None
        call_kwargs = mock_jwt_verifier_cls.call_args
        assert call_kwargs.kwargs.get("required_scopes") == ["ack:read", "ack:write"]

    def test_create_server_oauth_default_disabled(self, monkeypatch):
        """默认情况下 OAuth 应该是禁用的。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        # 使用 None（不设置 enable_oauth）来测试默认值行为
        settings = _base_settings()  # enable_oauth defaults to False
        server = ms.create_main_server(settings_dict=settings)

        assert server is not None
        assert getattr(server, "_auth_server_provider", None) is None

    def test_create_server_oauth_base_url_default(self, monkeypatch):
        """OAuth 未指定 base_url 时，应使用 host:port 拼接的默认值。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_base_url=None,
            host="0.0.0.0",
            port=9090,
        )
        ms.create_main_server(settings_dict=settings)

        call_kwargs = mock_remote_auth_cls.call_args
        # base_url should fall back to http://host:port
        assert "0.0.0.0" in str(call_kwargs.kwargs.get("base_url", ""))
        assert "9090" in str(call_kwargs.kwargs.get("base_url", ""))

    def test_create_server_oauth_explicit_base_url(self, monkeypatch):
        """OAuth 指定了 base_url 时，应使用指定值。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_base_url="https://mcp.example.com",
        )
        ms.create_main_server(settings_dict=settings)

        call_kwargs = mock_remote_auth_cls.call_args
        assert "mcp.example.com" in str(call_kwargs.kwargs.get("base_url", ""))


class TestOAuthEnvironmentVariables:
    """Test OAuth environment variable support."""

    def test_enable_oauth_from_env(self, monkeypatch):
        """ENABLE_OAUTH 环境变量应该能启用 OAuth（通过 settings_dict 模拟）。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        # 模拟环境变量传入 settings_dict 的效果
        # 在实际 main() 中: enable_oauth = args.enable_oauth or os.getenv("ENABLE_OAUTH", "false").lower() == "true"
        # 这里直接验证当 settings_dict 中 enable_oauth=True 且配置不完整时会报错
        # （证明 enable_oauth 标志被正确识别）
        settings = _base_settings(enable_oauth=True)
        with pytest.raises(ValueError, match="oauth-jwks-uri"):
            ms.create_main_server(settings_dict=settings)

    def test_oauth_config_from_env(self, monkeypatch):
        """OAuth 配置应该能从环境变量读取（通过 main() 的 settings_dict 构建逻辑）。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        # 模拟环境变量最终生成的 settings_dict
        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://from-env.example.com/.well-known/jwks.json",
            oauth_issuer="https://from-env.example.com",
            oauth_audience="env-audience",
            oauth_required_scopes="scope1,scope2,scope3",
        )
        server = ms.create_main_server(settings_dict=settings)

        assert server is not None
        call_kwargs = mock_jwt_verifier_cls.call_args
        assert call_kwargs.kwargs.get("jwks_uri") == "https://from-env.example.com/.well-known/jwks.json"
        assert call_kwargs.kwargs.get("issuer") == "https://from-env.example.com"
        assert call_kwargs.kwargs.get("audience") == "env-audience"
        assert call_kwargs.kwargs.get("required_scopes") == ["scope1", "scope2", "scope3"]


class TestOAuthScopeParsing:
    """Test edge cases for OAuth scope parsing."""

    def test_empty_scopes_string(self, monkeypatch):
        """空字符串 scopes 应该被解析为 None（无强制 scope）。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_required_scopes="",
        )
        ms.create_main_server(settings_dict=settings)

        call_kwargs = mock_jwt_verifier_cls.call_args
        # Empty string → empty list after split/strip → passed as None
        assert call_kwargs.kwargs.get("required_scopes") is None

    def test_scopes_with_extra_whitespace(self, monkeypatch):
        """Scopes 中包含额外空格时应被正确 strip。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_required_scopes=" ack:read , ack:write , ",
        )
        ms.create_main_server(settings_dict=settings)

        call_kwargs = mock_jwt_verifier_cls.call_args
        assert call_kwargs.kwargs.get("required_scopes") == ["ack:read", "ack:write"]

    def test_none_scopes(self, monkeypatch):
        """oauth_required_scopes 为 None 时，required_scopes 应为 None。"""
        _apply_handler_mocks(monkeypatch)
        import main_server as ms

        mock_jwt_verifier_cls = MagicMock()
        mock_remote_auth_cls = MagicMock()

        monkeypatch.setattr(
            "fastmcp.server.auth.providers.jwt.JWTVerifier",
            mock_jwt_verifier_cls,
        )
        monkeypatch.setattr(
            "fastmcp.server.auth.RemoteAuthProvider",
            mock_remote_auth_cls,
        )

        settings = _base_settings(
            enable_oauth=True,
            oauth_jwks_uri="https://issuer.example.com/.well-known/jwks.json",
            oauth_issuer="https://issuer.example.com",
            oauth_required_scopes=None,
        )
        ms.create_main_server(settings_dict=settings)

        call_kwargs = mock_jwt_verifier_cls.call_args
        assert call_kwargs.kwargs.get("required_scopes") is None
