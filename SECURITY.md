# 安全策略

- [安全策略](#安全策略)
  - [报告安全问题](#报告安全问题)
  - [漏洞管理计划](#漏洞管理计划)
    - [关键更新和安全通知](#关键更新和安全通知)
  - [Network Security Configuration](#network-security-configuration)
    - [Host Binding](#host-binding)
    - [DNS Rebinding Protection](#dns-rebinding-protection)
    - [Authentication Recommendations](#authentication-recommendations)
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

### Authentication Recommendations

The [MCP 2025-11-25 Authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) defines an optional OAuth 2.1 authorization framework for HTTP/SSE transport. The current version of this server does not include built-in authentication.

For production deployments, we recommend the following approaches to secure your MCP server:

- **Reverse Proxy**: Use Nginx or Envoy in front of the server with authentication modules
- **API Gateway**: Use an API Gateway with built-in authentication and authorization
- **Kubernetes NetworkPolicy / Service Mesh**: Restrict network access at the infrastructure level
- **VPN / Private Network**: Limit access to trusted networks (e.g., VPC boundaries)

### Transport Security (TLS/HTTPS)

- **Production environments should always use HTTPS/TLS** to encrypt traffic between clients and the server.
- TLS termination is best handled by a reverse proxy (e.g., Nginx, Envoy, or a cloud load balancer).
- The MCP specification requires that authorization endpoints **must** use HTTPS.
