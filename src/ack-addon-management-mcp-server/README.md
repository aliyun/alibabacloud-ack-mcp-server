# ACK Addon Management MCP Server

ACK插件管理MCP服务器，提供对阿里云ACK集群插件的统一管理接口。

## 功能特性

- **插件查询**: 列出可用的插件和已安装的插件实例
- **插件安装**: 安装插件到ACK集群
- **插件卸载**: 从ACK集群卸载插件
- **插件详情**: 获取插件详细信息
- **插件修改**: 修改已安装插件的配置
- **插件升级**: 升级插件到新版本

## 工具方法

### list_addons
列出可用的插件。

**参数:**
- `cluster_type` (str, 可选): 集群类型过滤
- `region` (str, 可选): 地域过滤
- `cluster_spec` (str, 可选): 集群规格过滤
- `cluster_version` (str, 可选): 集群版本过滤
- `profile` (str, 可选): 集群子类型过滤
- `cluster_id` (str, 可选): 特定集群ID

### list_cluster_addon_instances
列出集群已安装的插件实例。

**参数:**
- `cluster_id` (str, 必需): 集群ID

### get_cluster_addon_instance
获取特定插件实例的详细信息。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addon_name` (str, 必需): 插件名称

### describe_addon
描述插件信息。

**参数:**
- `addon_name` (str, 必需): 插件名称
- `cluster_spec` (str, 可选): 集群规格过滤
- `cluster_type` (str, 可选): 集群类型过滤
- `cluster_version` (str, 可选): 集群版本过滤
- `region` (str, 可选): 地域过滤

### install_cluster_addons
安装插件到集群。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要安装的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称
  - `version` (str, 可选): 插件版本
  - `config` (str, 可选): 插件配置
  - `disabled` (bool, 可选): 是否禁用插件

### uninstall_cluster_addons
从集群卸载插件。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要卸载的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称
  - `cleanup_cloud_resources` (bool, 可选): 是否清理云资源

### modify_cluster_addon
修改集群插件配置。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addon_name` (str, 必需): 插件名称
- `config` (str, 可选): 插件配置（JSON字符串格式）

### upgrade_cluster_addons
升级集群插件。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要升级的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称
  - `version` (str, 必需): 目标版本
  - `config` (str, 可选): 插件配置

## 测试

运行测试:

```bash
# 运行所有测试
./run_tests.sh

# 运行特定测试
./run_tests.sh tools    # 运行插件管理工具测试
./run_tests.sh api      # 运行API参数测试
./run_tests.sh verify   # 运行测试覆盖率验证
```

## API参考

参考阿里云ACK插件管理API文档:
https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/developer-reference/api-cs-2015-12-15-dir-add-ons/?spm=a2c4g.11186623.0.i1