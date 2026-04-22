# 安全策略

- [安全策略](#安全策略)
  - [报告安全问题](#报告安全问题)
  - [漏洞管理计划](#漏洞管理计划)
    - [关键更新和安全通知](#关键更新和安全通知)
  - [Network Security Configuration](#network-security-configuration)
    - [Host Binding](#host-binding)
    - [DNS Rebinding Protection](#dns-rebinding-protection)
    - [Authentication (OAuth 2.1)](#authentication-oauth-21)
    - [Transport Security (TLS/HTTPS)](#transport-security-tlshttps)

## 报告安全问题

**请勿创建 ISSUE** 来报告安全问题。请您发送邮件至 **kubernetes-security@service.aliyun.com**，相关安全团队将第一时间启动评估并及时回复。

请您遵循[保密政策](./embargo-policy.md)处理所有与安全相关的问题。

## 漏洞管理计划

### 关键更新和安全通知

我们从以下来源了解关键软件更新和安全威胁：

1. GitHub Security Alerts
2. [Dependabot](https://dependabot.com/) 依赖更新
3. 自动化的Trivy安全扫描

## Network Security Configuration

### Host Binding

By default, the server binds to `127.0.0.1` (localhost), which only allows local access. This is the recommended configuration for development environments.

- **Development**: Use `localhost` or `127.0.0.1` (default) for local-only access.
- **Production**: If network access is required, change the `--host` parameter, but **always** combine it with Origin validation (`--allowed-origins`) and authentication (e.g., reverse proxy). Using a reverse proxy (such as Nginx or Envoy) in front of the server is strongly recommended for production deployments.

### DNS Rebinding Protection

The server includes a built-in Origin header validation middleware, compliant with the **MCP 2025-03-26 specification MUST-level requirement** for DNS rebinding protection.

**How it works:**

- Requests **without** an `Origin` header (e.g., non-browser direct API calls) are allowed through.
- When an explicit `--allowed-origins` list is configured, requests whose `Origin` is **not in the allow list** receive a `403 Forbidden` response.
- When the server is bound to `localhost`/`127.0.0.1` and no explicit allowed origins are configured, only localhost origins are automatically permitted; other origins receive `403 Forbidden`.
- **Important:** When the server is bound to a non-localhost address (e.g., `0.0.0.0`) and no `--allowed-origins` are configured, **all requests with `Origin` headers will be rejected** with `403 Forbidden`. You **must** configure `--allowed-origins` or `ALLOWED_ORIGINS` before exposing the server to the network.

**Configuration:**

Use the `--allowed-origins` CLI parameter (comma-separated list):

```bash
python -m src.main_server --transport http --host 127.0.0.1 --port 8000 \
  --allowed-origins "http://localhost:3000,https://myapp.example.com"
```

Or set the `ALLOWED_ORIGINS` environment variable:

```bash
export ALLOWED_ORIGINS="http://localhost:3000,https://myapp.example.com"
python -m src.main_server --transport http --host 127.0.0.1 --port 8000
```

### Authentication (OAuth 2.1)

This server supports optional OAuth 2.1 authentication for HTTP/SSE transport, compliant with the 
[MCP 2025-11-25 Authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization).

**Enabling OAuth Authentication:**

```bash
python -m src.main_server --transport http --enable-oauth \
  --oauth-jwks-uri "https://your-auth-provider.com/.well-known/jwks.json" \
  --oauth-issuer "https://your-auth-provider.com" \
  --oauth-audience "alibabacloud-ack-mcp-server"
```

Or via environment variables:
```bash
export ENABLE_OAUTH=true
export OAUTH_JWKS_URI=https://your-auth-provider.com/.well-known/jwks.json
export OAUTH_ISSUER=https://your-auth-provider.com
export OAUTH_AUDIENCE=alibabacloud-ack-mcp-server
```

**Configuration Parameters:**

| Parameter | Env Variable | Required | Description |
|-----------|-------------|----------|-------------|
| `--enable-oauth` | `ENABLE_OAUTH` | No | Enable OAuth 2.1 authentication (default: false) |
| `--oauth-jwks-uri` | `OAUTH_JWKS_URI` | Yes* | JWKS endpoint URI for JWT public key retrieval |
| `--oauth-issuer` | `OAUTH_ISSUER` | Yes* | Expected JWT token issuer |
| `--oauth-audience` | `OAUTH_AUDIENCE` | No | Expected JWT audience claim |
| `--oauth-base-url` | `OAUTH_BASE_URL` | No | Public base URL of this server (auto-detected if omitted) |
| `--oauth-required-scopes` | `OAUTH_REQUIRED_SCOPES` | No | Comma-separated required OAuth scopes |

*Required when `--enable-oauth` is set.

**What you get when OAuth is enabled:**
- Bearer token validation on all HTTP/SSE requests (JWT with automatic key rotation)
- `/.well-known/oauth-protected-resource` endpoint (RFC 9728) for client discovery
- Standard `401 Unauthorized` with `WWW-Authenticate` header for unauthenticated requests
- Standard `403 Forbidden` for insufficient scope
- STDIO transport is unaffected (no authentication required)

**Supported OIDC Providers:**
- Keycloak
- Okta / Auth0
- Azure AD (Entra ID)
- Google Identity Platform
- Any standard OIDC provider with JWKS endpoint

**For deployments without OAuth:**

If OAuth is not enabled, we recommend these alternatives for production:
- Use a reverse proxy (Nginx, Envoy) with authentication
- Use an API Gateway with built-in auth
- Use Kubernetes NetworkPolicy or Service Mesh for network isolation
- Restrict access via VPN or private network (VPC) boundaries

### Transport Security (TLS/HTTPS)

- **Production environments should always use HTTPS/TLS** to encrypt traffic between clients and the server.
- TLS termination is best handled by a reverse proxy (e.g., Nginx, Envoy, or a cloud load balancer).
- The MCP specification requires that authorization endpoints **must** use HTTPS.
