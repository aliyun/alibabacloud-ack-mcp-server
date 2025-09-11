# Alibaba Cloud Container Service MCP Server

阿里云 ACK MCP Server（Python 版）。本项目基于 MCP（Model Context Protocol），将 ACK 管理、Kubernetes 原生操作与可观测性能力统一为标准工具集，便于以同一接口被各类 AI 代理或自动化系统调用。

- **技术栈**: fastmcp、Python、Loguru、(部分子服务) 阿里云 SDK、Kubernetes Python Client
- **架构**: 主服务 + 多个子 MCP Server（通过 FastMCP 代理挂载），各子服务亦可独立运行
- 详细架构请参阅 `DESIGN.md`

## 功能特性

- **ACK 管理**
  - `scale_nodepool`、`remove_nodepool_nodes`
  - `describe_task_info`
  - `create_cluster_diagnosis`、`get_cluster_diagnosis_result`
- **Kubernetes 原生操作**
  - 执行 `kubectl` 类操作（读写可控）、获取日志/事件，列表/详情/增删改
- **可观测性**
  - Prometheus（ARMS 指标）PromQL 查询、自然语言转 PromQL
  - SLS 日志 SQL 查询、自然语言转 Log-SQL、失败诊断
  - 云监控（CMS）资源指标与告警能力
- **工程能力**
  - 分层清晰：工具层、服务层、认证层解耦
  - 动态凭证注入：按请求传入 AK 或默认环境凭证
  - 健壮错误传递与类型化输出

## 安装

- 使用 `pip`:
```bash
pip install -r requirements.txt
```

- 或使用 `uv`（如需与 `uv.lock` 对齐）:
```bash
uv sync
```

## 配置

支持通过环境变量或 `.env`（若安装了 `python-dotenv` 将自动加载）。关键项：

```env
# 阿里云凭证与区域
ACCESS_KEY_ID=your-ak-id
ACCESS_KEY_SECRET=your-ak-secret
REGION_ID=cn-hangzhou
DEFAULT_CLUSTER_ID=

# 其他可选
CACHE_TTL=300
CACHE_MAX_SIZE=1000
FASTMCP_LOG_LEVEL=INFO
DEVELOPMENT=false
```

说明：
- 未设置 `ACCESS_KEY_ID/ACCESS_KEY_SECRET` 时，部分需要云 API 的功能不可用（会警告）。
- 可以通过命令行参数覆盖上述项（见下）。

## 运行

主服务入口：`src/main_server.py`

- 标准（stdio）模式：
```bash
python -m src.main_server
```

- SSE（HTTP）模式：
```bash
python -m src.main_server --transport sse --host 0.0.0.0 --port 8000
```

常用参数：
- `--region, -r`: 指定阿里云区域（默认 `REGION_ID` 或 `cn-hangzhou`）
- `--access-key-id`: 覆盖 `ACCESS_KEY_ID`
- `--access-key-secret`: 覆盖 `ACCESS_KEY_SECRET`
- `--default-cluster-id`: 设置默认集群 ID
- `--allow-write`: 启用写入操作（默认只读）
- `--transport [stdio|sse]`、`--host`、`--port`

## 认证与凭证注入

- 默认走环境凭证（上文环境变量）。
- 对齐各子服务的 AK 传入逻辑：内部统一以凭证客户端+配置对象传入 `access_key_id/access_key_secret/region_id/endpoint`。
- 在 SSE（HTTP）模式下，可按需在上层网关增加请求级别的 AK 头部注入；如未注入，则回退环境凭证。具体头部键名可按网关实现映射为环境注入，本项目内部已对 AK 读取进行统一封装。

## 子服务一览（代理挂载）

主服务会挂载以下子 MCP Server（路径前缀）：
- `ack-cluster`：ACK 集群管理与诊断
- `ack-addon`：ACK 插件管理
- `ack-nodepool`：ACK 节点池管理
- `kubernetes`：Kubernetes 客户端操作
- `ack-diagnose`：集群诊断能力
- `observability-prometheus`：PromQL / 指标相关
- `observability-sls`：SLS 日志查询与分析
- `observability-cloudmonitor`：云监控资源能力
- `audit-log`：Kubernetes 审计日志查询

> 具体可用工具列表与参数请参阅各子模块 `src/<module>/README.md` 或测试用例。

## 测试

使用 pytest：
```bash
# 运行全部
pytest -v

# 仅运行架构测试
pytest src/tests/test_architecture.py -v

# 或使用脚本
./run_tests.sh all
```

如需安装测试依赖：
```bash
pip install pytest pytest-asyncio
# or
uv add pytest pytest-asyncio
```

## 常见问题

- 启动后提示未配置 AK：请确认 `ACCESS_KEY_ID/ACCESS_KEY_SECRET` 是否在环境或 `.env` 中设置，或通过命令行参数传入。
- 仅需 Kubernetes 客户端能力：无需配置 AK，但需本地 `KUBECONFIG` 或在集群内运行。
- SSE 模式下如何鉴权：可在外层接入层（如反向代理）统一做鉴权与 Header 注入，本服务仅消费已注入的凭证。

## 许可证

Apache-2.0。详见 `LICENSE`。
