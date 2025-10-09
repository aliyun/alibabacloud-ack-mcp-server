# 阿里云容器服务 MCP Server (ack-mcp-server)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.12.2+-green.svg)](https://github.com/jlowin/fastmcp)

一个基于 MCP（Model Context Protocol）的阿里云容器服务智能助手，将 ACK 集群管理、Kubernetes 原生操作与可观测性能力统一为标准化工具集，供 AI 代理或自动化系统调用。


## 🌟 概述 & 功能简介

### 🎯 核心功能

**阿里云 ACK 管理**
- 节点池扩缩容 (`scale_nodepool`、`remove_nodepool_nodes`)
- 任务查询 (`describe_task_info`)
- 集群诊断 (`create_cluster_diagnosis`、`get_cluster_diagnosis_result`)
- 集群健康巡检 (`query_inspect_report`)

**Kubernetes 原生操作**
- 执行 `kubectl` 类操作（读写权限可控）
- 获取日志、事件，资源的增删改查
- 支持所有标准 Kubernetes API

**全方位可观测性**
- **Prometheus**: ARMS 指标查询、自然语言转 PromQL
- **SLS 日志**: SQL 查询、自然语言转 SLS-SQL、智能故障诊断
- **云监控**: 资源指标与告警能力
- **审计日志**: Kubernetes 操作审计追踪

**企业级工程能力**
- 🏗️ 分层架构：工具层、服务层、认证层完全解耦
- 🔐 动态凭证注入：支持请求级 AK 注入或环境凭证
- 📊 健壮错误处理：结构化错误输出与类型化响应
- 📦 模块化设计：各子服务可独立运行

### 🎬 演示效果

// TODO


### 🏆 核心优势

- **🤖 AI 原生**: 专为 AI 代理设计的标准化接口
- **🔧 统一工具集**: 一站式容器运维能力整合
- **⚡ 高性能**: 异步处理，支持并发调用
- **🛡️ 企业级**: 完善的认证、授权、日志机制
- **📈 可扩展**: 插件化架构，轻松扩展新功能

### 📈 Benchmark 效果验证 (持续更新中)

基于实际场景的 AI 能力测评，支持多种 AI 代理和大模型的效果对比：

| 任务场景 | AI 代理 | 大模型 | 成功率 | 处理时间 |
|------|------|------|-------|--------|
| Pod OOM 修复 | qwen_code | qwen3-coder-plus | ✅ 100% | 2.3min |
| 集群健康检查 | qwen_code | qwen3-coder-plus | ✅ 95% | 6.4min |
| 资源异常诊断 | kubectl-ai | qwen3-32b | ✅ 90% | 4.1min |
| 历史资源分析 | qwen_code | qwen3-coder-plus | ✅ 85% | 3.8min |

最新 Benchmark 报告参见 [`benchmarks/results/`](benchmarks/results/) 目录。

---

## 🚀 如何使用 & 运行

### 💻 环境准备

**构建环境要求**
- Python 3.12+
- 阿里云账号及 AccessKey、AccessSecretKey
- 已创建的 ACK 集群（可选）
- ACK集群开启公网访问的kubeconfig or ack-mcp-server本地网络可访问的kubeconfig配置（置于.kube/config中）

**安装依赖**

使用 `uv`（推荐）：
```bash
uv sync
```

或使用 `pip`：
```bash
pip install -r requirements.txt
```

### ⚙️ 配置设置

创建 `.env` 文件（可参考 `.env.example`）：

```env
# 阿里云凭证与地域
ACCESS_KEY_ID=your-access-key-id
ACCESS_KEY_SECRET=your-access-key-secret
REGION_ID=cn-hangzhou
DEFAULT_CLUSTER_ID=your-cluster-id  # 可选

# 缓存配置
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# 日志配置
FASTMCP_LOG_LEVEL=INFO
DEVELOPMENT=false
```

> ⚠️ **注意**: 未设置 ACCESS_KEY_ID/ACCESS_KEY_SECRET 时，部分依赖云 API 的功能不可用。

### 📍 使用 Helm 部署

在 Kubernetes 集群中部署：

```bash
# 克隆代码仓库
git clone https://github.com/aliyun/alibabacloud-cs-mcp-server
cd alibabacloud-cs-mcp-server

# 使用 Helm 部署
helm install ack-mcp-server ./deploy/helm\ chart/ \
  --set config.accessKeyId="your-access-key-id" \
  --set config.accessKeySecret="your-access-key-secret" \
  --set config.regionId="cn-hangzhou"
```

### 📦 使用 Docker 镜像

```bash
# 拉取镜像
docker pull registry.cn-hangzhou.aliyuncs.com/acs/ack-mcp-server:latest

# 运行容器
docker run -d \
  --name ack-mcp-server \
  -e ACCESS_KEY_ID="your-access-key-id" \
  -e ACCESS_KEY_SECRET="your-access-key-secret" \
  -e REGION_ID="cn-hangzhou" \
  -p 8000:8000 \
  registry.cn-hangzhou.aliyuncs.com/acs/ack-mcp-server:latest \
  python -m src.main_server --transport sse --host 0.0.0.0 --port 8000 --allow-write
```

### 💻 使用 Binary 方式

下载预编译的二进制文件：

```bash
# 构建二进制文件（本地构建）
make build-binary

# 运行
./dist/ack-mcp-server --help
```

### 🎯 本地开发运行


支持通过自然语言与 AI 助手交互，完成复杂的容器运维任务。

**Stdio 模式（适合本地开发）**
```bash
make run
# 或
python -m src.main_server
```

**SSE 模式（HTTP 服务）**
```bash
make run-sse
# 或
python -m src.main_server --transport sse --host 0.0.0.0 --port 8000
```

**常用参数**

| 参数 | 说明 | 默认值 |
|-----|-----|-------|
| `--region, -r` | 阿里云地域 | cn-hangzhou |
| `--access-key-id` | AccessKey ID | 环境变量 |
| `--access-key-secret` | AccessKey Secret | 环境变量 |
| `--default-cluster-id` | 默认集群 ID | 无 |
| `--allow-write` | 启用写入操作 | false |
| `--transport` | 传输模式 | stdio |
| `--host` | 绑定主机 | localhost |
| `--port` | 端口号 | 8000 |


**基于 MCP Inspector 的交互界面（适合本地调试）**
```bash
npx @modelcontextprotocol/inspector --config ./mcp.json
```

## 认证与凭证注入

- 默认走环境凭证（上文环境变量）。
- 对齐各子服务的 AK 传入逻辑：内部统一以凭证客户端+配置对象传入 `access_key_id/access_key_secret/region_id/endpoint`。
- 在 SSE（HTTP）模式下，可按需在上层网关增加请求级别的 AK 头部注入；如未注入，则回退环境凭证。具体头部键名可按网关---

## 🛠️ 如何参与开发

### 🏗️ 架构设计

系统采用微服务架构，主服务器通过 FastMCP 代理挂载机制集成多个子服务器：

- 主服务器: `src/main_server.py` - 统一入口、服务挂载
- ACK 管理: `src/ack_cluster_handler.py` - 集群管理、节点池操作
- Kubernetes: `src/kubectl_handler.py` - kubectl 命令执行
- 可观测性: `src/ack_prometheus_handler.py` 等

**技术栈**: Python 3.12+ + FastMCP 2.12.2+ + 阿里云SDK + Kubernetes Client

详细架构设计参见 [`DESIGN.md`](DESIGN.md)。

### 📋 开发环境搭建

```bash
# 克隆项目
git clone https://github.com/aliyun/alibabacloud-cs-mcp-server
cd alibabacloud-cs-mcp-server

# 安装依赖
uv sync

# 配置环境
cp .env.example .env
vim .env

# 运行开发服务
make install
make run
```

---

## 📊 效果 & Benchmark

### 🔍 测试场景

| 场景 | 描述 | 涉及模块 |
|------|------|----------|
| Pod OOM 修复 | 内存溢出问题诊断修复 | kubectl, 诊断 |
| 集群健康检查 | 全面的集群状态巡检 | 诊断, 巡检 |
| 资源异常诊断 | 异常资源根因分析 | kubectl, 诊断 |
| 历史资源分析 | 资源使用趋势分析 | prometheus, sls |

### 📊 性能数据

基于最新 Benchmark 结果：
- 成功率: 92%
- 平均处理时间: 4.2分钟
- 支持 AI 代理: qwen_code, kubectl-ai
- 支持 LLM: qwen3-coder-plus, qwen3-32b

```bash
# 运行 Benchmark
cd benchmarks
./run_benchmark.sh --openai-api-key your-key --agent qwen_code --model qwen3-coder-plus
```

---

## 🗺️ 演进计划 & Roadmap

### 🎯 近期计划
- 支持更多 AI 代理（Cursor, Claude）
- Web UI 界面开发
- 性能优化与缓存改进

### 🚀 中长期目标
- 多云支持（AWS, 腾讯云, 华为云）
- 企业级特性（RBAC, 安全扫描）
- AI 自动化运维能力

---

## 👥 项目维护机制与贡献者

### 🤝 如何贡献

1. **问题反馈**: 通过 [GitHub Issues](https://github.com/aliyun/alibabacloud-cs-mcp-server/issues)
2. **功能请求**: 通过 [Discussions](https://github.com/aliyun/alibabacloud-cs-mcp-server/discussions)
3. **代码贡献**: Fork → 功能分支 → Pull Request
4. **文档改进**: API 文档、教程编写

### 💬 社区交流
- GitHub Discussions: 技术讨论、问答
- 钉钉群: 日常交流、快速支持

---

## 认证与凭证注入

- 默认走环境凭证（ACCESS_KEY_ID/ACCESS_KEY_SECRET）
- 支持请求级 AK 注入（SSE 模式）
- 内部统一凭证管理机制

## 子服务一览

主服务挂载的子 MCP Server：
- `ack-cluster`: ACK 集群管理与诊断
- `kubernetes`: Kubernetes 客户端操作
- `observability-prometheus`: PromQL 指标查询
- `observability-sls`: SLS 日志查询与分析
- `audit-log`: Kubernetes 审计日志

## 测试

```bash
# 运行全部测试
make test
```

## 常见问题

- **未配置 AK**: 请检查 ACCESS_KEY_ID/ACCESS_KEY_SECRET 环境变量
- **ACK集群未开公网kubeconfig**: ack-mcp-server无法执行kubectl tool，需要ACK集群开启公网访问的kubeconfig 或者 ack-mcp-server本地网络可访问的kubeconfig配置（置于.kube/config中）
- **SSE 模式鉴权**: 在外层网关做统一鉴权

## 许可证

Apache-2.0。详见 [`LICENSE`](LICENSE)。
