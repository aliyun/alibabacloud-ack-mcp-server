# CLI 直接执行 Tool 功能实施计划 (`ack-mcp-cli`)

## 实施步骤

### 步骤 1：统一 Handler 中的 ctx 访问方式

**文件**:
- `src/ack_cluster_handler.py`
- `src/ack_diagnose_handler.py`
- `src/ack_prometheus_handler.py`
- `src/ack_inspect_handler.py`
- `src/ack_audit_log_handler.py`
- `src/ack_controlplane_log_handler.py`
- `src/kubectl_handler.py`

**改动内容**:
将所有 handler 中的 `ctx.request_context.lifespan_context` 统一改为 `ctx.lifespan_context`。

`ctx.lifespan_context` 是 FastMCP 官方 API，当 `request_context` 存在时从中获取，当 `request_context` 为 None 时（CLI 模式）自动 fallback 到 `mcp._lifespan_result`。

### 步骤 2：重构 KubectlHandler

**文件**: `src/kubectl_handler.py`

**改动内容**:
1. 将 `_register_tools()` 内部的 `ack_kubectl` 闭包逻辑提取为公开的 `execute()` 方法
2. `__init__` 中先初始化 `allow_write` 和 `kubectl_timeout` 属性，再判断 `server is None`
3. `_register_tools()` 中的闭包改为调用 `self.execute()` 方法

### 步骤 3：修复各 Handler 的 `__init__` 方法

将各 Handler 的 `__init__` 方法中配置属性初始化移到 `server is None` 判断之前。

### 步骤 4：创建 CLI 模块

**文件**: `src/cli.py`（新建）

**核心组件**:

1. **`_resolve_param_type(prop_schema)`** -- 从 JSON Schema 属性中提取有效类型（处理 `anyOf` nullable 模式）

2. **`build_tool_arg_parser(tool_name, parameters)`** -- 根据 tool 的 JSON Schema 动态创建 argparse.ArgumentParser
   - 所有参数使用 `_UNSET` 哨兵作为 default，区分「用户未传」和「schema 默认值」
   - 所有参数在 argparse 层面均为 optional（必填校验在 parse_tool_args 中进行）
   - 始终附加 `--args` JSON fallback 参数

3. **`parse_tool_args(tool_name, parameters, argv)`** -- 解析 CLI 参数并合并
   - 优先级：显式 CLI 参数 > `--args` JSON > schema defaults
   - `None` 默认值不加入结果（避免传入多余参数）
   - 校验 required 参数是否缺失

4. **`CLIRunner`**: CLI 执行器
   - `__init__(settings_dict)` -- 调用 `create_main_server()` 创建 FastMCP 实例，初始化 providers，设置 `mcp._lifespan_result`
   - `list_tools()` -- 通过 `mcp.list_tools()` 列出所有工具
   - `describe_tool(tool_name)` -- 显示工具参数详情（名称、CLI flag、类型、必填/默认值、描述）
   - `call_tool(tool_name, tool_args)` -- 通过 `mcp.call_tool()` 调用指定工具

5. **`main()`**: CLI 入口函数
   - 使用 `parse_known_args()` 先解析全局参数和子命令
   - `call` 子命令：获取 tool schema 后用 `parse_tool_args` 解析 remaining_argv
   - 子命令：`list`、`describe <tool_name>`、`call <tool_name> [--param-name value ...]`

### 步骤 5：更新项目配置

**文件**: `pyproject.toml`
- `[project.scripts]` 新增: `ack-mcp-cli = "cli:main"`
- `[tool.setuptools]` 的 `py-modules` 新增: `"cli"`

**文件**: `Makefile`
- 新增 `run-cli-list` 目标
- 新增 `run-cli-call` 目标

### 步骤 6：更新测试

**文件**: `src/tests/test_cli.py`（新建）

**测试覆盖**:
- `_resolve_param_type` 类型解析（string/integer/boolean/nullable/无类型）
- `build_tool_arg_parser` 动态参数生成（string required/integer default/boolean/nullable）
- `parse_tool_args` 合并逻辑（CLI only / JSON only / CLI override JSON / schema default / None 默认省略 / 缺失必填报错）
- `CLIRunner` 功能（list/describe/call/unknown tool）
- FastMCP 集成（lifespan_result 注入、list_tools 返回、call_tool 执行）
- `build_settings_dict` 参数构建

**文件**: 各 handler 测试文件中的 `FakeContext`
- 新增 `self.lifespan_context` 属性
- lifespan context 改为 dict 形式

## 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/cli.py` | 新建 | CLI 入口（schema-based args + FastMCP call_tool） |
| `src/ack_cluster_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_diagnose_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_prometheus_handler.py` | 修改 | ctx 访问方式统一（3 处） + __init__ 调整 |
| `src/ack_inspect_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_audit_log_handler.py` | 修改 | ctx 访问方式统一（2 处） |
| `src/ack_controlplane_log_handler.py` | 修改 | ctx 访问方式统一（3 处） + __init__ 调整 |
| `src/kubectl_handler.py` | 修改 | ctx 统一 + 提取 execute() + __init__ 调整 |
| `pyproject.toml` | 修改 | 新增 CLI 入口和模块 |
| `Makefile` | 修改 | 新增 CLI 快捷命令 |
| `src/tests/test_cli.py` | 新建 | CLI 测试（schema 解析 + 参数合并 + FastMCP 集成） |
| `src/tests/test_ack_cluster_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_audit_log_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_controlplane_log_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_prometheus_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_inspect_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_kubectl_handler.py` | 修改 | FakeContext + lifespan context 改为 dict |
| `src/tests/test_kubeconfig_mode.py` | 修改 | FakeContext + FakeLifespanContext 改为 dict 工厂 |
| `src/main_server.py` | 不变 | MCP server 入口保持独立 |
