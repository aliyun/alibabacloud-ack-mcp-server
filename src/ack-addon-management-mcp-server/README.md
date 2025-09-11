# ACK Addon Management MCP Server

ACK插件管理MCP服务器，提供对阿里云ACK集群插件的统一管理接口。

## 功能特性

- **插件查询**: 列出和查询集群可用的插件
- **插件安装**: 安装插件到ACK集群
- **插件卸载**: 从ACK集群卸载插件
- **插件详情**: 获取插件详细信息
- **插件修改**: 修改已安装插件的配置

## 工具方法

### describe_cluster_addons
描述集群可用的插件列表。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addon_name` (str, 可选): 插件名称过滤
- `component_name` (str, 可选): 组件名称过滤

### install_cluster_addons
安装插件到集群。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要安装的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称
  - `version` (str, 可选): 插件版本
  - `config` (Dict, 可选): 插件配置
  - `properties` (Dict, 可选): 插件属性

### uninstall_cluster_addons
从集群卸载插件。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要卸载的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称

### describe_cluster_addon_info
获取插件详细信息。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addon_name` (str, 必需): 插件名称

### modify_cluster_addons
修改集群插件。

**参数:**
- `cluster_id` (str, 必需): 集群ID
- `addons` (List[Dict], 必需): 要修改的插件列表，每个插件包含:
  - `name` (str, 必需): 插件名称
  - `config` (Dict, 可选): 插件配置
  - `version` (str, 可选): 插件版本
  - `properties` (Dict, 可选): 插件属性

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