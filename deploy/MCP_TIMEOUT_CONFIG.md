# MCP超时配置指南

## 问题描述

当遇到MCP错误`-32001: Request timed out`时，表示请求超时。这个超时可能发生在多个层面：

1. **诊断任务超时**：诊断任务执行时间过长
2. **kubectl命令超时**：kubectl命令执行时间过长
3. **API调用超时**：阿里云API调用超时
4. **MCP客户端超时**：客户端等待响应超时

## 解决方案

### 1. 环境变量配置

通过设置环境变量来调整各种超时参数：

```bash
# 诊断任务超时配置（秒）
export DIAGNOSE_TIMEOUT=600          # 诊断任务最大等待时间，默认10分钟
export DIAGNOSE_POLL_INTERVAL=15     # 诊断轮询间隔，默认15秒

# kubectl命令超时配置（秒）
export KUBECTL_TIMEOUT=30            # kubectl命令超时时间，默认30秒

# API调用超时配置（秒）
export API_TIMEOUT=60                # API调用超时时间，默认60秒

# 缓存配置
export CACHE_TTL=300                 # 缓存TTL，默认5分钟
export CACHE_MAX_SIZE=1000           # 缓存最大大小，默认1000

# 日志级别
export FASTMCP_LOG_LEVEL=INFO        # 日志级别：DEBUG, INFO, WARNING, ERROR
```

### 2. 启动服务器时设置环境变量

```bash
# 设置超时参数并启动服务器
DIAGNOSE_TIMEOUT=900 KUBECTL_TIMEOUT=60 python src/main_server.py --transport sse --port 3000
```

### 3. Docker环境配置

在Docker环境中，可以通过环境变量或docker-compose.yml配置：

```yaml
# docker-compose.yml
version: '3.8'
services:
  mcp-server:
    image: your-mcp-server:latest
    environment:
      - DIAGNOSE_TIMEOUT=900
      - KUBECTL_TIMEOUT=60
      - API_TIMEOUT=120
      - DIAGNOSE_POLL_INTERVAL=20
    ports:
      - "3000:3000"
```

### 4. Kubernetes环境配置

在Kubernetes中，可以通过ConfigMap或环境变量配置：

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-server-config
data:
  DIAGNOSE_TIMEOUT: "900"
  KUBECTL_TIMEOUT: "60"
  API_TIMEOUT: "120"
  DIAGNOSE_POLL_INTERVAL: "20"
```

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  template:
    spec:
      containers:
      - name: mcp-server
        image: your-mcp-server:latest
        envFrom:
        - configMapRef:
            name: mcp-server-config
```

## 超时参数说明

### 诊断任务超时 (DIAGNOSE_TIMEOUT)

- **默认值**: 600秒（10分钟）
- **用途**: 控制诊断任务的最大等待时间
- **建议值**: 
  - 简单诊断：300-600秒
  - 复杂诊断：900-1800秒
  - 网络诊断：1200-2400秒

### 诊断轮询间隔 (DIAGNOSE_POLL_INTERVAL)

- **默认值**: 15秒
- **用途**: 控制检查诊断状态的频率
- **建议值**:
  - 快速响应：10-15秒
  - 平衡性能：15-30秒
  - 减少API调用：30-60秒

### kubectl命令超时 (KUBECTL_TIMEOUT)

- **默认值**: 30秒
- **用途**: 控制kubectl命令的执行超时时间
- **建议值**:
  - 简单查询：15-30秒
  - 复杂操作：60-120秒
  - 大规模操作：180-300秒

### API调用超时 (API_TIMEOUT)

- **默认值**: 60秒
- **用途**: 控制阿里云API调用的超时时间
- **建议值**:
  - 快速API：30-60秒
  - 复杂API：120-300秒

## 故障排除

### 1. 诊断任务超时

如果诊断任务经常超时，可以：

```bash
# 增加诊断超时时间
export DIAGNOSE_TIMEOUT=1800  # 30分钟

# 增加轮询间隔以减少API调用
export DIAGNOSE_POLL_INTERVAL=30  # 30秒
```

### 2. kubectl命令超时

如果kubectl命令经常超时，可以：

```bash
# 增加kubectl超时时间
export KUBECTL_TIMEOUT=120  # 2分钟
```

### 3. 网络问题

如果网络不稳定，可以：

```bash
# 增加API超时时间
export API_TIMEOUT=180  # 3分钟

# 增加轮询间隔
export DIAGNOSE_POLL_INTERVAL=45  # 45秒
```

### 4. 调试模式

启用调试模式查看详细日志：

```bash
export FASTMCP_LOG_LEVEL=DEBUG
```

## 监控和日志

### 查看超时日志

```bash
# 查看诊断超时日志
grep "DIAGNOSE_TIMEOUT" logs/mcp-server.log

# 查看kubectl超时日志
grep "Command timed out" logs/mcp-server.log

# 查看API超时日志
grep "Request timeout" logs/mcp-server.log
```

### 性能监控

建议监控以下指标：

1. **诊断任务完成时间**
2. **kubectl命令执行时间**
3. **API调用响应时间**
4. **超时错误频率**

## 最佳实践

1. **渐进式调整**: 从默认值开始，根据实际使用情况逐步调整
2. **监控告警**: 设置超时错误告警，及时发现问题
3. **日志分析**: 定期分析日志，识别性能瓶颈
4. **环境隔离**: 不同环境使用不同的超时配置
5. **文档记录**: 记录超时配置的变更原因和效果

## 示例配置

### 开发环境
```bash
export DIAGNOSE_TIMEOUT=300
export KUBECTL_TIMEOUT=30
export API_TIMEOUT=60
export DIAGNOSE_POLL_INTERVAL=10
export FASTMCP_LOG_LEVEL=DEBUG
```

### 生产环境
```bash
export DIAGNOSE_TIMEOUT=900
export KUBECTL_TIMEOUT=60
export API_TIMEOUT=120
export DIAGNOSE_POLL_INTERVAL=20
export FASTMCP_LOG_LEVEL=INFO
```

### 高负载环境
```bash
export DIAGNOSE_TIMEOUT=1800
export KUBECTL_TIMEOUT=120
export API_TIMEOUT=180
export DIAGNOSE_POLL_INTERVAL=30
export FASTMCP_LOG_LEVEL=WARNING
```
