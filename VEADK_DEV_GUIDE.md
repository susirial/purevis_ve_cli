# 火山引擎 VeADK (Volcengine Agent Development Kit) 开发说明文档

VeADK 是由火山引擎推出的一套面向智能体开发的全流程框架，旨在为开发者提供面向智能体构建、云端部署、评测与优化的全流程云原生解决方案。相较于现有的智能体开发框架，VeADK 具备与火山引擎产品体系深度融合的优势，帮助开发者更高效地构建企业级 AI 智能体应用。

### 核心特性
- **多生态与模型兼容**：完全兼容 Google ADK，支持项目无缝迁移；兼容 LiteLLM 模型推理服务，支持各类主流大模型。
- **完善的记忆与知识库**：支持基于 MySQL/PostgreSQL 的短期记忆持久化，以及基于 Viking DB、Redis、云搜索服务 (OpenSearch) 的长期记忆和知识库接入。
- **丰富的工具生态集成**：内置 Web Search、VeSearch、图片/视频生成等多款工具，并支持 MCP 广场生态直连。
- **可观测性与评估能力**：集成 APMPlus、CozeLoop (扣子罗盘)、TLS (日志服务)，全面覆盖调用链路追踪、日志检索与在线评测。
- **云原生架构与企业级安全**：整合 VeFaaS 函数服务与 API 网关实现一站式部署；依托火山引擎身份鉴权体系，提供企业级安全防护（权限管控与凭据托管）。

## 1. 环境准备与安装

### 1.1 使用 pip 安装 (推荐)
通过 PyPI 直接安装 VeADK：
```bash
# 稳定版
pip install veadk-python
# 安装包含额外扩展的版本
pip install "veadk-python[extensions]"
# 预览版 (从 Github main 分支安装)
pip install git+https://github.com/volcengine/veadk-python.git@main
```
*注：如果你在本地使用的终端是 `zsh`，进行 `pip install` 时，**依赖包名称应当被双引号包裹起来**，例如 `pip install "veadk-python"`，否则会解析错误。*

### 1.2 从源码编译安装
官方推荐使用 `uv` 进行依赖管理并基于 Python 3.10+ 创建虚拟环境：
```bash
git clone https://github.com/volcengine/veadk-python.git
cd veadk-python
# 创建 python 3.10 及以上虚拟环境
uv venv --python 3.10
source .venv/bin/activate

# 以开发者模式安装
uv pip install -e .
```

### 1.3 使用 Docker 镜像
VeADK 提供了 Python 版的官方镜像仓库，便于容器化部署：
```text
veadk-cn-beijing.cr.volces.com/veadk/veadk-python:latest
veadk-cn-beijing.cr.volces.com/veadk/veadk-python:preview
```

## 2. 快速创建与配置

### 2.1 项目脚手架初始化
您可以通过 CLI 命令生成预制好的 Agent 项目模板：
```bash
veadk create
```
根据提示输入项目名称和火山方舟 API Key 后，将生成如下目录结构：
```text
your_project
├── __init__.py # 模块导出文件
├── .env        # 环境变量文件 (配置 API Key)
└── agent.py    # Agent 定义文件
```

### 2.2 配置文件方式 (`config.yaml`)
建议在项目根目录下创建一个 `config.yaml` 文件：
```yaml
model:
  agent:
    provider: openai
    name: doubao-seed-1-6-250615
    api_base: https://ark.cn-beijing.volces.com/api/v3/
    api_key: # <-- 填入你的火山引擎 ARK api key
```

### 2.3 环境变量方式
可以直接在代码中或 `.env` 中设置鉴权信息：
```python
import os

os.environ["MODEL_AGENT_NAME"] = "doubao-seed-1-6-251015"  # 火山方舟大模型名称
os.environ["MODEL_AGENT_API_KEY"] = "your_ark_api_key"     # 火山方舟 API KEY
os.environ["LOGGING_LEVEL"] = "ERROR"                      # 调整日志等级
```

## 3. Agent 构建与执行引擎 (Runner)

`Runner` 是 ADK Runtime 中的核心组件，负责协调 Agent、Tools、Callbacks 等共同响应用户输入，并完全兼容 Google ADK Runner 规范。

### 3.1 多租户数据隔离设计
为了满足企业级设计，VeADK 提供了多维度的数据隔离：
| 数据类别 | 隔离维度 |
| --- | --- |
| 短期记忆 | `app_name`, `user_id`, `session_id` |
| 长期记忆 | `app_name`, `user_id` |
| 知识库 | `app_name` |

### 3.2 基础运行示例
最简单的接口 `Runner.run` 用于直接处理并返回完整响应：
```python
import asyncio
from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

async def main():
    agent = Agent()
    short_term_memory = ShortTermMemory() # 短期记忆记录
    
    runner = Runner(
        agent=agent, 
        short_term_memory=short_term_memory, 
        app_name="veadk_app", 
        user_id="user_01"
    )
    
    response = await runner.run(
        messages="你好，我是一名 Agent 开发者。", 
        session_id="session_01"
    )
    print(response)

asyncio.run(main())
```

### 3.3 生产级异步流式运行
生产级别通常需要对执行过程中的各个 Event 进行精确控制，推荐使用 `runner.run_async` 接口：
```python
import asyncio
from veadk import Agent, Runner, RunConfig
from google.genai.types import Content, Part

async def run_production():
    agent = Agent()
    runner = Runner(agent=agent, app_name="production_app")
    
    user_message = Content(
        role="user",
        parts=[Part(text="请执行任务分析。")]
    )
    
    # 使用异步生成器处理 Agent 每个步骤产生的 Event
    async for event in runner.run_async(
        user_id="user_02",
        session_id="session_02",
        new_message=user_message,
        run_config=RunConfig(max_llm_calls=5),
    ):
        print("Event received:", event)

asyncio.run(run_production())
```

### 3.4 使用内置工具 (Builtin Tools)
例如使用火山引擎的网页搜索工具 `web_search`：
```python
import os
from veadk import Agent
from veadk.tools.builtin_tools.web_search import web_search

os.environ["VOLCENGINE_ACCESS_KEY"] = "your_ak"
os.environ["VOLCENGINE_SECRET_KEY"] = "your_sk"

# 初始化时挂载内置工具
agent = Agent(tools=[web_search])
```

## 4. 命令行工具 (CLI) 进阶
VeADK 提供了实用的命令行工具：
- **`veadk create`**：快速生成基础 Agent 项目模板。
- **`veadk web`**：启动一个基于 Gradio/Streamlit 风格的本地 Web UI 与 Agent 进行交互。支持配置服务：
  ```bash
  veadk web --host 0.0.0.0 --port 8000 --log_level DEBUG
  ```
- **`veadk deploy`**：一键将项目部署到火山引擎 VeFaaS (函数计算) 平台。
- **`veadk prompt`**：通过 PromptPilot 优化你的智能体系统提示词。

## 5. 更多参考
- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [VeADK GitHub 仓库](https://github.com/volcengine/veadk-python)
- [Jupyter 教程](https://github.com/volcengine/veadk-python/blob/main/veadk_tutorial.ipynb)



# 启动虚拟环境
source venv/bin/activate