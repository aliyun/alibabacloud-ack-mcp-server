# AlibabaCloud ACK MCP Server

AlibabaCloud ACK (Alibaba Container Service for Kubernetes) MCP (Model Context Protocol) Server for Kubernetes audit log querying.

## 安装

### 基本安装
```bash
pip install alibabacloud-cluster-audit-log-mcp-server.zip
```

### 包含 Alibaba SLS 支持的安装
```bash
pip install alibabacloud-cluster-audit-log-mcp-server.zip[aliyun]
```

## 使用方法

### 作为 MCP 服务器运行
```bash
alibabacloud-cluster-audit-log-mcp-server
```

### 作为 Python 库导入
```python
from alibabacloud_cluster_audit_log_mcp_server import KubeAuditTool, create_server

# 创建服务器
config = {
    'clusters': [
        {
            'name': 'my-cluster',
            'description': 'My Kubernetes cluster',
            'provider': {
                'name': 'alibaba-sls',
                'alibaba_sls': {
                    'endpoint': 'cn-hangzhou.log.aliyuncs.com',
                    'project': 'my-project',
                    'logstore': 'my-logstore',
                    'region': 'cn-hangzhou'
                }
            }
        }
    ]
}

server = create_server(config_dict=config)
tool = KubeAuditTool(server)
```

## 功能特性

- **Kubernetes 审计日志查询**: 支持查询 Kubernetes 集群的审计日志
- **多集群支持**: 可以配置和管理多个 Kubernetes 集群
- **Alibaba SLS 集成**: 支持使用 Alibaba Cloud Log Service (SLS) 作为日志存储后端
- **资源类型映射**: 支持 20+ 种 Kubernetes 资源类型的查询
- **灵活的时间范围**: 支持相对时间（如 "24h"）和绝对时间格式
- **可选的 Alibaba SDK**: aliyun-log-python-sdk 作为可选依赖，避免包冲突

## 配置

### 集群配置
```yaml
clusters:
  - name: "my-cluster"
    description: "My Kubernetes cluster"
    provider:
      name: "alibaba-sls"
      alibaba_sls:
        endpoint: "cn-hangzhou.log.aliyuncs.com"
        project: "my-project"
        logstore: "my-logstore"
        region: "cn-hangzhou"
        # 可选：自定义 aliyun.log 模块路径，解决导入冲突
        aliyun_log_module_path: "custom.aliyun.log"
```

## 解决导入冲突

如果您的项目中存在 `aliyun.log` 路径冲突，可以通过配置 `aliyun_log_module_path` 来指定自定义的模块路径：

```python
config = {
    'clusters': [
        {
            'name': 'my-cluster',
            'provider': {
                'name': 'alibaba-sls',
                'alibaba_sls': {
                    'endpoint': 'cn-hangzhou.log.aliyuncs.com',
                    'project': 'my-project',
                    'logstore': 'my-logstore',
                    'region': 'cn-hangzhou',
                    'aliyun_log_module_path': 'custom.aliyun.log'  # 自定义路径
                }
            }
        }
    ]
}
```

## 依赖项

### 必需依赖
- `mcp>=1.0.0` - Model Context Protocol 支持
- `pydantic>=2.0.0` - 数据验证
- `pyyaml>=6.0` - YAML 配置文件支持

### 可选依赖
- `aliyun-log-python-sdk>=0.8.0` - Alibaba Cloud Log Service SDK（通过 `[aliyun]` 安装）

## 许可证

MIT License
