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

改动模式：
```python
# Before
lifespan_context = getattr(ctx.request_context, "lifespan_context", {}) or {}
providers = lifespan_context.get("providers", {}) if isinstance(lifespan_context, dict) else {}
config = lifespan_context.get("config", {}) if isinstance(lifespan_context, dict) else {}

# After
lifespan_context = ctx.lifespan_context or {}
providers = lifespan_context.get("providers", {})
config = lifespan_context.get("config", {})
```

`ctx.lifespan_context` 是 FastMCP 官方 API，当 `request_context` 存在时从中获取，当 `request_context` 为 None 时（CLI 模式）自动 fallback 到 `mcp._lifespan_result`。

### 步骤 2：重构 KubectlHandler

**文件**: `src/kubectl_handler.py`

**改动内容**:
1. 将 `_register_tools()` 内部的 `ack_kubectl` 闭包逻辑提取为公开的 `execute()` 方法
2. `__init__` 中先初始化 `allow_write` 和 `kubectl_timeout` 属性，再判断 `server is None`
3. `_register_tools()` 中的闭包改为调用 `self.execute()` 方法

### 步骤 3：修复各 Handler 的 `__init__` 方法

**文件**:
- `src/ack_cluster_handler.py`
- `src/ack_diagnose_handler.py`
- `src/ack_prometheus_handler.py`
- `src/ack_inspect_handler.py`
- `src/ack_audit_log_handler.py`
- `src/ack_controlplane_log_handler.py`

**改动内容**:
将各 Handler 的 `__init__` 方法中配置属性初始化移到 `server is None` 判断之前。

改动模式：
```python
# Before
def __init__(self, server, settings=None):
    self.settings = settings or {}
    if server is None:
        return
    self.server = server
    self.allow_write = self.settings.get("allow_write", False)

# After
def __init__(self, server, settings=None):
    self.settings = settings or {}
    self.allow_write = self.settings.get("allow_write", False)
    if server is None:
        return
    self.server = server
```

### 步骤 4：创建 CLI 模块

**文件**: `src/cli.py`（新建）

**核心类**:

1. **`CLIRunner`**: CLI 执行器
   - `__init__(settings_dict)` -- 调用 `create_main_server()` 创建 FastMCP 实例，初始化 providers，设置 `mcp._lifespan_result`
   - `list_tools()` -- 通过 `mcp.list_tools()` 列出所有工具
   - `call_tool(tool_name, args_json)` -- 通过 `mcp.call_tool()` 调用指定工具

2. **`build_settings_dict(args)`**: 从 CLI 参数和环境变量构建统一配置字典

3. **`main()`**: CLI 入口函数
   - argparse 定义：
     - 全局参数：`--allow-write`, `--region`, `--access-key-id`, `--access-key-secret`, `--kubeconfig-mode`, `--kubeconfig-path`
     - 子命令 `list`：列出所有工具
     - 子命令 `call <tool_name> --args '<JSON>'`：调用工具

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
- CLIRunner 初始化和 FastMCP 实例创建
- `mcp._lifespan_result` 注入验证
- `mcp.list_tools()` 返回所有 9 个工具
- `mcp.call_tool()` 执行 `get_current_time` 并验证结果
- `list` 子命令输出验证
- `call` 子命令执行和 JSON 输出验证
- 参数解析正确性（`build_settings_dict`）
- 错误处理（不存在的 tool、无效 JSON、非 dict JSON）

**文件**: 各 handler 测试文件中的 `FakeContext`

在所有 `FakeContext` 类中新增 `self.lifespan_context` 属性，同时将使用对象形式 lifespan context 的测试改为 dict 形式，以匹配 handler 中 `ctx.lifespan_context.get()` 的 dict 访问方式。

涉及文件：
- `src/tests/test_ack_cluster_handler.py`
- `src/tests/test_ack_audit_log_handler.py`
- `src/tests/test_ack_controlplane_log_handler.py`
- `src/tests/test_ack_prometheus_handler.py`
- `src/tests/test_ack_inspect_handler.py`
- `src/tests/test_kubectl_handler.py`
- `src/tests/test_kubeconfig_mode.py`

## 文件变更清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/cli.py` | 新建 | CLI 入口模块（复用 FastMCP list_tools/call_tool） |
| `src/ack_cluster_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_diagnose_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_prometheus_handler.py` | 修改 | ctx 访问方式统一（3 处） + __init__ 调整 |
| `src/ack_inspect_handler.py` | 修改 | ctx 访问方式统一 + __init__ 调整 |
| `src/ack_audit_log_handler.py` | 修改 | ctx 访问方式统一（2 处） |
| `src/ack_controlplane_log_handler.py` | 修改 | ctx 访问方式统一（3 处） + __init__ 调整 |
| `src/kubectl_handler.py` | 修改 | ctx 访问方式统一 + 提取 execute() + __init__ 调整 |
| `pyproject.toml` | 修改 | 新增 CLI 入口和模块 |
| `Makefile` | 修改 | 新增 CLI 快捷命令 |
| `src/tests/test_cli.py` | 新建 | CLI 测试（基于 FastMCP API） |
| `src/tests/test_ack_cluster_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_audit_log_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_controlplane_log_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_prometheus_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_ack_inspect_handler.py` | 修改 | FakeContext 增加 lifespan_context 属性 |
| `src/tests/test_kubectl_handler.py` | 修改 | FakeContext 增加 lifespan_context + lifespan context 改为 dict |
| `src/tests/test_kubeconfig_mode.py` | 修改 | FakeContext 增加 lifespan_context + FakeLifespanContext 改为 dict 工厂 |
| `src/main_server.py` | 不变 | MCP server 入口保持独立 |
