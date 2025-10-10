# 阿里云容器服务 MCP Server (ack-mcp-server)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.12.2+-green.svg)](https://github.com/jlowin/fastmcp)

阿里云容器服务MCP Server工具集 ack-mcp-server。   
将 ACK 集群/资源管理、Kubernetes 原生操作与容器场景的可观测性能力、安全审计、诊断巡检等运维能力统一为AI原生的标准化工具集。   
本工具集的能力被[阿里云容器服务智能助手功能](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-container-ai-assistant-for-troubleshooting-and-intelligent-q-a)集成。也可支持三方AI Agent ([kubectl-ai](https://github.com/GoogleCloudPlatform/kubectl-ai/blob/main/pkg/mcp/README.md#local-stdio-based-server-configuration)、[QWen Code](https://qwenlm.github.io/qwen-code-docs/zh/tools/mcp-server/#%E4%BD%BF%E7%94%A8-qwen-mcp-%E7%AE%A1%E7%90%86-mcp-%E6%9C%8D%E5%8A%A1%E5%99%A8)、[Claude Code](https://docs.claude.com/zh-CN/docs/claude-code/mcp)、[Cursor](https://cursor.com/cn/docs/context/mcp/directory)、[Gemini CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md#configure-the-mcp-server-in-settingsjson)、[VS Code](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server)等)或自动化系统调用集成，基于 [MCP（Model Context Protocol）](https://modelcontextprotocol.io/docs/getting-started/intro)协议。  
实现支持通过自然语言与 AI 助手交互，完成复杂的容器运维任务。帮助构建用户自己的容器场景AIOps运维体系。

* [1. 概述 & 功能简介](#-1-概述--功能简介)
* [2. 如何使用 & 部署](#-2-如何使用--部署)
* [3. 如何本地开发运行](#-3-如何本地开发运行)
* [4. 如何参与社区贡献](#-4-如何参与社区贡献)
* [5. 效果-benchmark](#-5-效果--benchmark-持续构建中)
* [6. 演进计划-roadmap](#-6-演进计划--roadmap)
* [7. 常见问题](#7-常见问题)

## 🌟 1. 概述 & 功能简介

### 🎬 1.1 演示效果

// TODO 插入B站视频

### 🎯 1.2 核心功能

**阿里云 ACK 全生命周期的资源管理**
- 集群查询 (`list_clusters`)
- 节点资源管理、节点池扩缩容 (Later)
- 组件Addon管理 (Later)
- 集群创建、删除 (Later)
- 集群升级 (Later)
- 集群资源运维任务查询 (Later)

**Kubernetes 原生操作** (`ack_kubectl`)
- 执行 `kubectl` 类操作（读写权限可控）
- 获取日志、事件，资源的增删改查
- 支持所有标准 Kubernetes API

**AI原生的容器场景可观测性**
- **Prometheus**: 支持ACK集群对应的阿里云Prometheus、自建Prometheus的指标查询、自然语言转 PromQL (`query_prometheus` / `query_prometheus_metric_guidance`)
- **集群控制面日志查询**: 支持ACK集群的控制面SLS 日志的查询，包括SLS SQL 查询、自然语言转 SLS-SQL (`query_controlplane_logs`)
- **审计日志**: Kubernetes 操作审计追踪 (`query_audit_log`)
- …… (更多[容器可观测能力](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices) ing)

**阿里云 ACK 诊断、巡检功能**
- 集群资源诊断 (`diagnose_resource`)
- 集群健康巡检 (`query_inspect_report`)

**企业级工程能力**
- 🏗️ 分层架构：工具层、服务层、认证层完全解耦
- 🔐 动态凭证注入：支持请求级 AK 注入或环境凭证
- 📊 健壮错误处理：结构化错误输出与类型化响应
- 📦 模块化设计：各子服务可独立运行


### 🏆 1.3 核心优势

- **🤖 AI 原生**: 专为 AI 代理设计的标准化接口
- **🔧 统一工具集**: 一站式容器运维能力整合
- **⚡ 知识沉淀**: 内置ACK、K8s、容器可观测体系的最佳实践经验沉淀
- **🛡️ 企业级**: 完善的认证、授权、日志机制
- **📈 可扩展**: 插件化架构，轻松扩展新功能

### 📈 1.4 Benchmark 效果验证 (持续更新中)

基于实际场景的 AI 能力测评，支持多种 AI 代理和大模型的效果对比：

| 任务场景 | AI Agent   | 大模型 | 成功率 | 平均处理时间 |
|------|------------|------|-------|--------|
| Pod OOM 修复 | qwen_code  | qwen3-coder-plus | ✅ 100% | 2.3min |
| 集群健康检查 | qwen_code  | qwen3-coder-plus | ✅ 95% | 6.4min |
| 资源异常诊断 | kubectl-ai | qwen3-32b | ✅ 90% | 4.1min |
| 历史资源分析 | qwen_code  | qwen3-coder-plus | ✅ 85% | 3.8min |

最新 Benchmark 报告参见 [`benchmarks/results/`](benchmarks/results/) 目录。

---

## 🚀 2. 如何使用 & 部署

### 💻 2.1 阿里云认证、权限准备

建议为ack-mcp-server配置的阿里云账号认证为一个主账号的子账号，并遵循最小权限原则，为此子账号赋予如下权限策略集。

**所需RAM权限策略集**
  
如何为阿里云账号的RAM账号添加所需权限，参考文档：[RAM 权限策略](https://help.aliyun.com/zh/ram/user-guide/policy-overview)  
当前ack-mcp-server所需只读权限集为：
- 容器服务cs 所有只读权限
- 日志服务log 所有只读权限
- 阿里云prometheus(arms) 实例只读权限
- ……后续追加资源变更权限以支持资源全生命周期管理

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cs:Check*",
        "cs:Describe*",
        "cs:Get*",
        "cs:List*",
        "cs:Query*",
        "cs:RunClusterCheck",
        "cs:RunClusterInspect"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "arms:GetPrometheusInstance",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "log:Describe*",
        "log:Get*",
        "log:List*"
      ],
      "Resource": "*"
    }
  ]
}
```

### 💻 2.2 （可选）创建ACK集群

- 阿里云账号中已创建的 ACK 集群
- ACK集群开启公网访问的kubeconfig or ack-mcp-server本地网络可访问的kubeconfig配置（置于.kube/config中）

### 📍 2.3 部署运行ack-mcp-server

#### 2.3.1 部署方式1 - 使用 Helm 部署在k8s集群内

在 Kubernetes 集群中部署：

```bash
# 克隆代码仓库
git clone https://github.com/aliyun/alibabacloud-cs-mcp-server
cd alibabacloud-cs-mcp-server

# 使用 Helm 部署
helm install \
--set accessKeyId=<your-access-key-id> \
--set accessKeySecret=<your-access-key-secret> \
--set transport=sse \
ack-mcp-server \
./deploy/helm \
-n kube-system 
```
部署后通过为ack-mcp-server service配置负载均衡等方式透出外网访问服务，以对接AI Agent。

**参数说明**
- `accessKeyId`: 阿里云账号的 AccessKeyId
- `accessKeySecret`: 阿里云账号的 AccessKeySecret

#### 2.3.2 部署方式2 - 📦 使用 Docker 镜像部署ack-mcp-server

```bash
# 拉取镜像
docker pull registry-cn-beijing.ack.aliyuncs.com/acs/ack-mcp-server:latest

# 运行容器
docker run \ 
  -d \
  --name ack-mcp-server \
  -e ACCESS_KEY_ID="your-access-key-id" \
  -e ACCESS_KEY_SECRET="your-access-key-secret" \
  -p 8000:8000 \
  registry-cn-beijing.ack.aliyuncs.com/acs/ack-mcp-server:latest \
  python -m main_server --transport sse --host 0.0.0.0 --port 8000 --allow-write
```

#### 2.3.3 部署方式3 - 💻 使用 Binary 方式启动部署

下载预编译的二进制文件 或 本地构建二进制文件后运行：

```bash
# 构建二进制文件（本地构建）
make build-binary

# 运行
./dist/ack-mcp-server --help
```

## 🎯 3 如何本地开发运行

### 💻 3.1 环境准备

**构建环境要求**
- Python 3.12+
- 阿里云账号及 AccessKey、AccessSecretKey，所需权限集
- 阿里云账号中已创建的 ACK 集群
- ACK集群开启公网访问的kubeconfig or ack-mcp-server本地网络可访问的kubeconfig配置（置于.kube/config中）


### 📋 3.2 开发环境搭建

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

**安装依赖**

使用 `uv`（推荐）：
```bash
uv sync
```

或使用 `pip`：
```bash
pip install -r requirements.txt
```

### ⚙️ 3.3 配置设置

创建 `.env` 文件（可参考 `.env.example`）：

```env
# 阿里云凭证与地域
ACCESS_KEY_ID=your-access-key-id
ACCESS_KEY_SECRET=your-access-key-secret
REGION_ID=cn-hangzhou

# 缓存配置
CACHE_TTL=300
CACHE_MAX_SIZE=1000

# 日志配置
FASTMCP_LOG_LEVEL=INFO
DEVELOPMENT=false
```

> ⚠️ **注意**: 未设置 ACCESS_KEY_ID/ACCESS_KEY_SECRET 时，部分依赖云 API 的功能不可用。

### 3.4.1 运行模式1. 基于 [MCP Inspector](https://github.com/modelcontextprotocol/inspector) 的交互界面（适合本地效果调试）
```bash
npx @modelcontextprotocol/inspector --config ./mcp.json
```

#### 3.4.2 本地python命令运行ack-mcp-server

**本地运行ack-mcp-server Stdio 模式（适合本地开发）**
```bash
make run
# 或
python -m src.main_server
```

**本地运行ack-mcp-server Streaming HTTP 模式（推荐线上系统集成使用）**
```bash
make run-http
# 或
python -m src.main_server --transport http --host 0.0.0.0 --port 8000
```

**本地运行ack-mcp-server SSE 模式**
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


### 3.5. 功能测试UT

```bash
# 运行全部测试UT
make test
```

## 🛠️ 4. 如何参与社区贡献

### 🏗️ 4.1 工程架构设计

**技术栈**: Python 3.12+ + FastMCP 2.12.2+ + 阿里云SDK + Kubernetes Client

详细架构设计参见 [`DESIGN.md`](DESIGN.md)。

### 👥 4.2 项目维护机制

#### 🤝 如何贡献

1. **问题反馈**: 通过 [GitHub Issues](https://github.com/aliyun/alibabacloud-cs-mcp-server/issues)
2. **功能请求**: 通过 [Discussions](https://github.com/aliyun/alibabacloud-cs-mcp-server/discussions)
3. **代码贡献**: Fork → 功能分支 → Pull Request
4. **文档改进**: API 文档、教程编写

### 💬 社区交流
- GitHub Discussions: 技术讨论、问答
- 钉钉群: 日常交流、快速支持。 搜索钉钉群号： 70080006301

---

## 📊 5. 效果 & Benchmark （持续构建中）

### 🔍 测试场景

| 场景 | 描述 | 涉及模块 |
|------|------|----------|
| Pod OOM 修复 | 内存溢出问题诊断修复 | kubectl, 诊断 |
| 集群健康检查 | 全面的集群状态巡检 | 诊断, 巡检 |
| 资源异常诊断 | 异常资源根因分析 | kubectl, 诊断 |
| 历史资源分析 | 资源使用趋势分析 | prometheus, sls |

### 📊 效果数据

基于最新 Benchmark 结果：
- 成功率: 92%
- 平均处理时间: 4.2分钟
- 支持 AI 代理: qwen_code, kubectl-ai
- 支持 LLM: qwen3-coder-plus, qwen3-32b

### 如何运行benchmark

详细参见 [`Benchmark README.md`](./benchmarks/README.md)。

```bash
# 运行 Benchmark
cd benchmarks
./run_benchmark.sh --openai-api-key your-key --agent qwen_code --model qwen3-coder-plus
```

---

## 🗺️ 6. 演进计划 & Roadmap

### 🎯 近期计划
- 支持ACK 集群、节点、功能承载组件(addon)的全生命周期资源运维
- 以benchmark效果作为基线目标，持续优化核心场景在通用三方Agent、LLM model中的效果，提升核心运维场景的效果成功率
- 持续补充benchmark的核心运维场景case，覆盖ACK大部分运维场景，如有需求，欢迎提issue
- 性能优化与缓存改进

### 🚀 中长期目标
- 覆盖容器场景的[卓越架构的五大支柱](https://help.aliyun.com/product/2362200.html)：安全、稳定、成本、效率、性能(高可靠性等)的能力，对多步骤的复杂容器运维场景，提供更优秀的AIOps体验。
- - 集群成本的洞察与治理
- - 集群弹性伸缩的最佳实践
- - 集群的安全漏洞发现与治理
- - ……
- 企业级特性（RBAC, 安全扫描）
- AI 自动化运维能力

## 7. 常见问题

- **未配置 AK**: 请检查 ACCESS_KEY_ID/ACCESS_KEY_SECRET 环境变量
- **ACK集群未开公网kubeconfig**: ack-mcp-server无法执行kubectl tool，需要ACK集群开启公网访问的kubeconfig 或者 ack-mcp-server本地网络可访问的kubeconfig配置（置于.kube/config中）

## 许可证

Apache-2.0。详见 [`LICENSE`](LICENSE)。
