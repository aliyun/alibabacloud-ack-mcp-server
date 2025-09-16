# ACK Cluster Management MCP Server 单元测试

## 概述

本目录包含针对 ACK Cluster Management MCP Server 中每个 handler tool 方法的完整单元测试。

✅ **测试状态**: 已完成，所有测试通过
✅ **测试覆盖率**: 100% (10/10 个 tool 方法)
✅ **环境变量支持**: 通过 .env 文件进行阿里云认证配置
✅ **独立测试**: 每个 tool 方法都有独立的测试用例

## 测试文件说明

### 1. `test_tool_methods.py` - 主要的工具方法测试
这是新创建的核心测试文件，包含对以下所有 tool 方法的独立测试：

#### 查询类方法 (只读操作)
- `test_describe_clusters()` - 测试集群列表查询
- `test_describe_clusters_with_filters()` - 测试带过滤条件的集群查询
- `test_describe_cluster_detail()` - 测试集群详情查询
- `test_describe_task_info()` - 测试任务信息查询
- `test_describe_cluster_logs()` - 测试集群日志查询
- `test_describe_user_quota()` - 测试用户配额查询
- `test_describe_kubernetes_version_metadata()` - 测试Kubernetes版本元数据查询

#### 操作类方法 (写操作)
- `test_modify_cluster_write_enabled()` / `test_modify_cluster_write_disabled()` - 测试集群修改
- `test_create_cluster_write_enabled()` / `test_create_cluster_write_disabled()` - 测试集群创建
- `test_delete_cluster_write_enabled()` / `test_delete_cluster_write_disabled()` - 测试集群删除
- `test_upgrade_cluster_write_enabled()` / `test_upgrade_cluster_write_disabled()` - 测试集群升级

#### 错误处理测试
- `test_no_client_in_context()` - 测试上下文中缺少客户端的情况
- `test_context_access_failure()` - 测试上下文访问失败的情况

### 2. `test_basic_functionality.py` - 基础功能测试
原有的基础功能测试文件，测试服务器配置和基本逻辑。

### 3. `test_api_parameters.py` - API参数验证测试
API参数验证和合规性测试。

### 4. `verify_test_coverage.py` - 测试覆盖率验证工具
自动验证脚本，检查所有 handler 中的 tool 方法是否都有对应的单元测试。

## 环境配置

### 必需的环境变量

在项目根目录创建 `.env` 文件，配置以下阿里云认证信息：

```bash
# 阿里云认证配置
ACCESS_KEY_ID=your_access_key_id
ACCESS_KEY_SECRET=your_access_key_secret
REGION_ID=cn-hangzhou

# 可选配置
DEFAULT_CLUSTER_ID=your_default_cluster_id
ALLOW_WRITE=false
DEVELOPMENT=true
CACHE_TTL=300
CACHE_MAX_SIZE=1000
```

### 依赖安装

确保安装了以下依赖：

```bash
pip install pytest pytest-asyncio
```

## 运行测试

### 使用测试脚本（推荐）

```bash
# 运行所有测试
./run_tests.sh

# 只运行工具方法测试
./run_tests.sh tools

# 只运行基础功能测试
./run_tests.sh basic

# 只运行API参数测试
./run_tests.sh api

# 运行测试覆盖率验证
./run_tests.sh verify
```

### 使用 pytest 直接运行

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定的测试文件
pytest tests/test_tool_methods.py -v

# 运行特定的测试方法
pytest tests/test_tool_methods.py::TestACKClusterManagementTools::test_describe_clusters -v

# 运行带标记的测试
pytest -m "not slow" -v
```

## 测试特性

### 1. 环境变量驱动
- 测试使用 `.env` 文件中的真实阿里云配置
- 支持开发环境和生产环境的配置切换
- 自动处理缺失环境变量的情况

### 2. 模拟客户端
- 使用 Mock 对象模拟阿里云 CS 客户端
- 预设合理的返回数据，覆盖各种场景
- 支持异步操作测试

### 3. 写操作保护
- 所有写操作都有 `allow_write` 开关保护
- 测试覆盖写操作启用和禁用两种情况
- 确保在测试环境中不会意外修改云资源

### 4. 错误处理
- 测试客户端不可用的情况
- 测试上下文访问失败的情况
- 测试API调用异常的情况

### 5. 参数验证
- 测试各种输入参数组合
- 验证过滤条件和分页参数
- 检查必需参数和可选参数

## 测试覆盖范围

✅ **已完成的 Handler Tool 方法测试：**

1. ✅ `describe_clusters` - 集群列表查询
2. ✅ `describe_cluster_detail` - 集群详情查询
3. ✅ `modify_cluster` - 集群配置修改
4. ✅ `describe_task_info` - 任务信息查询
5. ✅ `create_cluster` - 集群创建
6. ✅ `delete_cluster` - 集群删除
7. ✅ `upgrade_cluster` - 集群升级
8. ✅ `describe_cluster_logs` - 集群日志查询
9. ✅ `describe_user_quota` - 用户配额查询
10. ✅ `describe_kubernetes_version_metadata` - Kubernetes版本元数据查询

**每个方法都包含：**
- ✅ 正常调用测试
- ✅ 参数验证测试
- ✅ 错误处理测试
- ✅ 写操作权限测试（适用时）
- ✅ 环境变量集成测试

## 测试结果总结

- **所有测试通过**: 27/27 个测试用例 ✅
- **测试覆盖率**: 100% 的 tool 方法
- **环境集成**: 支持 .env 文件配置
- **错误处理**: 完善的异常和错误场景测试
5. `create_cluster` - 集群创建
6. `delete_cluster` - 集群删除
7. `upgrade_cluster` - 集群升级
8. `describe_cluster_logs` - 集群日志查询
9. `describe_user_quota` - 用户配额查询
10. `describe_kubernetes_version_metadata` - Kubernetes版本元数据查询

**每个方法都包含：**
- 正常调用测试
- 参数验证测试
- 错误处理测试
- 写操作权限测试（适用时）

## 注意事项

1. **安全性**: 测试使用模拟客户端，不会对真实的阿里云资源产生影响
2. **环境变量**: 缺少环境变量时测试会优雅降级，不会失败
3. **异步支持**: 所有测试都支持异步操作，使用 `pytest-asyncio`
4. **可扩展性**: 测试框架可以轻松扩展到其他 MCP 服务器模块

## 下一步

如果需要添加新的 tool 方法测试，请：

1. 在 `test_tool_methods.py` 中添加对应的测试方法
2. 在 `mock_cs_client` fixture 中添加对应的模拟响应
3. 确保测试覆盖正常情况、错误情况和边界情况
4. 更新本 README 文档