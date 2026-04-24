# SEP-001: MCP Server 安全与鉴权增强计划

## 概述
- 背景：MCP 2025-11-25 规范对 SSE/HTTP 传输层的安全和鉴权要求
- 目标：逐步补齐安全能力，达到 MCP 规范合规性
- 状态：进行中

## 当前安全现状

### 已完成项
1. **Origin 头校验中间件**（MCP 规范 MUST 级别）
   - 实现了 `OriginValidationMiddleware` ASGI 中间件
   - 采用 fail-closed 策略：非 localhost 绑定 + 未配置白名单时拒绝所有带 Origin 的请求
   - 支持 `--allowed-origins` CLI 参数和 `ALLOWED_ORIGINS` 环境变量
   - 文件：`src/main_server.py`

2. **默认安全绑定**
   - 所有入口（Makefile、Dockerfile、Helm Chart）默认绑定 `127.0.0.1`
   - Helm Chart 支持通过 `host` values 参数配置
   - 文件：`Makefile`、`deploy/Dockerfile`、`deploy/helm/`

3. **安全文档**
   - SECURITY.md 包含网络安全配置、DNS Rebinding 防护、认证建议、TLS 建议
   - README.md 包含安全注意事项和 `--allowed-origins` 使用说明

## MCP 2025-11-25 鉴权规范要求

### 规范核心要点
- 鉴权对 MCP 实现是 **OPTIONAL（可选的）**
- HTTP 传输 SHOULD 遵循该规范，STDIO 传输 SHOULD NOT
- 基于 OAuth 2.1 (IETF DRAFT)、RFC 8414、RFC 7591、RFC 9728、RFC 6750
- 规范参考：https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

### MUST 级别要求（一旦实现 OAuth 则强制）
1. 受保护资源元数据 (RFC 9728) — `/.well-known/oauth-protected-resource` 端点
2. 授权服务器发现 — RFC 8414 或 OpenID Connect Discovery
3. Bearer Token 验证 — `Authorization: Bearer <token>` 头提取和验证
4. WWW-Authenticate 头 — 401 响应中包含元数据指针
5. PKCE 支持 — 授权码流程必须支持 S256
6. OAuth 2.1 完整实现 — 为机密客户端和公开客户端

### SHOULD 级别要求
1. Client ID Metadata Documents (CIMD) — 新推荐的客户端注册方式（取代 DCR）
2. 作用域 (Scope) 管理 — WWW-Authenticate 中包含 scope 参数
3. HTTPS/TLS — 生产环境
4. Step-Up Authorization — 增量作用域请求

## 差距分析

### 与 MCP 2025-11-25 的对比

| 要求 | 规范级别 | 当前状态 | 计划阶段 |
|------|---------|---------|---------|
| Origin 头校验 | MUST | ✅ 已完成 | - |
| 默认 localhost 绑定 | SHOULD | ✅ 已完成 | - |
| 安全文档 | Best Practice | ✅ 已完成 | - |
| 受保护资源元数据 (RFC 9728) | MUST* | ❌ 缺失 | Phase 1 |
| 授权服务器发现 (RFC 8414) | MUST* | ❌ 缺失 | Phase 1 |
| Bearer Token 验证 | MUST* | ❌ 缺失 | Phase 1 |
| WWW-Authenticate 头响应 | MUST* | ❌ 缺失 | Phase 1 |
| PKCE 支持 | MUST* | ❌ 缺失 | Phase 1 |
| 作用域定义和管理 | SHOULD | ❌ 缺失 | Phase 2 |
| 工具级权限检查 | SHOULD | ❌ 缺失 | Phase 2 |
| Step-Up Authorization | SHOULD | ❌ 缺失 | Phase 3 |
| CIMD/DCR 客户端注册 | SHOULD/MAY | ❌ 缺失 | Phase 4 |
| HTTPS/TLS 强制 | SHOULD | ⚠️ 通过反向代理 | 文档指导 |

*标注 MUST* 表示：OAuth 本身是 OPTIONAL，但一旦选择实现则为 MUST

### FastMCP 框架支持情况

FastMCP 2.12.4 已内置以下能力（配置即可，无需自定义开发）：
- Bearer Token 验证（JWTVerifier / IntrospectionTokenVerifier）
- `/.well-known/oauth-protected-resource` 端点自动生成
- OAuth Server Metadata Discovery 自动生成
- WWW-Authenticate 头自动生成
- 401/403 标准错误响应
- RemoteAuthProvider（对接外部 OIDC 提供者）
- OAuthProxy（对接 GitHub/Google/Azure 等不支持 DCR 的提供者）

## 实施路线图

### Phase 1: 基础 OAuth 2.1 资源服务器（优先级：高）

**目标**：实现最小可行的 OAuth 2.1 资源服务器，满足所有 MUST 级别要求

**预计工作量**：2-3 天

**核心改动**：

1. **`src/main_server.py`** — FastMCP OAuth 集成
   - 使用 `FastMCP(auth=RemoteAuthProvider(...))` 集成外部 OIDC 提供者
   - 配置 JWTVerifier 进行令牌验证
   - 添加 `OAUTH_ENABLED` 开关（默认 false，保持向后兼容）

2. **`src/config.py`** — OAuth 配置项
   - `OAUTH_ENABLED` — 是否启用 OAuth 鉴权
   - `OAUTH_JWKS_URI` — JWKS 公钥端点
   - `OAUTH_ISSUER` — 令牌签发者
   - `OAUTH_AUDIENCE` — 令牌受众

3. **`.env.example`** — OAuth 环境变量示例

4. **自动获得的能力**（由 FastMCP 提供）：
   - `/.well-known/oauth-protected-resource` 端点
   - RFC 8414 授权服务器发现
   - Bearer Token 提取和验证
   - WWW-Authenticate 头生成
   - 401/403 标准响应

**关键设计决策**：
- 默认关闭 OAuth，不影响现有部署
- STDIO 传输不启用 OAuth（符合规范）
- 支持对接任意 OIDC 提供者（Keycloak、Okta、Azure AD 等）

### Phase 2: 作用域和权限管理（优先级：中）

**目标**：为每个 MCP 工具定义和校验作用域

**预计工作量**：3-5 天

**核心改动**：

1. 定义应用作用域：
   - `ack:cluster:read` — 读取集群信息
   - `ack:cluster:write` — 修改集群配置
   - `ack:kubectl:execute` — 执行 kubectl 命令
   - `ack:diagnose:read` — 运行诊断
   - `ack:observe:read` — 查询监控/日志数据
   - `ack:cost:read` — 查询成本分析
   - `ack:inspect:read` — 巡检报告查询

2. 在各 Handler 中添加作用域验证
3. 实现 Scope Selection Strategy 回退逻辑
4. 在 WWW-Authenticate 401 响应中包含 scope 参数

### Phase 3: 高级鉴权功能（优先级：低）

**目标**：Step-Up Authorization 和增量作用域

**预计工作量**：5-7 天

**核心改动**：
1. 支持运行时逐步请求新作用域
2. 权限不足时的增量请求机制
3. Token Refresh 支持
4. Token Introspection 端点（可选）

### Phase 4: 客户端注册支持（优先级：低）

**目标**：支持客户端自注册

**预计工作量**：2-4 天

**核心改动**：
1. 对接支持 DCR 的授权服务器（FastMCP 自动提供）
2. 如使用 GitHub/Google 等，使用 OAuthProxy
3. 可选的 Client ID Metadata Documents (CIMD) 支持

## 安全风险评估

### 当前风险等级

| 风险项 | 等级 | 缓解措施 |
|--------|------|---------|
| 无令牌验证（HTTP/SSE 模式） | 高 | Phase 1 实现 OAuth；短期使用反向代理 |
| 无作用域限制 | 中 | Phase 2 实现权限管理 |
| DNS Rebinding 攻击 | 已缓解 | Origin 头校验已实现 |
| 网络暴露 | 已缓解 | 默认 localhost 绑定 |

### 生产部署过渡建议（Phase 1 完成前）
- 使用反向代理（Nginx/Envoy）添加外部身份认证
- 使用 API Gateway 处理鉴权
- 利用 Kubernetes NetworkPolicy 或 Service Mesh 实现网络隔离
- 基于 VPN 或专有网络限制访问来源

## 参考资料

### MCP 规范
- Authorization: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- Transports: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports

### RFC 标准
- RFC 6750 — Bearer Token Usage
- RFC 7591 — Dynamic Client Registration
- RFC 8414 — Authorization Server Metadata
- RFC 9728 — Protected Resource Metadata

### FastMCP 文档
- 认证概览: https://gofastmcp.com/servers/auth
- Remote OAuth: https://gofastmcp.com/servers/auth/remote-oauth
- OAuth Proxy: https://gofastmcp.com/servers/auth/oauth-proxy

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-04-22 | v1.0 | 初始版本 — 完成 Origin 校验、默认安全绑定、安全文档 |
| 2026-04-22 | v1.1 | 回滚 — 移除 OAuth 集成，待确认 FastMCP 端点自动生成机制后重新实现 |
