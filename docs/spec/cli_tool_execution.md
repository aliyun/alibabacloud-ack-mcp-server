# CLI 直接执行 Tool 功能设计文档 (`ack-mcp-cli`)

## 1. 需求概述

当前项目所有 tool（如 `ack_kubectl`、`list_clusters` 等）必须通过启动 MCP server 后，由 MCP 客户端（如 Cursor、Claude Desktop）调用。用户希望能够在终端直接调用任意 tool，无需启动 MCP server，方便调试和脚本化使用。

### 目标

- 新增独立 CLI 命令 `ack-mcp-cli`，作为独立入口
- 支持列出所有可用 tools
- 支持查看 tool 的详细参数信息
- 支持通过 CLI 友好的参数调用 tool（自动从 tool schema 生成 `--param-name` 参数）
- 保留 `--args` JSON 格式作为 fallback
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

通过设置 `mcp._lifespan_result` 手动注入 providers，`ctx.lifespan_context` 属性会自动 fallback 到 `_lifespan_result`，无需启动 server 事件循环。

#### Schema-based 参数解析

从每个 tool 的 `parameters` JSON Schema 自动生成 CLI 参数：

| Schema 类型 | CLI 参数类型 | 示例 |
|---|---|---|
| `"type": "string"` | `type=str` | `--cluster-id cxxx` |
| `"type": "integer"` | `type=int` | `--page-size 10` |
| `"type": "boolean"` | `BooleanOptionalAction` | `--is-result-exception / --no-is-result-exception` |
| `"anyOf": [{type}, null]` | optional, `default=None` | `--namespace kube-system` |
| `"required": [...]` | 必填参数 | 缺失时报错退出 |
| 有 `"default": X` | 可选参数 | 未提供时使用 schema 默认值 |

- 参数名：下划线 `_` 转连字符 `-`（如 `cluster_id` → `--cluster-id`）
- description：取 schema description 首行作为 help 文本
- 优先级：显式 CLI 参数 > `--args` JSON > schema defaults

### 3.3 核心组件

#### CLIRunner

唯一的核心类，负责：
1. 调用 `create_main_server(settings)` 创建 FastMCP 实例（所有 tools 自动注册）
2. 初始化 providers（复用 `ACKClusterRuntimeProvider.initialize_providers()`）
3. 通过 `mcp._lifespan_result` 注入 lifespan context
4. 使用 `mcp.list_tools()` 列出所有工具
5. 使用 `mcp.call_tool(name, args)` 执行工具
6. 将 `ToolResult` 序列化为 JSON 输出到 stdout

#### build_tool_arg_parser / parse_tool_args

从 tool 的 JSON Schema 动态生成 argparse 参数解析器，支持：
- 自动类型映射（string/integer/boolean/nullable）
- `_UNSET` 哨兵值区分「用户未提供」与「schema 默认值」
- `--args` JSON 与显式 CLI 参数的合并（CLI 优先）
- 必填参数校验

### 3.4 数据流

```
用户输入 CLI 命令
    ↓
parse_known_args() 解析全局参数 + 子命令 + tool_name
    ↓
create_main_server() 创建 FastMCP 实例
    ↓
初始化 providers → 设置 mcp._lifespan_result
    ↓
从 tool.parameters 动态构建 argparse parser
    ↓
解析 remaining_argv → 合并 CLI 参数 + --args JSON + schema defaults
    ↓
mcp.call_tool(name, merged_args)
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

# 查看 tool 的参数详情
ack-mcp-cli describe <tool_name>

# 调用 tool（schema-based 参数，推荐）
ack-mcp-cli call <tool_name> --param-name value [--param2 value2]

# 调用 tool（JSON 格式 fallback）
ack-mcp-cli call <tool_name> --args '<JSON>'

# 全局参数
ack-mcp-cli [--allow-write] [--region REGION] \
  [--access-key-id AK] [--access-key-secret SK] \
  [--kubeconfig-mode MODE] [--kubeconfig-path PATH] \
  <subcommand>
```

### 4.2 使用示例

```bash
# 列出集群
ack-mcp-cli call list_clusters --page-size 20

# 执行 kubectl 命令
ack-mcp-cli call ack_kubectl --command "get pods -A" --cluster-id cxxx

# 查询审计日志
ack-mcp-cli call query_audit_log --cluster-id cxxx --namespace kube-system --limit 50

# 查看巡检报告（boolean 参数）
ack-mcp-cli call query_inspect_report --cluster-id cxxx --region-id cn-hangzhou --no-is-result-exception

# 获取当前时间（无参数）
ack-mcp-cli call get_current_time

# JSON fallback（复杂参数）
ack-mcp-cli call diagnose_resource --args '{"cluster_id":"c1","resource_type":"pod","resource_target":"{\"namespace\":\"default\",\"name\":\"nginx\"}"}'
```

### 4.3 输出格式

- `list` 子命令：表格格式列出 tool 名称和描述
- `describe` 子命令：显示参数名、CLI flag、类型、是否必填、默认值、描述
- `call` 子命令：JSON 格式输出 tool 执行结果（来自 `ToolResult.structured_content`）
- 错误信息和日志输出到 stderr，不干扰 JSON 结果输出

## 5. 重构内容

### 5.1 Handler ctx 访问方式统一

将所有 handler 中的 `ctx.request_context.lifespan_context` 统一改为 `ctx.lifespan_context`，使其同时兼容 MCP server 模式和 CLI 模式。

### 5.2 KubectlHandler 重构

将 `ack_kubectl` 闭包核心逻辑提取为 `KubectlHandler.execute()` 公开方法。

### 5.3 各 Handler 的 `__init__` 方法调整

配置属性初始化移到 `server is None` 判断之前。

## 6. 安全考虑

- 默认只读模式（`--allow-write` 需显式传入），与 MCP server 模式一致
- 认证参数支持命令行传入和环境变量两种方式
- 日志输出到 stderr，不干扰 JSON 结果输出
