# ACK Diagnose MCP Server - 使用示例

本文档提供阿里云容器服务(ACK)集群诊断和巡检MCP服务器的使用示例。

## 功能概述

该服务器提供以下主要功能：

### 集群诊断功能
- **create_cluster_diagnosis**: 创建集群诊断任务
- **get_cluster_diagnosis_result**: 获取诊断结果
- **get_cluster_diagnosis_check_items**: 获取诊断检查项

### 集群巡检功能
- **list_cluster_inspect_reports**: 列出巡检报告
- **get_cluster_inspect_report_detail**: 获取巡检报告详情
- **run_cluster_inspect**: 运行集群巡检

### 巡检配置管理
- **create_cluster_inspect_config**: 创建巡检配置
- **update_cluster_inspect_config**: 更新巡检配置
- **get_cluster_inspect_config**: 获取巡检配置

## 配置要求

### 环境变量
```bash
export ACCESS_KEY_ID=\"your-access-key-id\"
export ACCESS_KEY_SECRET=\"your-access-key-secret\"
export REGION_ID=\"cn-hangzhou\"
export DEFAULT_CLUSTER_ID=\"your-cluster-id\"
```

### 启动服务器
```bash
# 启动stdio模式（用于MCP客户端连接）
python -m ack-diagnose-mcp-server --allow-write --region cn-hangzhou

# 启动SSE模式（用于HTTP API）
python -m ack-diagnose-mcp-server --transport sse --port 8003 --allow-write
```

## 使用示例

### 1. 创建集群诊断任务

```python
# 通过MCP工具调用
result = await create_cluster_diagnosis(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    diagnosis_type=\"all\",  # 可选: all, node, pod, network
    target={}  # 可选的目标配置
)

print(f\"诊断任务ID: {result['diagnosis_id']}\")
print(f\"状态: {result['status']}\")
```

### 2. 获取诊断结果

```python
result = await get_cluster_diagnosis_result(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    diagnosis_id=\"diag-xxxxxxxxxxxxx\"
)

print(f\"诊断状态: {result['status']}\")
print(f\"诊断结果: {result['result']}\")
print(f\"进度: {result['progress']}\")
```

### 3. 运行集群巡检

```python
result = await run_cluster_inspect(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    inspect_type=\"all\"  # 可选: all, security, performance
)

print(f\"巡检任务ID: {result['inspect_id']}\")
print(f\"状态: {result['status']}\")
```

### 4. 列出巡检报告

```python
result = await list_cluster_inspect_reports(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    page_num=1,
    page_size=10
)

print(f\"总报告数: {result['total_count']}\")
for report in result['reports']:
    print(f\"报告ID: {report['report_id']}, 状态: {report['status']}\")
```

### 5. 获取巡检报告详情

```python
result = await get_cluster_inspect_report_detail(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    report_id=\"report-xxxxxxxxxxxxx\"
)

print(f\"报告状态: {result['status']}\")
print(f\"创建时间: {result['created_time']}\")
print(f\"完成时间: {result['finished_time']}\")
print(f\"报告详情: {result['report_detail']}\")
```

### 6. 创建巡检配置

```python
inspect_config = {
    \"inspection_type\": \"all\",
    \"schedule\": \"0 2 * * *\",  # 每天凌晨2点
    \"enabled\": True,
    \"notification\": {
        \"webhook\": \"https://your-webhook-url\",
        \"email\": \"admin@example.com\"
    }
}

result = await create_cluster_inspect_config(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    inspect_config=inspect_config
)

print(f\"配置ID: {result['config_id']}\")
print(f\"状态: {result['status']}\")
```

### 7. 获取诊断检查项

```python
result = await get_cluster_diagnosis_check_items(
    cluster_id=\"c-xxxxxxxxxxxxx\",
    diagnosis_type=\"all\",
    lang=\"zh\"  # 中文描述
)

print(\"可用的检查项:\")
for item in result['check_items']:
    print(f\"- {item['name']}: {item['description']}\")
```

## 错误处理

所有API调用都包含错误处理，返回结果中包含错误信息：

```python
result = await create_cluster_diagnosis(
    cluster_id=\"invalid-cluster\",
    diagnosis_type=\"all\"
)

if \"error\" in result:
    print(f\"操作失败: {result['error']}\")
    print(f\"状态: {result['status']}\")
else:
    print(f\"操作成功: {result['diagnosis_id']}\")
```

## 权限控制

需要写权限的操作包括：
- create_cluster_diagnosis
- run_cluster_inspect  
- create_cluster_inspect_config
- update_cluster_inspect_config

如果服务器以只读模式启动（不使用 --allow-write），这些操作将返回错误：

```json
{
    \"error\": \"Write operations are disabled\"
}
```

## 注意事项

1. **认证**: 确保配置正确的阿里云访问凭证
2. **权限**: 使用的AccessKey需要具有容器服务的诊断和巡检权限
3. **地域**: 确保指定正确的地域ID
4. **集群ID**: 使用有效的ACK集群ID
5. **配额限制**: 遵守阿里云API的调用频率限制

## 支持的地域

- cn-hangzhou (杭州)
- cn-shanghai (上海) 
- cn-beijing (北京)
- cn-shenzhen (深圳)
- 其他阿里云支持的地域

更多详细信息请参考[阿里云容器服务API文档](https://help.aliyun.com/document_detail/26043.html)。