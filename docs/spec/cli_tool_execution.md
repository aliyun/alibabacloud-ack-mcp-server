# CLI 直接执行 Tool 功能设计文档 (`ack-mcp-cli`)

## 1. 需求概述

当前项目所有 tool（如 `ack_kubectl`、`list_clusters` 等）必须通过启动 MCP server 后，由 MCP 客户端（如 Cursor、Claude Desktop）调用。用户希望能够在终端直接调用任意 tool，无需启动 MCP server，方便调试和脚本化使用。

### 目标

- 新增独立 CLI 命令 `ack-mcp-cli`，作为独立入口
- 支持列出所有可用 tools
- 支持通过命令行调用任意 tool，传入 JSON 参数，输出 JSON 结果
- 现有 `alibabacloud-ack-mcp-server` 入口完全不变

## 2. 已注册的 Tools

| Tool 名称 | Handler | 说明 |
|---|---|---|
| `list_clusters` | ACKClusterHandler | 获取所有 region 下 ACK 集群列表 |
| `ack_kubectl` | KubectlHandler | 执行 kubectl 命令 |
| `query_prometheus` | PrometheusHandler | 查询 Prometheus 数据 |
| `query_prometheus_metric_guidance` | PrometheusHandler | 获取 Prometheus 指标定义和最佳实践 |
| `diagnose_resource` | DiagnoseHandler | 对 ACK 集群资源进行诊断 |
| `query_inspect_report` | InspectHandler | 查询集群健康巡检报告 |
| `query_audit_log` | ACKAuditLogHandler | 查询 K8s 审计日志 |
| `get_current_time` | ACKAuditLogHandler | 获取当前时间 |
| `query_controlplane_logs` | ACKControlPlaneLogHandler | 查询控制面组件日志 |

## 3. 架构设计

### 3.1 整体架构

`ack-mcp-cli` 是独立于 MCP server 的入口，两者互不影响。CLI 直接复用 `create_main_server()` 创建的 FastMCP 实例，通过 FastMCP 原生的 `list_tools()` / `call_tool()` API 发现和执行 tools。

```
alibabacloud-ack-mcp-server (main_server:main)  -->  FastMCP Server (stdio/sse/http)
ack-mcp-cli (cli:main)                          -->  FastMCP call_tool() 直接调用
```

### 3.2 核心机制

#### Provider 注入

FastMCP 的 `Context` 对象有一个 `lifespan_context` 属性，在正常 server 模式下由 lifespan 回调函数注入。在 CLI 模式下，通过设置 `mcp._lifespan_result` 手动注入 providers，`ctx.lifespan_context` 属性会自动 fallback 到 `_lifespan_result`，无需启动 server 事件循环。

#### Handler ctx 访问方式

所有 handler 统一使用 `ctx.lifespan_context`（FastMCP 官方 API）访问 providers 和 config，该属性在 MCP server 模式和 CLI 模式下均可正常工作。

### 3.3 核心组件

#### CLIRunner

唯一的核心类，负责：
1. 调用 `create_main_server(settings)` 创建 FastMCP 实例（所有 tools 自动注册）
2. 初始化 providers（复用 `ACKClusterRuntimeProvider.initialize_providers()`）
3. 通过 `mcp._lifespan_result` 注入 lifespan context
4. 使用 `mcp.list_tools()` 列出所有工具
5. 使用 `mcp.call_tool(name, args)` 执行工具（FastMCP 自动注入 `ctx`）
6. 将 `ToolResult` 序列化为 JSON 输出到 stdout

### 3.4 数据流

```
用户输入 CLI 命令
    ↓
argparse 解析参数（全局参数 + 子命令）
    ↓
create_main_server() 创建 FastMCP 实例
    ↓
初始化 providers（认证、SDK 客户端工厂等）
    ↓
设置 mcp._lifespan_result（注入 providers + config）
    ↓
mcp.list_tools() 或 mcp.call_tool(name, args)
    ↓
ToolResult.structured_content 序列化为 JSON
    ↓
输出到 stdout
```

## 4. 用户界面设计

### 4.1 命令行格式

```bash
# 列出所有可用 tools
ack-mcp-cli list

# 调用 tool（JSON 参数）
ack-mcp-cli call <tool_name> --args '<JSON>'

# 全局参数
ack-mcp-cli [--allow-write] [--region REGION] \
  [--access-key-id AK] [--access-key-secret SK] \
  [--kubeconfig-mode MODE] [--kubeconfig-path PATH] \
  <subcommand>
```

### 4.2 输出格式

- `list` 子命令：表格格式列出 tool 名称和描述
- `call` 子命令：JSON 格式输出 tool 执行结果（来自 `ToolResult.structured_content`）
- 错误信息和日志输出到 stderr，不干扰 JSON 结果输出

## 5. 重构内容

### 5.1 Handler ctx 访问方式统一

将所有 handler 中的 `ctx.request_context.lifespan_context` 统一改为 `ctx.lifespan_context`，使其同时兼容 MCP server 模式（有 request_context）和 CLI 模式（无 request_context，fallback 到 `_lifespan_result`）。

涉及文件中的 `_get_cs_client` / `_get_sls_client` 等辅助函数和 handler 方法：
- `src/ack_cluster_handler.py`
- `src/ack_diagnose_handler.py`
- `src/ack_prometheus_handler.py`
- `src/ack_inspect_handler.py`
- `src/ack_audit_log_handler.py`
- `src/ack_controlplane_log_handler.py`
- `src/kubectl_handler.py`

### 5.2 KubectlHandler 重构

将 `_register_tools()` 内的 `ack_kubectl` 闭包核心逻辑提取为 `KubectlHandler.execute()` 公开方法，闭包改为委托调用 `self.execute()`。

### 5.3 各 Handler 的 `__init__` 方法调整

配置属性初始化（如 `allow_write`、`kubectl_timeout`）移到 `server is None` 判断之前，确保 CLI 模式下也能正常初始化。

## 6. 安全考虑

- 默认只读模式（`--allow-write` 需显式传入），与 MCP server 模式一致
- 认证参数支持命令行传入和环境变量两种方式
- 日志输出到 stderr，不干扰 JSON 结果输出
