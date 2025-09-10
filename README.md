# Alibaba Cloud Container Service MCP Server


阿里云 ACK MCP Server (Python版)

本项目是一个基于 Python 的 MCP (Model Context Protocol) 服务器，旨在为**阿里云容器服务（ACK）**提供强大的运维、管理和操作能力。它通过一系列 MCP 工具，将复杂的云原生操作封装为简单、统一的接口。

服务器采用 `fastmcp` 和 `FastAPI` 构建，拥有一个清晰、解耦且易于扩展的现代化架构。

关于架构的详细设计理念和数据流，请参阅 [`DESIGN.md`](./DESIGN.md)。

## 功能特性

- **阿里云 ACK 管理**:
    - `scale_nodepool`: 对指定的节点池进行扩容。
    - `remove_nodepool_nodes`: 从指定的节点池中安全地移除一个或多个节点。
    - `describe_task_info`: 查询指定异步任务（如扩容、移除节点）的详细状态。
    - `create_cluster_diagnosis`: 创建集群诊断任务。
    - `get_cluster_diagnosis_result`: 获取集群诊断结果。
- **Kubernetes 原生操作**:
    - `kubectl`: 针对已配置的 ACK 集群，执行任意 `kubectl` 命令。成功时返回 `stdout`，失败时抛出包含 `stderr` 的错误。
- **阿里云可观测性**:
    - `cms_execute_promql_query`: 在 ARMS 指标库中执行 PromQL 查询。
    - `cms_translate_text_to_promql`: 将自然语言文本转换为 PromQL 查询。
    - `sls_execute_sql_query`: 在 SLS 日志库中执行 Log-SQL 查询。
    - `sls_translate_text_to_sql_query`: 将自然语言文本转换为 Log-SQL 查询。
    - `sls_diagnose_query`: 诊断失败的 Log-SQL 查询。
- **企业级架构**:
    - **清晰解耦**: 工具层、服务层与认证层完全分离，易于维护和扩展。
    - **动态凭证注入**: 支持通过 HTTP Header 为每一次请求动态、安全地传递阿里云凭证，完美支持多租户或临时凭证（STS）场景。
    - **健壮的错误处理**: 所有工具都提供清晰的错误传递，底层服务的错误信息（如 `stderr`）会完整地返回给用户。
    - **类型安全的返回**: 工具返回定义良好的 Pydantic 模型或原生类型，而不是通用字典，确保了接口的稳定性和可预测性。

## 如何运行

1.  **安装依赖**:
    本项目使用 `uv` 作为包管理工具。
    ```bash
    # 建议先根据 uv.lock 文件同步依赖
    uv sync
    ```
    如果 `uv.lock` 不存在或需要重新安装，可以执行以下命令：
    ```bash
    uv pip install "fastmcp" fastapi uvicorn pydantic-settings alibabacloud_cs20151215 alibabacloud_tea_util
    ```

2.  **配置服务器**:
    在项目根目录下创建一个 `.env` 文件来配置服务。您可以复制并修改以下示例：
    ```env
    # 服务监听的端口 (默认为 8080)
    HTTP_PORT=8080

    # 默认的阿里云区域 (默认为 cn-beijing)
    ALIYUN_REGION="cn-beijing"

    # 用于客户端认证的 Bearer Token (可选，推荐生产环境设置)
    # 如果设置了此值，所有客户端请求都必须包含一个匹配的 Authorization Header。
    # 示例: Authorization: Bearer your-secret-token
    MCP_AUTH_TOKEN="your-secret-token"
    ```

3.  **启动服务器**:
    ```bash
    python -m app.main
    ```
    服务将启动在 `.env` 文件中指定的端口上（默认为 8080）。

## 如何使用

您可以使用任何兼容 MCP 协议的客户端与本服务器交互。服务器的 MCP 端点暴露在 `/mcp/v1`。

### 认证机制

- **Bearer Token (推荐)**: 如果在 `.env` 文件中设置了 `MCP_AUTH_TOKEN`，您的所有请求都必须包含以下 Header:
    - `Authorization: Bearer <your-secret-token>`

- **阿里云凭证 (按需提供)**: 如需为单次请求指定特定的阿里云凭证，请在 HTTP Headers 中提供。这会覆盖服务器环境中的任何默认凭证。
    - `X-Aliyun-Access-Key-Id`: 您的 AccessKey ID。
    - `X-Aliyun-Access-Key-Secret`: 您的 AccessKey Secret。
    - `X-Aliyun-Security-Token` (可选): 如果使用 STS 临时凭证，请提供此项。
    - `X-Aliyun-Region` (可选): 为本次请求指定特定的阿里云区域。

如果请求的 Header 中未提供任何凭证，服务将回退使用其运行环境中的默认凭证链（例如，`ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `ALIBABA_CLOUD_ACCESS_KEY_SECRET` 环境变量）。

### 上下文处理机制

本服务器采用了一种强大而灵活的上下文处理机制，旨在简化工具的使用，同时保持控制的精确性。

**核心原则**:
- **`cluster_id` 是关键**: 对于需要明确操作目标的工具（如 `scale_nodepool` 或 `sls_execute_sql_query`），用户在调用时传入的 `cluster_id` 参数是绝对的，它定义了该次操作的目标。
- **后台自动上下文发现**: 一旦工具接收到 `cluster_id`，系统后台会立即为其自动查找所有必需的下游上下文信息（如 `region_id`、默认的 `sls_project` 和 `sls_log_store` 等）。

**参数优先级**:
- **显式参数优先**: 用户在工具调用中直接提供的参数（如 `logstore`）具有最高优先级。
- **自动发现兜底**: 如果未提供可选参数（如 `logstore`），系统将使用通过 `cluster_id` 发现的默认值。

这种设计确保了工具接口的简洁性（通常只需传入 `cluster_id`），同时为高级用户提供了精确控制操作细节的能力。

## 如何扩展

### 添加一个新的工具

1.  **创建服务逻辑**: 如果新工具需要与新的云服务 API 交互，请在 `app/services/` 目录下添加新的服务文件，例如 `app/services/new_cloud_service.py`。
2.  **创建依赖项**: 在 `app/dependencies/services.py` 中，添加一个新的依赖注入函数（例如 `get_new_cloud_service`）来创建和提供该服务。
3.  **定义工具**: 在 `app/tools/` 目录下创建新的工具文件（例如 `app/tools/new_cloud_tools.py`）。在其中定义工具的输入模型（Pydantic）和异步工具函数，并使用 `Depends` 来注入您刚刚创建的服务。
4.  **注册工具**: 打开 `app/tools/registry.py`，导入您的新工具函数，并将其添加到 `register_all_tools` 函数中。

完成以上步骤后，服务在重启时会自动发现并加载您的新工具。


# Installation and Setup

## Local installation

```
pip install -r requirements.txt
```

# How to run it.

## Authorization

### 1. 阿里云 RAM 策略

### 2. Kubernetes RBAC 策略

## Configuration

  ```.env
  # .env 文件内容，包含阿里云访问凭证
  ACCESS_KEY_ID={YOUR_ALIYUN_ACCESS_KEY}
  ACCESS_SECRET_KEY={YOUR_ALIYUN_ACCESS_SECRET_KEY}
  REGION_ID={YOUR_ALIYUN_REGION}
  
  ```
