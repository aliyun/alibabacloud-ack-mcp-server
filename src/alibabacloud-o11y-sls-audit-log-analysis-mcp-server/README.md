# AlibabaCloud Cluster Audit Log MCP Server

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/alibabacloud-cluster-aduit-log-mcp-server.svg)](https://pypi.org/project/alibabacloud-cluster-aduit-log-mcp-server/)

一个基于MCP (Model Context Protocol) 的专业Kubernetes审计日志查询服务器，专门为阿里云SLS (Simple Log Service) 设计。采用标准Python包结构，支持现代包管理工具。

## 🚀 快速开始

### 使用 uvx (推荐)

```bash
# 直接运行，无需安装
uvx alibabacloud-cluster-aduit-log-mcp-server

# 使用自定义配置文件
uvx alibabacloud-cluster-aduit-log-mcp-server --config /path/to/config.yaml
```

### 使用 pip 安装

```bash
# 安装完整版本
pip install alibabacloud-cluster-aduit-log-mcp-server
```

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/alibabacloud/alibabacloud-cluster-aduit-log-mcp-server.git
cd alibabacloud-cluster-aduit-log-mcp-server

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装utils包（通用工具包）- 必须先安装
cd src/utils
pip install -e .

# 安装主包
cd ../alibabacloud_cluster_audit_log_mcp_server
pip install -e .
```

## ⚙️ 配置文件示例

### 1. 创建配置文件

创建 `config.yaml` 文件：

```yaml
default_cluster: "production"

clusters:
  - name: "production"
    description: "Production Kubernetes cluster"
    provider:
      name: "alibaba-sls"
      alibaba_sls:
        endpoint: "cn-hangzhou.log.aliyuncs.com"
        project: "k8s-audit-logs"
        logstore: "audit-log-store"
        region: "cn-hangzhou"
```

### 2. 配置认证

#### 阿里云SLS
- 通过环境变量：`ACCESS_KEY_ID` 和 `ACCESS_KEY_SECRET`


## 🎯 使用方法

### 命令行使用

```bash
# 使用默认配置启动（stdio transport）
alibabacloud-cluster-aduit-log-mcp-server

# 使用自定义配置文件
alibabacloud-cluster-aduit-log-mcp-server --config /path/to/config.yaml

# 使用 SSE transport（HTTP 服务器模式）
alibabacloud-cluster-aduit-log-mcp-server --transport sse --host 0.0.0.0 --port 8000

# 指定传输方式和端口
alibabacloud-cluster-aduit-log-mcp-server --transport stdio --config /path/to/config.yaml

# 查看版本信息
alibabacloud-cluster-aduit-log-mcp-server --version

# 查看帮助
alibabacloud-cluster-aduit-log-mcp-server --help
```

### 传输方式选择

#### 1. stdio Transport（默认）
- **用途**: 与 MCP 客户端通过标准输入输出通信
- **适用场景**: Claude Desktop、Cursor、Continue 等 MCP 客户端
- **特点**: 进程间通信，无需网络端口

```bash
# 使用 stdio transport
alibabacloud-cluster-aduit-log-mcp-server --transport stdio --config config.yaml
```

#### 2. SSE Transport（Server-Sent Events）
- **用途**: 通过 HTTP 服务器提供 MCP 服务
- **适用场景**: Web 应用、远程访问、调试
- **特点**: 网络访问，支持多客户端连接

```bash
# 使用 SSE transport
alibabacloud-cluster-aduit-log-mcp-server --transport sse --host 0.0.0.0 --port 8000 --config config.yaml
```

#### 3. 传输方式对比

| 特性 | stdio | SSE |
|------|-------|-----|
| 通信方式 | 标准输入输出 | HTTP/SSE |
| 网络端口 | 不需要 | 需要 |
| 多客户端 | 不支持 | 支持 |
| 调试难度 | 较难 | 容易 |
| 适用场景 | MCP 客户端 | Web 应用 |
| 性能 | 高 | 中等 |

### MCP Clients 添加方法

#### 1. 在 Claude Desktop 中添加

1. **打开 Claude Desktop 配置**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **添加 MCP 服务器配置**
   ```json
   {
     "mcpServers": {
       "alibabacloud-cluster-audit-log": {
         "command": "alibabacloud-cluster-aduit-log-mcp-server",
         "args": ["--config", "/path/to/your/config.yaml"],
         "env": {
        	"ACCESS_KEY_ID": "your-access-key-id",
           "ACCESS_KEY_SECRET": "your-access-key-secret"
      	  }
       }
     }
   }
   ```

3. **重启 Claude Desktop**

#### 2. 在 Cursor 中添加

1. **打开 Cursor 设置**
   - 按 `Cmd/Ctrl + ,` 打开设置
   - 搜索 "MCP" 或 "Model Context Protocol"

2. **添加 MCP 服务器**
   ```json
   {
     "mcpServers": {
       "alibabacloud-cluster-audit-log": {
         "command": "alibabacloud-cluster-aduit-log-mcp-server",
         "args": ["--config", "/path/to/your/config.yaml"],
         "env": {
           "ACCESS_KEY_ID": "your-access-key-id",
           "ACCESS_KEY_SECRET": "your-access-key-secret"
         }
       }
     }
   }
   ```

#### 3. 验证连接

添加配置后，您可以在 MCP 客户端中看到以下工具：

- `query_audit_log`: 查询 Kubernetes 审计日志
- `list_clusters`: 列出配置的集群

#### 4. 故障排查

如果连接失败，请检查：

1. **服务器是否可执行**
   ```bash
   which alibabacloud-cluster-aduit-log-mcp-server
   ```
   如果不可知性，请添加二进制文件到/usr/local/bin等可执行目录。

2. **配置文件是否存在且有效**
   ```bash
   alibabacloud-cluster-aduit-log-mcp-server --config /path/to/config.yaml --validate
   ```

3. **查看服务器日志**
   ```bash
   alibabacloud-cluster-aduit-log-mcp-server --config /path/to/config.yaml --verbose
   ```

4. **检查网络连接**
   - 确保可以访问云服务商的 API 端点
   - 检查防火墙和代理设置

## 🔍 查询参数

### query_audit_log 工具参数

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `namespace` | string | 否 | 命名空间过滤，支持通配符 |
| `verbs` | array | 否 | 操作动词过滤，支持多个值 |
| `resource_types` | array | 否 | 资源类型过滤，支持多个值 |
| `resource_name` | string | 否 | 资源名称过滤，支持通配符 |
| `user` | string | 否 | 用户过滤，支持通配符 |
| `start_time` | string | 否 | 开始时间，支持ISO 8601和相对时间格式 |
| `end_time` | string | 否 | 结束时间，支持ISO 8601和相对时间格式 |
| `limit` | integer | 否 | 结果数量限制，默认10，最大100 |
| `cluster_name` | string | 否 | 集群名称，默认使用default_cluster |

### 时间格式示例

- ISO 8601: `"2024-01-01T10:00:00Z"`
- 相对时间: `"24h"`, `"7d"`, `"30m"`

### 通配符示例

- 命名空间: `"kube*"` (匹配以kube开头的命名空间)
- 资源名称: `"nginx-*"` (匹配以nginx-开头的资源)
- 用户: `"system:*"` (匹配以system:开头的用户)


## 🧪 开发

### 开发环境初始化
```bash
# 安装开发依赖
pip install -e .
```

### 添加新的云提供商

1. 在 `toolkits/provider.py` 中创建新的Provider类
2. 实现 `query_audit_log` 方法
3. 在 `utils/context.py` 的 `SimpleLifespanManager._initialize_clients` 中添加初始化逻辑
4. 更新配置文件格式
5. 添加相应的测试用例

## 🤝 贡献

我们欢迎社区贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与。

### 开发流程

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 Apache License 2.0 许可证。详情请查看 [LICENSE](LICENSE) 文件。

## 🆘 支持

- 📖 [文档](https://github.com/alibabacloud/alibabacloud-ack-mcp-server#readme)
- 🐛 [问题报告](https://github.com/alibabacloud/alibabacloud-ack-mcp-server/issues)
- 💬 [讨论](https://github.com/alibabacloud/alibabacloud-ack-mcp-server/discussions)
- 📧 [邮件支持](mailto:support@alibabacloud.com)

## 🔗 相关链接

- [MCP (Model Context Protocol)](https://github.com/modelcontextprotocol)
- [阿里云SLS文档](https://help.aliyun.com/product/28958.html)

---

<div align="center">
  <p>由 <a href="https://www.alibabacloud.com">AlibabaCloud</a> 提供支持</p>
</div>