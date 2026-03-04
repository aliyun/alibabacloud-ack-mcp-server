# 贡献指南

首先，感谢您花时间为本项目做出贡献！❤️

我们欢迎并重视各种类型的贡献。请查看[目录](#目录)了解不同的贡献方式以及本项目如何处理这些贡献。在做出贡献之前，请务必阅读相关章节，这将使维护者的工作更轻松，并为所有参与者提供更流畅的体验。我们期待您的贡献！🎉

> 如果您喜欢这个项目，但没有时间贡献，也没关系。还有其他简单的方式来支持项目并表达您的赞赏，我们也会非常高兴：
> - 为项目点星标 ⭐
> - 在社交媒体上分享
> - 在您的项目 README 中引用本项目
> - 在本地技术聚会上提及本项目并告诉您的朋友/同事

## 目录

- [行为准则](#行为准则)
- [我有疑问](#我有疑问)
- [我想贡献](#我想贡献)
  - [报告 Bug](#报告-bug)
  - [提出功能建议](#提出功能建议)
  - [首次代码贡献](#首次代码贡献)
  - [改进文档](#改进文档)
- [开发指南](#开发指南)
  - [开发环境设置](#开发环境设置)
  - [项目结构](#项目结构)
  - [编码规范](#编码规范)
  - [测试规范](#测试规范)
  - [提交信息规范](#提交信息规范)
- [Pull Request 流程](#pull-request-流程)
- [加入项目团队](#加入项目团队)

## 行为准则

本项目及其所有参与者均受[行为准则](CODE_OF_CONDUCT.md)约束。参与即表示您同意遵守此准则。请向项目维护者报告不可接受的行为。

## 我有疑问

> 在提问之前，请先阅读可用的[文档](README.md)和[设计文档](DESIGN.md)。

在提问之前，最好先搜索现有的 [Issues](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues)，看看是否能找到答案。如果找到了相关 issue 但仍需要澄清，可以在该 issue 中提问。同时也建议先在互联网上搜索答案。

如果您仍然需要提问，我们建议：

- 创建一个新的 [Issue](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues/new)
- 尽可能提供详细的上下文信息
- 提供项目和平台版本信息（Python 版本、操作系统、FastMCP 版本等）

我们会尽快处理您的问题。

## 我想贡献

> ### 法律声明
> 在向本项目贡献时，您必须同意您拥有所贡献内容 100% 的版权，您拥有必要的内容权利，并且您贡献的内容可以在项目许可证下提供。

### 报告 Bug

#### 提交 Bug 报告之前

一个好的 Bug 报告不应该让其他人需要追着您要更多信息。因此，我们要求您仔细调查、收集信息并在报告中详细描述问题。请提前完成以下步骤，以帮助我们尽快修复潜在的 Bug：

- 确保您使用的是最新版本
- 确认您的问题确实是一个 Bug，而不是您自己的配置问题（例如使用不兼容的环境组件/版本）
- 在 [Bug 跟踪器](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues?q=label%3Abug)中查看是否已有相同的 Bug 报告
- 在互联网（包括 Stack Overflow）上搜索，看是否有其他用户讨论过此问题
- 收集关于 Bug 的信息：
  - 堆栈跟踪（Traceback）
  - 操作系统、平台和版本（Windows、Linux、macOS、x86、ARM）
  - Python 版本、FastMCP 版本、依赖包版本
  - 您的输入和实际输出
  - 能否稳定重现该问题？能否在旧版本中重现？

#### 如何提交一个好的 Bug 报告？

> 切勿在 issue 跟踪器或其他公共场所报告安全相关的问题、漏洞或包含敏感信息的 Bug。相反，敏感 Bug 必须通过邮件发送到项目维护者。

我们使用 GitHub Issues 来跟踪 Bug 和错误。如果您遇到项目问题：

- 创建一个 [Issue](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues/new)
- 解释您期望的行为和实际行为
- 请提供尽可能多的上下文，并描述**重现步骤**，以便其他人可以跟随这些步骤在他们自己的环境中重现问题。这通常包括您的代码。优秀的 Bug 报告应该隔离问题并创建简化的测试用例
- 提供您在上一节中收集的信息

提交后：

- 项目团队将相应地标记 issue
- 团队成员将尝试使用您提供的步骤重现问题。如果没有重现步骤或没有明显的方法来重现问题，团队会要求您提供这些步骤并将 issue 标记为 `needs-repro`
- 如果团队能够重现问题，它将被标记为 `needs-fix`，以及可能的其他标签（如 `critical`），然后等待[实现](#首次代码贡献)

### 提出功能建议

本节指导您为 ack-mcp-server 提交功能建议，**包括全新功能和对现有功能的改进**。

#### 提交功能建议之前

- 确保您使用的是最新版本
- 仔细阅读[文档](README.md)和[设计文档](DESIGN.md)，确认该功能尚未涵盖
- 执行[搜索](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues)以查看该功能建议是否已被提出。如果已经存在，请在现有 issue 中添加评论，而不是创建新的
- 确定您的想法是否符合项目的范围和目标。您需要向项目开发者充分说明此功能的优点。请记住，我们希望功能对大多数用户有用，而不仅仅是一小部分用户

#### 如何提交一个好的功能建议？

功能建议通过 [GitHub Issues](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues) 跟踪：

- 使用**清晰和描述性的标题**来标识建议
- 尽可能详细地提供**建议功能的分步描述**
- **描述当前行为**并**解释您期望看到的行为**以及原因
- 您可以**包含截图和动画 GIF** 来帮助演示步骤或指出建议相关的部分
- **解释为什么此增强功能对大多数用户有用**
- 列出您参考的其他项目或实现

### 首次代码贡献

不确定从哪里开始贡献？您可以从这些 `good-first-issue` 和 `help-wanted` issues 开始：

- [Good First Issues](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) - 适合初学者的问题
- [Help Wanted Issues](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) - 需要社区帮助的问题

### 改进文档

文档改进总是受欢迎的！您可以：

- 修复文档中的拼写错误或语法错误
- 改进现有文档的清晰度
- 为缺少文档的功能添加文档
- 添加更多示例和用例
- 翻译文档到其他语言

## 开发指南

### 开发环境设置

#### 前置要求

- Python 3.12+
- Git
- uv 或 pip（推荐使用 uv）
- Docker（可选，用于容器化测试）
- kubectl（可选，用于 Kubernetes 功能测试）

#### 设置步骤

1. **Fork 并克隆仓库**

```bash
git clone https://github.com/YOUR_USERNAME/alibabacloud-ack-mcp-server.git
cd alibabacloud-ack-mcp-server
```

2. **创建虚拟环境并安装依赖**

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

3. **配置环境变量**

```bash
cp .env.example .env
# 编辑 .env 文件，填写您的阿里云 AccessKey 信息
```

4. **运行测试**

```bash
# 运行所有测试
make test

# 运行特定测试
pytest src/tests/test_ack_cluster_handler.py

# 运行测试并生成覆盖率报告
make test-cov
```

5. **运行服务器**

```bash
# stdio 模式
make run

# HTTP 模式
make run-http

# SSE 模式
make run-sse
```

### 项目结构

请参考 [DESIGN.md](DESIGN.md) 了解详细的项目结构和架构设计。关键目录：

```
src/
├── main_server.py           # 主服务器入口
├── runtime_provider.py      # 运行时提供者
├── config.py               # 配置管理
├── models.py               # 数据模型
├── *_handler.py            # 功能处理器
├── interfaces/             # 接口定义
├── tests/                  # 测试文件
└── prometheus_metrics_guidance/  # Prometheus 指标指导
```

### 编码规范

我们使用以下工具确保代码质量：

#### 代码格式化

```bash
# 使用 ruff 格式化代码
ruff format src/

# 或使用 make 命令
make format
```

#### 代码检查

```bash
# 运行 ruff 代码检查
ruff check src/

# 运行 mypy 类型检查
mypy src/

# 或使用 make 命令
make lint
```

#### 编码标准

1. **Python 版本**: 使用 Python 3.12+
2. **行长度**: 最大 99 字符
3. **引号**: 使用双引号
4. **导入顺序**: 使用 isort（通过 ruff 集成）
5. **类型注解**: 所有函数必须包含类型注解
6. **文档字符串**: 所有公共函数、类和模块必须包含 docstring

#### 命名约定

- **文件名**: `snake_case.py`
- **类名**: `PascalCase`
- **函数名**: `snake_case`
- **常量**: `UPPER_CASE_WITH_UNDERSCORES`
- **私有成员**: `_leading_underscore`

#### Handler 开发规范

创建新的 Handler 时，请遵循以下模式：

```python
from fastmcp import FastMCP, Context
from pydantic import Field
from typing import Dict, Any, Optional

class NewFeatureHandler:
    """新功能处理器的描述。"""
    
    def __init__(self, mcp: FastMCP, config: Optional[Dict[str, Any]] = None):
        """初始化 Handler 并注册工具。"""
        self.mcp = mcp
        self.config = config or {}
        self._register_tools()
    
    def _register_tools(self):
        """注册 MCP 工具。"""
        self.mcp.tool(name="tool-name")(self.tool_function)
    
    async def tool_function(
        self,
        ctx: Context = None,
        param: str = Field(..., description="参数描述"),
    ) -> str:
        """工具函数的详细文档。
        
        ## 使用要求
        - 列出使用要求
        
        ## 参数
        - param: 参数说明
        
        ## 返回值
        返回值说明
        """
        try:
            # 从上下文获取提供者
            providers = ctx.request_context.lifespan_context.get("providers", {})
            
            # 实现逻辑
            # ...
            
            return result
        except Exception as e:
            logger.error(f"错误信息: {str(e)}")
            await ctx.error(f"错误信息: {str(e)}")
            raise
```

### 测试规范

#### 测试要求

1. **测试覆盖率**: 所有新代码必须达到 100% 测试覆盖率
2. **测试类型**: 
   - 单元测试：测试单个函数
   - 集成测试：测试 Handler 与服务的集成
3. **测试框架**: 使用 pytest
4. **异步测试**: 使用 pytest-asyncio

#### 测试文件组织

```
src/tests/
├── test_ack_cluster_handler.py
├── test_kubectl_handler.py
├── test_runtime_provider.py
└── verify_all_test_coverage.py
```

#### 测试示例

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_tool_function():
    """测试工具函数的正常情况。"""
    # Arrange
    mock_mcp = Mock()
    handler = NewFeatureHandler(mock_mcp, {})
    
    mock_ctx = Mock()
    mock_ctx.request_context.lifespan_context = {
        "providers": {"client_factory": Mock()}
    }
    
    # Act
    result = await handler.tool_function(mock_ctx, param="test")
    
    # Assert
    assert result is not None
    assert "expected" in result

@pytest.mark.asyncio
async def test_tool_function_error():
    """测试工具函数的错误处理。"""
    # 测试异常情况
    pass
```

#### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest src/tests/test_ack_cluster_handler.py

# 运行特定测试函数
pytest src/tests/test_ack_cluster_handler.py::test_list_clusters

# 生成覆盖率报告
pytest --cov=src --cov-report=html

# 验证测试覆盖率
python src/tests/verify_all_test_coverage.py
```

### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

#### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type 类型

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更改
- `style`: 代码格式（不影响代码运行的变动）
- `refactor`: 重构（既不是新增功能，也不是修改 Bug 的代码变动）
- `perf`: 性能优化
- `test`: 添加或修改测试
- `chore`: 构建过程或辅助工具的变动
- `ci`: CI 配置文件和脚本的变动

#### Scope 范围

- `cluster`: ACK 集群管理
- `kubectl`: Kubernetes 操作
- `prometheus`: Prometheus 监控
- `audit`: 审计日志
- `diagnose`: 诊断功能
- `inspect`: 巡检功能
- `runtime`: 运行时提供者
- `deps`: 依赖管理

#### 示例

```
feat(prometheus): 添加自然语言转 PromQL 功能

- 实现 NL2PromQL 转换逻辑
- 添加 Prometheus 指标指导知识库
- 增加相关单元测试

Closes #123
```

```
fix(kubectl): 修复获取 Pod 日志时的编码问题

当 Pod 日志包含非 UTF-8 字符时会导致解码错误。
现在使用 errors='replace' 参数来处理无效字符。

Fixes #456
```

## Pull Request 流程

### 提交 PR 之前

1. **确保代码通过所有检查**

```bash
# 格式化代码
make format

# 运行代码检查
make lint

# 运行测试
make test

# 验证测试覆盖率
python src/tests/verify_all_test_coverage.py
```

2. **更新文档**
   - 如果添加了新功能，更新 README.md
   - 如果更改了架构，更新 DESIGN.md
   - 添加或更新相关的 docstring

3. **添加测试**
   - 为新功能添加测试
   - 确保测试覆盖率达到 100%

### 提交 PR

1. **创建特性分支**

```bash
git checkout -b feature/my-new-feature
# 或
git checkout -b fix/bug-description
```

2. **提交更改**

```bash
git add .
git commit -m "feat(scope): 描述您的更改"
```

3. **推送到您的 Fork**

```bash
git push origin feature/my-new-feature
```

4. **创建 Pull Request**
   - 访问 GitHub 仓库
   - 点击 "New Pull Request"
   - 选择您的分支
   - 填写 PR 模板

### PR 模板

```markdown
## 描述
简要描述这个 PR 的目的和更改内容。

## 更改类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 重构
- [ ] 文档更新
- [ ] 性能优化
- [ ] 其他（请说明）

## 相关 Issue
Closes #(issue number)

## 测试
描述您如何测试这些更改：
- [ ] 添加了新的单元测试
- [ ] 所有现有测试通过
- [ ] 手动测试场景

## 检查清单
- [ ] 代码遵循项目的编码规范
- [ ] 已运行代码格式化工具
- [ ] 已添加/更新相关文档
- [ ] 已添加/更新测试
- [ ] 测试覆盖率达到 100%
- [ ] 提交信息遵循规范
```

### PR 审查流程

1. **自动检查**: CI/CD 会自动运行测试和代码检查
2. **代码审查**: 至少一名维护者会审查您的代码
3. **反馈处理**: 根据反馈进行必要的修改
4. **合并**: 审查通过后，维护者会合并您的 PR

## 加入项目团队

如果您对成为项目维护者感兴趣，请：

1. 持续贡献高质量的代码
2. 积极参与 issue 讨论和 PR 审查
3. 帮助其他贡献者
4. 联系现有维护者表达您的兴趣

## 开发资源

### 重要文档

- [README.md](README.md) - 项目概述和使用指南
- [DESIGN.md](DESIGN.md) - 架构设计和开发指南
- [Makefile](Makefile) - 常用开发命令

### 有用的命令

```bash
# 代码格式化
make format

# 代码检查
make lint

# 运行测试
make test

# 测试覆盖率
make test-cov

# 构建 Docker 镜像
make docker-build-amd64

# 运行服务器（不同模式）
make run          # stdio
make run-http     # HTTP
make run-sse      # SSE

# 清理构建文件
make clean
```

### 获取帮助

如果您在贡献过程中遇到问题：

1. 查看[文档](README.md)和[设计文档](DESIGN.md)
2. 搜索现有的 [Issues](https://github.com/aliyun/alibabacloud-ack-mcp-server/issues)
3. 在 [Discussions](https://github.com/aliyun/alibabacloud-ack-mcp-server/discussions) 中提问
4. 创建新的 Issue 描述您的问题

## 致谢

感谢所有为本项目做出贡献的人！您的努力使这个项目变得更好。

本指南基于 [contributing.md](https://contributing.md/example/) 模板创建。