# 全局测试覆盖率验证

## 概述

本文档说明如何使用全局测试覆盖率验证工具来检查所有子MCP服务器的测试覆盖率。

## 文件结构

```
src/
├── verify_all_test_coverage.py          # 全局测试覆盖率验证脚本
├── ack-addon-management-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # 插件管理服务器测试覆盖率验证
├── ack-cluster-management-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # 集群管理服务器测试覆盖率验证
├── ack-diagnose-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # 诊断服务器测试覆盖率验证
├── ack-nodepool-management-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # 节点池管理服务器测试覆盖率验证
├── alibabacloud-ack-cloudresource-monitor-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # 云资源监控服务器测试覆盖率验证
├── alibabacloud-o11y-prometheus-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # Prometheus可观测性服务器测试覆盖率验证
├── alibabacloud-o11y-sls-apiserver-log-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # SLS API服务器日志测试覆盖率验证
├── alibabacloud-o11y-sls-audit-log-analysis-mcp-server/
│   └── tests/
│       └── verify_test_coverage.py      # SLS审计日志分析测试覆盖率验证
└── kubernetes-client-mcp-server/
    └── tests/
        └── verify_test_coverage.py      # Kubernetes客户端测试覆盖率验证
```

## 使用方法

### 1. 全局验证所有服务器

```bash
# 进入src目录
cd src

# 运行全局测试覆盖率验证
python verify_all_test_coverage.py
```

### 2. 验证单个服务器

```bash
# 进入特定服务器目录
cd src/ack-cluster-management-mcp-server

# 运行该服务器的测试覆盖率验证
python tests/verify_test_coverage.py
```

### 3. 通过测试脚本验证（推荐）

```bash
# 进入特定服务器目录
cd src/ack-cluster-management-mcp-server

# 使用测试脚本验证覆盖率
./run_tests.sh verify
```

## 验证脚本功能

每个 `verify_test_coverage.py` 脚本会：

1. **扫描tool方法**：从 `handler.py` 文件中自动发现所有 `@self.server.tool` 装饰的方法
2. **扫描测试文件**：从 `tests/` 目录中查找所有测试文件，检查是否有对应的测试用例
3. **计算覆盖率**：统计已测试方法数量与总方法数量的比例
4. **生成报告**：详细列出已测试和未测试的方法

## 输出示例

### 全局验证输出

```
🔍 全局MCP服务器测试覆盖率验证
================================================================================
📋 发现 9 个子MCP服务器:
  • ack-addon-management-mcp-server
  • ack-cluster-management-mcp-server
  • ...

================================================================================
📊 测试覆盖率总结
================================================================================
总计子MCP服务器: 9
测试覆盖率检查通过: 2
测试覆盖率检查失败: 7

📋 各服务器测试覆盖率:
  ❌ ack-addon-management-mcp-server               0.0%
  ✅ ack-cluster-management-mcp-server             100.0%
  ...
```

### 单个服务器验证输出

```
🔍 ACK集群管理MCP服务器测试覆盖率验证
==================================================
📋 扫描handler.py中的tool方法...
✓ 发现tool方法: describe_clusters
✓ 发现tool方法: describe_cluster_detail
...

📊 测试覆盖率分析
==================================================
总tool方法数: 10
已测试方法数: 10
测试覆盖率: 100.0%

✅ 已测试的方法:
  • create_cluster
  • delete_cluster
  ...

🎉 所有tool方法都已有测试覆盖！
```

## 当前状态

根据最新验证结果：

| 服务器 | 测试覆盖率 | 状态 |
|--------|------------|------|
| ack-cluster-management-mcp-server | 100.0% | ✅ 完成 |
| alibabacloud-o11y-sls-audit-log-analysis-mcp-server | 100.0% | ✅ 完成 |
| ack-addon-management-mcp-server | 0.0% | ❌ 待完善 |
| ack-diagnose-mcp-server | 0.0% | ❌ 待完善 |
| ack-nodepool-management-mcp-server | 0.0% | ❌ 待完善 |
| alibabacloud-ack-cloudresource-monitor-mcp-server | 0.0% | ❌ 待完善 |
| alibabacloud-o11y-prometheus-mcp-server | 0.0% | ❌ 待完善 |
| alibabacloud-o11y-sls-apiserver-log-mcp-server | 0.0% | ❌ 待完善 |
| kubernetes-client-mcp-server | 0.0% | ❌ 待完善 |

## 下一步工作

1. **为待完善的服务器创建单元测试**：参考 `ack-cluster-management-mcp-server` 的测试实现
2. **环境变量配置**：确保所有测试都支持通过 `.env` 文件进行阿里云认证配置
3. **测试脚本集成**：为每个服务器的 `run_tests.sh` 添加 `verify` 选项

## 开发规范

根据项目memory规范：

- ✅ 所有测试文件都放在对应的 `tests` 目录下
- ✅ 每个handler的tool方法都有独立的单元测试
- ✅ 测试覆盖率需达到100%
- ✅ 测试通过 `.env` 文件进行环境变量初始化
- ✅ 使用 `pytest-asyncio` 支持异步测试
- ✅ 包含正常调用、参数验证、错误处理等测试场景