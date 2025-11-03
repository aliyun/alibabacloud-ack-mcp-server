# 阿里云容器服务 MCP Server 设计指南

本文档概述了阿里云容器服务 MCP Server (ack-mcp-server) 的架构设计、开发指南和最佳实践。基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 协议实现，提供 AI 原生的容器运维工具集。

## 前言

遵循这些设计指南将帮助创建一致、可维护和用户友好的 MCP 服务器。ack-mcp-server 项目采用统一的单体架构，通过 Handler 模式组织功能模块，提供了一个可靠的基础，用于开发新的容器运维能力。

### 关键要点

1. **统一架构**：所有功能集成在主服务器中，避免子服务器的复杂性
2. **Handler 模式**：通过 Handler 类组织功能，模块化且易于扩展
3. **生命周期管理**：RuntimeProvider 统一管理资源生命周期
4. **类型安全**：使用 Pydantic 模型和类型注释
5. **企业级特性**：完善的错误处理、日志记录和安全机制

### 后续扩展

添加新功能时：

1. 创建新的 Handler 类（如 `new_feature_handler.py`）
2. 在 Handler 中实现 MCP 工具和资源
3. 在 `main_server.py` 中注册 Handler
4. 在 `runtime_provider.py` 中添加所需的客户端或资源
5. 编写单元测试确保质量
6. 更新文档


## 项目结构

ack-mcp-server 采用统一的单体架构，所有功能模块作为 Handler 集成到主服务器中：

```
alibabacloud-ack-mcp-server/
├── CHANGELOG.md            # 版本历史和变更记录
├── LICENSE                 # 许可证信息
├── DESIGN.md              # 架构设计文档（本文档）
├── README.md              # 项目说明、使用指南
├── Makefile               # 构建和开发命令
├── pyproject.toml         # 项目配置和依赖管理
├── requirements.txt       # Python 依赖列表
├── pytest.ini             # pytest 配置
├── mypy.ini               # mypy 类型检查配置
├── mcp.json               # MCP 配置文件
├── deploy/                # 部署相关文件
│   ├── Dockerfile         # Docker 镜像构建文件
│   ├── helm/              # Kubernetes Helm Chart
│   └── README.md          # 部署说明
├── benchmarks/            # 性能测试和基准测试
│   ├── agents/            # 不同 AI Agent 的配置
│   ├── tasks/             # 测试任务场景
│   └── run_benchmark.sh   # 基准测试运行脚本
└── src/                   # 源代码目录
    ├── __init__.py        # 包初始化
    ├── main_server.py     # 主服务器入口
    ├── config.py          # 配置管理
    ├── models.py          # Pydantic 数据模型
    ├── runtime_provider.py # 运行时提供者（生命周期管理）
    ├── fastmcp.json       # FastMCP 配置
    ├── interfaces/        # 接口定义
    │   └── runtime_provider.py  # 运行时提供者接口
    ├── prometheus_metrics_guidance/  # Prometheus 指标指导知识库
    │   ├── metrics_dictionary/      # 指标字典
    │   └── promql_best_practice/    # PromQL 最佳实践
    ├── tests/             # 测试目录
    │   ├── test_*.py      # 各模块单元测试
    │   └── verify_all_test_coverage.py  # 测试覆盖率验证
    └── *_handler.py       # 功能处理器模块
        ├── ack_cluster_handler.py      # ACK 集群管理
        ├── kubectl_handler.py          # Kubernetes 操作
        ├── ack_prometheus_handler.py   # Prometheus 监控
        ├── ack_audit_log_handler.py    # 审计日志查询
        ├── ack_controlplane_log_handler.py  # 控制面日志
        ├── ack_diagnose_handler.py     # 集群诊断
        └── ack_inspect_handler.py      # 集群巡检
```

## 架构设计

### 架构原则

ack-mcp-server 采用分层架构，遵循以下设计原则：

1. **关注点分离**：
   - `main_server.py`：服务器入口、生命周期管理、Handler 注册
   - `runtime_provider.py`：资源生命周期管理、客户端初始化
   - `*_handler.py`：具体功能处理器，实现 MCP 工具和资源
   - `models.py`：数据模型和验证逻辑
   - `config.py`：配置管理

2. **模块化设计**：
   - 每个 Handler 为独立模块，负责特定领域功能
   - Handler 通过构造函数注册到主服务器
   - 支持动态添加和移除 Handler

3. **单一职责**：
   - 每个模块只负责一个明确的功能领域
   - 避免跨模块的紧耦合

4. **一致性命名约定**：
   - 清晰、一致的文件、类、函数命名
   - 使用描述性的名称

### 核心组件

#### 1. main_server.py - 服务器入口

主服务器负责：
- 创建 FastMCP 服务器实例
- 配置生命周期管理
- 注册所有 Handler 模块
- 处理命令行参数
- 启动服务器

#### 2. runtime_provider.py - 运行时提供者

负责管理服务器生命周期内的资源：
- 阿里云客户端工厂（CS, ARMS, SLS）
- Kubernetes 客户端
- Prometheus 指标指导知识库
- 其他共享资源

#### 3. Handler 模块 - 功能处理器

每个 Handler 实现特定领域的 MCP 工具和资源：

## 鉴权方案策略 / 集群Kubeconfig证书管理

ack-mcp-server中tools所需权限分为：
- 访问Kubernetes集群rbac权限，通过集群证书访问
- 访问阿里云服务权限，通过阿里云OpenAPI访问，通过阿里云Ram鉴权体系鉴权
- 访问可观测数据，如Prometheus指标、日志系统数据

### Kubernetes集群访问策略

通过配置ack-mcp-server参数：
```shell
KUBECONFIG_MODE = ACK_PUBLIC(默认，通过ACK OpenAPI获取公网kubeconfig访问) / ACK_PRIVATE （通过ACK OpenAPI获取内网kubeconfig访问） / LOCAL(本地kubeconfig)

KUBECONFIG_PATH = xxx (Optional参数，只有当KUBECONFIG_MODE = LOCAL 时生效，指定本地kubeconfig文件路径)
```

注意：本地测试使用公网访问集群kubeconfig需在[对应ACK开启公网访问kubeconfig](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/obtain-the-kubeconfig-file-of-a-cluster-and-use-kubectl-to-connect-to-the-cluster#a4bbf3452azq5)。

默认配置为通过阿里云OpenAPI获取公网kubeconfig访问，默认ttl=1h。

推荐生产使用时，打通集群网络内网访问后，推荐使用KUBECONFIG_MODE = ACK_PRIVATE，通过阿里云OpenAPI获取内网kubeconfig访问，避免公网暴露kubeconfig。

### 访问阿里云服务权限

通过[阿里云Ram鉴权体系](https://help.aliyun.com/zh/sdk/developer-reference/v2-manage-python-access-credentials)。

推荐生产使用，推荐通过子账号控制授权策略，满足安全最小使用权限范围最佳实践。

### 访问可观测数据

优先访问ACK集群对应的阿里云Prometheus服务数据，如没有对应服务，通过env参数寻找可观测数据的访问地址。
通过配置可指定[Prometheus Read HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/)。

当该集群没有阿里云Prometheus对应实例数据，ack-mcp-server将按按如下优先级寻找={prometheus_http_api_url}访问可观测数据。
```shell
env参数配置：
PROMETHEUS_HTTP_API_{cluster_id}={prometheus_http_api_url}
PROMETHEUS_HTTP_API={prometheus_http_api_url}
```

## 包命名和版本管理

### 项目命名

遵循阿里云容器服务命名规范：
- 名称空间：`alibabacloud-cs`
- 包名：小写字母 + 连字符（在 pyproject.toml 中）
- Python 模块：小写字母 + 下划线

示例：

```toml
# 在 pyproject.toml 中
name = "alibabacloud-ack-mcp-server"
```

```python
# Python 导入
from ack_cluster_handler import ACKClusterHandler
from kubectl_handler import KubectlHandler
```

### 版本信息

在 `__init__.py` 中存储版本信息：

```python
# src/__init__.py
"""阿里云容器服务 MCP Server。"""

__version__ = "0.1.0"
```

### 版本同步

使用 commitizen 配置自动更新版本：

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version = "0.0.0"
tag_format = "$version"
version_files = [
    "pyproject.toml:version",
    "src/__init__.py:__version__"
]
update_changelog_on_bump = true
```

## 许可证和版权头

在每个源文件顶部包含标准许可证头：

```python
# Copyright aliyun.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

## 常量管理

在专用的模块中组织常量（如需要）：

1. **常量命名**：使用大写字母 + 下划线
2. **分组**：将相关常量组织在一起
3. **文档**：添加注释说明目的和有效值

示例：

```python
"""常量定义。"""

# 默认配置值
DEFAULT_REGION_ID = "cn-hangzhou"
DEFAULT_TIMEOUT = 30  # 秒
DEFAULT_PAGE_SIZE = 20

# API 端点
CS_ENDPOINT_TEMPLATE = "cs.{region_id}.aliyuncs.com"
CS_CENTER_ENDPOINT = "cs.aliyuncs.com"
ARMS_ENDPOINT_TEMPLATE = "arms.{region_id}.aliyuncs.com"
SLS_ENDPOINT_TEMPLATE = "{region_id}.log.aliyuncs.com"

# 日志级别
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
```

## 类型定义和 Pydantic 模型

### 最佳实践

1. 所有数据模型使用 Pydantic，并包含完整的类型注释
2. 定义清晰的类层次结构，适当使用继承
3. 为受约束的值定义枚举
4. 包含全面的字段验证
5. 使用详细的 docstring 文档化模型

### 示例

```python
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Literal, Optional

class ClusterState(str, Enum):
    """集群状态枚举。

    Attributes:
        INITIAL: 初始化中
        RUNNING: 运行中
        UPDATING: 更新中
        DELETING: 删除中
        FAILED: 失败
    """
    INITIAL = 'initial'
    RUNNING = 'running'
    UPDATING = 'updating'
    DELETING = 'deleting'
    FAILED = 'failed'

class ClusterInfo(BaseModel):
    """集群信息模型。

    Attributes:
        cluster_id: 集群 ID
        name: 集群名称
        region_id: 所在地域
        state: 集群状态
        cluster_type: 集群类型
        created: 创建时间
    """
    cluster_id: str = Field(..., description="集群的唯一标识符")
    name: str = Field(..., description="集群名称")
    region_id: str = Field(default="cn-hangzhou", description="集群所在地域")
    state: ClusterState = Field(default=ClusterState.INITIAL, description="集群当前状态")
    cluster_type: str = Field(default="ManagedKubernetes", description="集群类型")
    created: Optional[str] = Field(default=None, description="创建时间")

    @field_validator('cluster_id')
    @classmethod
    def validate_cluster_id(cls, v: str) -> str:
        """验证集群 ID 格式。"""
        if not v or len(v) < 10:
            raise ValueError('集群 ID 必须至少 10 个字符')
        return v

    @model_validator(mode='after')
    def validate_model(self):
        """验证模型整体一致性。"""
        # 添加额外的验证逻辑
        return self
```

## 函数参数与 Pydantic Field

MCP 工具函数应使用 Pydantic 的 `Field` 来提供详细描述：

```python
from fastmcp import Context
from pydantic import Field
from typing import Optional, List, Literal

@mcp.tool(name='query_prometheus')
async def query_prometheus_tool(
    ctx: Context = None,
    query: str = Field(
        ..., 
        description='要执行的 PromQL 查询语句'
    ),
    cluster_id: str = Field(
        ...,
        description='集群 ID，必须从 resource://clusters 资源获取有效的集群 ID',
    ),
    start_time: Optional[str] = Field(
        None,
        description='查询开始时间，RFC3339 格式或相对时间（如 "1h", "30m"）',
    ),
    end_time: Optional[str] = Field(
        None,
        description='查询结束时间，RFC3339 格式或相对时间',
    ),
    step: str = Field(
        '1m',
        description='查询步长，如 "1m", "5m", "1h"',
    ),
) -> str:
    """执行 Prometheus PromQL 查询。

    ## 使用要求
    - 必须先使用 `resource://clusters` 资源获取有效的集群 ID
    - 可以对不同集群或同一集群进行多次查询

    ## 查询提示
    - 使用清晰、具体的 PromQL 表达式
    - 可以多次调用此工具来收集全面信息
    - 使用适当的时间范围和步长以获取最佳结果

    [... 详细功能文档 ...]
    """
    # 实现逻辑
    pass
```

### Field 指南

1. **必需参数**：使用 `...` 作为默认值表示参数是必需的
2. **可选参数**：提供合理的默认值，并在类型注释中标记为 `Optional`
3. **描述**：为每个参数编写清晰、信息丰富的描述
4. **验证**：使用 Field 约束，如 `ge`（大于等于）、`le`（小于等于）、`min_length`、`max_length`
5. **枚举值**：对于有固定值集合的参数，使用 `Literal`

### 在参数描述中指导 AI 模型

参数描述中可以包含对 AI 助手的明确指示。这对于需要上下文特定信息的参数尤其重要。

#### 最佳实践

1. **明确指示**：清楚说明 AI 应该做什么
2. **突出重要性**：对关键指示使用“必须”、“重要”、“关键”等关键词
3. **提供上下文**：解释为什么该指示很重要
4. **一致的格式**：在所有参数中以类似方式格式化 AI 特定指示
5. **放在末尾**：将给 AI 的指示放在描述的末尾，在解释参数目的之后

## 资源和工具

MCP 服务器实现两种主要类型的端点：

### 资源定义

MCP协议中，“资源”为定制化地请求和访问本地的资源 (Resources allow servers to share data that provides context to language models, such as files, database schemas, or application-specific information. Each resource is uniquely identified by a URI.)

通过服务查询资源，尽量设计为一个tool，如："list_clusters"。

资源提供工具可以使用的数据：

```python
@mcp.resource(uri='resource://clusters', name='ACKClusters', mime_type='application/json')
async def clusters_resource(ctx: Context = None) -> str:
    """列出所有可用的阿里云容器服务集群。

    此资源返回集群 ID 到其详细信息的映射，包括：
    - name: 集群的可读名称
    - region_id: 集群所在地域
    - state: 集群当前状态
    - cluster_type: 集群类型

    ## 响应结构示例：
    ```json
    {
        "c1234567890abcdef": {
            "name": "生产环境集群",
            "region_id": "cn-hangzhou",
            "state": "running",
            "cluster_type": "ManagedKubernetes"
        },
        "c9876543210fedcba": {
            "name": "测试环境集群",
            "region_id": "cn-beijing",
            "state": "running",
            "cluster_type": "ManagedKubernetes"
        }
    }
    ```

    ## 如何使用此信息：
    1. 提取集群 ID（如 "c1234567890abcdef"）以便与其他工具一起使用
    2. 注意地域信息以确保操作在正确的地域
    3. 使用名称确定哪个集群与用户查询最相关
    """
    return json.dumps(await discover_clusters(cs_client))
```

资源指南：

1. 使用一致的 URI 模式：`resource://name`
2. 指定 MIME 类型以便正确处理内容
3. 返回工具可以轻松使用的格式的数据
4. 全面文档化资源结构和使用方法

### 工具定义

工具提供 LLM 可以使用的功能：

```python
@mcp.tool(name='list_clusters')
async def list_clusters_tool(
    ctx: Context = None,
    region_id: str = Field(default="cn-hangzhou", description="阿里云地域 ID"),
) -> str:
    """查询指定地域的 ACK 集群列表。
    
    ## 使用说明
    - 返回指定地域下的所有 ACK 集群信息
    - 包括集群 ID、名称、状态、类型等信息
    
    ## 参数
    - region_id: 阿里云地域，默认为 cn-hangzhou
    
    ## 返回值
    JSON 格式的集群列表
    """
    # 实现逻辑
    pass
```

工具指南：

1. 使用描述性的工具名称，一致使用 `camelCase` 或 `snake_case`
2. 包含 Context 参数用于错误报告
3. 为所有参数使用详细的 Field 描述
4. 尽可能使用 Pydantic 模型返回结构化响应
5. 全面文档化工具的目的、输入和输出

### 工具命名约定

为了保持一致性和兼容性，工具名称必须遵循以下规则：

- ✅ **最多 64 个字符**
- ✅ 必须以字母开头
- ✅ 仅使用小写字母和连字符 (`-`)
- ❌ 避免特殊字符（如 `@`、`$`、`!`）
- ❌ 不能以数字开头

#### ✅ 有效示例：
- `list-clusters`
- `query-prometheus`
- `get-pod-logs`

#### ❌ 无效示例：
- `123tool`
- `tool!@#$`
- `name-that-is-way-too-long-and-goes-beyond-the-sixty-four-character-limit-of-the-rule`

## 异步编程

MCP 服务器使用异步编程模式：

1. **异步函数**：所有 MCP 工具和资源函数使用 `async`/`await`
2. **并发操作**：使用 `asyncio.gather` 进行并发操作
3. **非阻塞 I/O**：确保外部 API 调用尽可能使用异步库
4. **上下文管理**：正确处理异步上下文管理器

示例：

```python
import asyncio
from typing import List

@mcp.tool(name='parallel-operations')
async def perform_parallel_operations(
    ctx: Context = None, 
    query: str = Field(..., description="查询字符串")
) -> str:
    """并发执行多个操作。"""

    # 并发执行操作
    results = await asyncio.gather(
        operation1(query),
        operation2(query),
        operation3(query),
        return_exceptions=True
    )

    # 处理结果
    valid_results = [r for r in results if not isinstance(r, Exception)]

    return json.dumps(valid_results)
```

## 响应格式化

标准化所有工具的响应格式：

1. **JSON 响应**：为结构化数据返回 JSON 序列化字符串
2. **路径格式**：使用 URI 格式表示文件路径（如 `file:///path/to/file`）
3. **响应模型**：定义 Pydantic 模型以保证响应结构一致性

示例：

```python
from pydantic import BaseModel
from typing import List

class OperationResponse(BaseModel):
    """操作响应模型。"""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

@mcp.tool(name='execute-operation')
async def execute_operation(
    ctx: Context = None,
    operation: str = Field(..., description="要执行的操作"),
) -> OperationResponse:
    """执行操作并返回结果。"""
    # 实现逻辑
    # ...
    
    return OperationResponse(
        status='success',
        message='操作成功完成',
        data={'result': result}
    )
```

## 日志记录与 Loguru

所有 MCP 服务器都应使用 Loguru 进行一致的结构化日志记录：

```python
import sys
import os
from loguru import logger

# 移除默认处理器并添加自定义配置
logger.remove()
logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'WARNING'))

# 使用示例
logger.debug("详细信息，通常只在诊断问题时感兴趣")
logger.info("确认事情按预期工作")
logger.warning("发生了意外情况，但应用程序仍然工作")
logger.error("应用程序无法执行某些功能")
logger.critical("严重错误，表明程序本身可能无法继续运行")
```

### 日志指南

1. 通过环境变量配置日志级别（如 `FASTMCP_LOG_LEVEL`）
2. 记录重要操作，尤其是在服务边界
3. 在日志消息中包含上下文（请求 ID、操作详细信息）
4. 根据严重性使用适当的日志级别
5. 记录带有完整上下文的异常

## 阿里云服务认证

访问阿里云服务的 MCP 服务器应一致处理认证：

每个 Handler 应在 `runtime_provider.py` 中实现认证逻辑和客户端初始化。

阿里云客户端凭证（如 AccessKey 和 AccessKeySecret）不应存储在代码中，而应通过 create_main_server 方法的配置参数传递。

### 认证指南

1. `main_server.py` 支持通过 `ACCESS_KEY_ID` 和 `ACCESS_KEY_SECRET` 环境变量作为输入配置
2. 允许通过 `REGION_ID` 环境变量配置地域
3. 为认证失败提供清晰的错误消息
4. 在 README 中文档化所需的 RAM 权限

### 示例

```python
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_tea_openapi import models as open_api_models

# 初始化凭证客户端（使用全局默认凭证链）
credential_client = CredentialClient()

# 创建客户端工厂
def cs_client_factory(target_region: str, cfg: Dict[str, Any]):
    """CS 客户端工厂。"""
    cs_config = open_api_models.Config(credential=credential_client)
    
    # 支持通过配置覆盖 AK 信息
    if cfg.get("access_key_id"):
        cs_config.access_key_id = cfg.get("access_key_id")
    if cfg.get("access_key_secret"):
        cs_config.access_key_secret = cfg.get("access_key_secret")
    
    # 配置地域和端点
    if target_region == "CENTER":
        cs_config.endpoint = "cs.aliyuncs.com"
    else:
        cs_config.region_id = target_region or cfg.get("region_id") or "cn-hangzhou"
        cs_config.endpoint = f"cs.{cs_config.region_id}.aliyuncs.com"
    
    return CS20151215Client(cs_config)
```

## 环境变量

MCP 服务器应支持通过环境变量进行配置：

```python
import os

# 通过环境变量配置
LOG_LEVEL = os.environ.get('FASTMCP_LOG_LEVEL', 'WARNING')
REGION_ID = os.environ.get('REGION_ID', 'cn-hangzhou')
ACCESS_KEY_ID = os.environ.get('ACCESS_KEY_ID')
ACCESS_KEY_SECRET = os.environ.get('ACCESS_KEY_SECRET')
DEFAULT_CLUSTER_ID = os.environ.get('DEFAULT_CLUSTER_ID')
```

### 环境变量指南

1. 使用一致的命名约定（`大写字母_下划线`）
2. 为可选配置提供合理的默认值
3. 在 README 中文档化所有支持的环境变量
4. 优雅地验证和处理缺失的必需配置
5. 使用环境变量处理可能因部署而异的配置

### 使用 .env 文件

项目应支持使用 .env 文件进行本地开发：

```python
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 现在可以访问环境变量
access_key_id = os.getenv('ACCESS_KEY_ID')
```

提供 `.env.example` 文件作为示例：

```bash
# .env.example
ACCESS_KEY_ID=your_access_key_id
ACCESS_KEY_SECRET=your_access_key_secret
REGION_ID=cn-hangzhou
DEFAULT_CLUSTER_ID=c1234567890abcdef
FASTMCP_LOG_LEVEL=INFO
```

## 错误处理

MCP 工具应实现全面的错误处理：

```python
from fastmcp import Context
from loguru import logger

@mcp.tool(name='query-prometheus')
async def query_prometheus_tool(
    ctx: Context = None,
    query: str = Field(..., description="PromQL 查询语句"),
    cluster_id: str = Field(..., description="集群 ID"),
) -> str:
    """执行 Prometheus PromQL 查询。"""

    try:
        logger.info(f'执行 Prometheus 查询: {query}, 集群: {cluster_id}')
        
        # 获取客户端
        providers = ctx.request_context.lifespan_context.get("providers", {})
        # ... 执行查询
        
        if response.status == 'success':
            return json.dumps(response.data)
        else:
            logger.error(f'Prometheus 查询返回错误状态: {response.message}')
            await ctx.error(f'查询失败: {response.message}')
            raise Exception(f'查询失败: {response.message}')
            
    except Exception as e:
        logger.error(f'执行 Prometheus 查询时出错: {str(e)}')
        await ctx.error(f'查询错误: {str(e)}')
        raise
```

### 错误处理指南

1. 使用 try/except 块捕获和处理异常
2. 记录带有适当上下文的异常
3. 使用 MCP 上下文进行错误报告（`ctx.error`）
4. 向客户端提供有意义的错误消息
5. 考虑对错误进行分类（客户端错误 vs 服务器错误）

## 文档编写

### Docstrings

所有模块、类和函数都应包含全面的 docstring：

```python
"""执行 Prometheus PromQL 查询。

## 使用要求
- 必须先使用 `resource://clusters` 资源获取有效的集群 ID
- 可以对不同集群或同一集群进行多次查询

## 查询提示
- 使用清晰、具体的 PromQL 表达式以获得最佳结果
- 可以多次调用此工具来收集全面信息
- 将复杂问题分解为多个聚焦查询
- 考虑分别查询事实信息和解释

## 工具输出格式
响应包含多个 JSON 对象（每行一个），每个对象表示一个检索的文档，包含：
- timestamp: 时间戳
- value: 指标值
- labels: 标签信息

## 解释最佳实践
1. 从多个结果中提取和组合关键信息
2. 如果响应不相关，尝试不同的查询
3. 在几次尝试后，向用户询问澄清或不同的查询
"""
```

### MCP 服务器指令

为使用 MCP 服务器的 LLM 提供详细指令：

```python
mcp = FastMCP(
    'alibabacloud-cs-main-server',
    instructions=f"""
# 阿里云容器服务 MCP Server

这是阿里云容器服务的主 MCP 服务器，提供全面的 Kubernetes 
集群管理能力。

## 可用功能

### 1. ACK 集群管理
- 查询集群列表
- 集群诊断
- 集群巡检

### 2. Kubernetes 操作
- 资源增删改查
- 获取日志和事件
- 详细资源描述

### 3. 可观测性
- Prometheus 指标查询
- 控制面日志分析
- 审计日志查询

使用此服务器简化您的 Kubernetes 运维和监控工作流。
""",
)
```

### 文档指南

1. 包含详细的 README，附带设置说明和使用示例
2. 文档化所有可用的工具和资源
3. 提供输入和输出格式的示例
4. 解释限制和边界情况
5. 文档化所有环境变量和配置选项

## 代码风格和代码检查

MCP 服务器应遵循一致的代码风格和代码检查：

1. **代码格式化工具**：使用 `ruff format` 进行一致的代码格式化
2. **代码检查工具**：使用 `ruff` 和 `mypy` 进行类型检查和代码质量检查
3. **Pre-commit 钩子**：配置 pre-commit 以强制执行标准

### pyproject.toml 配置示例

```toml
[tool.ruff]
line-length = 99
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "Q"]
ignore = ["E203", "E501"]

[tool.ruff.lint.isort]
known-first-party = ["ack_cluster_handler", "kubectl_handler"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

## 测试

MCP 服务器应具有全面的测试覆盖：

1. **单元测试**：为单个函数编写测试
2. **集成测试**：为 API 通信编写测试
3. **端到端测试**：为完整工作流编写测试
4. **Mock 阿里云服务**：在没有真实阿里云凭证的情况下进行测试
5. **测试覆盖率报告**：确保足够的覆盖率

### 测试工具

- 使用 pytest 进行测试
- 使用 pytest-asyncio 测试异步函数
- 使用 pytest-cov 生成覆盖率报告
- 实现 CI/CD 管道进行自动化测试

### 测试示例

```python
import pytest
from unittest.mock import Mock, AsyncMock
from ack_cluster_handler import ACKClusterHandler

@pytest.mark.asyncio
async def test_list_clusters():
    """测试查询集群列表。"""
    # 设置 mock
    mock_mcp = Mock()
    mock_config = {
        "region_id": "cn-hangzhou",
        "access_key_id": "test_ak",
        "access_key_secret": "test_sk"
    }
    
    # 创建 handler
    handler = ACKClusterHandler(mock_mcp, mock_config)
    
    # 创建 mock 上下文
    mock_ctx = Mock()
    mock_ctx.request_context.lifespan_context = {
        "providers": {
            "cs_client_factory": lambda r, c: mock_cs_client
        }
    }
    
    # 执行测试
    result = await handler.list_clusters(mock_ctx, region_id="cn-hangzhou")
    
    # 验证结果
    assert result is not None
    assert "clusters" in result

@pytest.mark.asyncio
async def test_list_clusters_error():
    """测试查询集群列表错误处理。"""
    # 测试错误情况
    pass
```

### 测试覆盖率要求

- 所有 Handler 的工具方法必须有独立的单元测试
- 测试覆盖率需达到 >= 85%
- 测试应包含正常调用、参数验证、错误处理等场景
- 使用 pytest-asyncio 支持异步测试

## 部署指南

### Docker 部署

项目包含完整的 Docker 支持：

```bash
# 构建镜像
make docker-build-amd64

# 运行容器
docker run -d \
  -e ACCESS_KEY_ID=your_ak \
  -e ACCESS_KEY_SECRET=your_sk \
  -e REGION_ID=cn-hangzhou \
  -p 8000:8000 \
  alibabacloud-ack-mcp-server:latest \
  python -m main_server --transport sse --host 0.0.0.0 --port 8000
```

### Kubernetes 部署

使用 Helm Chart 部署到 Kubernetes 集群：

```bash
# 安装
helm install ack-mcp-server ./deploy/helm \
  --set accessKeyId=your_ak \
  --set accessKeySecret=your_sk \
  --set transport=sse \
  -n kube-system

# 升级
helm upgrade ack-mcp-server ./deploy/helm \
  --set accessKeyId=your_ak \
  --set accessKeySecret=your_sk \
  -n kube-system

# 卸载
helm uninstall ack-mcp-server -n kube-system
```

### 本地开发

```bash
# 安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate

# 复制配置文件
cp .env.example .env

# 编辑 .env 文件填写 AccessKey 信息

# 运行服务器
make run          # stdio 模式
make run-http     # HTTP 模式
make run-sse      # SSE 模式
```

## 性能优化

### 客户端复用

通过 RuntimeProvider 的客户端工厂模式，实现客户端复用：

```python
def cs_client_factory(target_region: str, cfg: Dict[str, Any]):
    """每次调用都重新创建 CS 客户端。"""
    # 根据需要创建新客户端
    return CS20151215Client(cs_config)
```

### 异步并发

利用 asyncio 实现并发操作：

```python
# 并发查询多个集群
results = await asyncio.gather(
    query_cluster_1(),
    query_cluster_2(),
    query_cluster_3(),
    return_exceptions=True
)
```

### 缓存策略

对于 Prometheus 指标指导等静态数据，在初始化时加载并缓存：

```python
def initialize_prometheus_guidance(self) -> Dict[str, Any]:
    """初始化 Prometheus 指标指导数据。"""
    # 从文件加载并缓存在内存中
    return guidance_data
```

## 安全最佳实践

1. **最小权限原则**：仅授予必要的 RAM 权限
2. **凭证管理**：
   - 使用环境变量传递凭证
   - 支持请求级 AK 注入
   - 不在代码中硬编码凭证
3. **网络安全**：
   - 使用 HTTPS 端点
   - 验证 SSL 证书
4. **日志安全**：
   - 不记录敏感信息
   - 脱敏后记录错误信息
5. **读写权限控制**：
   - 默认只读模式
   - 通过 `--allow-write` 参数启用写权限

