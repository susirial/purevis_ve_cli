# PureVis Studio Agent - AI短剧创作总控智能体

## 1. 项目简介 (Introduction)

**PureVis Studio Agent** 是一个基于 `VeADK` 构建的多模态智能体（Multi-Agent）流水线系统，专门用于自动化的 **AI 短剧/视频内容创作**。

该系统通过一个**总控智能体 (Orchestrator)** 协调多个专业领域的子智能体（Sub-Agents），实现了从**剧本大纲、角色/场景设定、图片分镜设计**到**图像与视频生成**的全链路闭环。不仅如此，系统具备本地化的状态管理机制，可以长效持久化项目资产，并在流式交互中通过内置 CLI 命令管理上下文 Tokens。

## 2. 环境要求与安装 (Installation & Setup)

### 2.1 环境依赖
- Python 3.10+

### 2.2 创建虚拟环境并安装依赖
强烈建议使用虚拟环境（如 `venv` 或 `conda`）来隔离项目依赖。以下提供使用 `venv` 的完整步骤：

```bash
# 1. 在项目根目录创建名为 .venv 的虚拟环境
python3 -m venv .venv

# 2. 激活虚拟环境
# (macOS/Linux)
source .venv/bin/activate
# (Windows)
# .venv\Scripts\activate

# 3. 安装项目依赖
pip install veadk-python google-genai python-dotenv rich tiktoken pillow requests
```

*(注：如果项目后续提供 `requirements.txt`，也可直接 `pip install -r requirements.txt`)*

### 2.3 配置环境变量 (.env)
项目依赖一些外部 API 密钥才能正常运行。根目录提供了一个配置文件模板 `.example_env`。

```bash
# 1. 复制模板并重命名为 .env
cp .example_env .env
```

# 2. 编辑 .env 文件，填入您的实际 API Keys
使用文本编辑器（如 `vim .env` 或直接在 IDE 中打开）修改以下配置：
- `MODEL_AGENT_NAME` / `MODEL_AGENT_API_KEY`: 必填。火山引擎/豆包大模型配置（用于文本生成、调度及降级方案）。
- `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`: 选填。火山引擎内置工具使用的 AK/SK（暂未用到）。
- `PUREVIS_API_KEY`: [可选] PureVis 高级工作流 API Key，如果不配置，系统默认回退使用火山引擎（Seed 系列）进行生图/视频。
- `MEDIA_PROVIDER`: [可选] 指定底层媒体生成提供商 (`auto` | `purevis` | `volcengine_ark`， 使用火山引擎选择 volcengine_ark)。

全部使用火山引擎的配置如下：
# 火山方舟大模型配置
MODEL_AGENT_NAME=doubao-seed-2-0-pro-260215 （建议不改，默认豆包2.0）
MODEL_AGENT_API_KEY= 你的火山引擎方舟的API KEY （不是火山引擎AK SK）

# 火山引擎内置工具(如 web_search) 需要的 AK 和 SK （目前还没用到，不需要）
#VOLCENGINE_ACCESS_KEY=your_ak_here
#VOLCENGINE_SECRET_KEY=your_sk_here

# 日志等级 
LOGGING_LEVEL=ERROR

# PureVis API Key （可选）
PUREVIS_API_KEY=

# 默认 volcengine_ark: 如果有 PUREVIS_API_KEY 则选 purevis
MEDIA_PROVIDER=volcengine_ark

## 3. 启动与使用 (Usage & CLI Commands)

### 3.1 启动系统
在终端运行主入口文件，即可进入交互式 CLI：

```bash
python purevis_agent.py
```

系统将展示带有流式输出和打字机特效的终端界面，您可以通过自然语言与总控智能体交互，发布您的创作需求。

### 3.2 内置 CLI 快捷指令
在对话框中，系统内置了一系列以 `/` 开头的快捷管理指令，用于会话控制：

- `/help` - 查看所有可用指令列表及说明。
- `/history` - 在终端以 Markdown 格式打印当前会话的上下文历史。
- `/clear` - 彻底清空当前会话的记忆上下文（重置模型记忆）。
- `/compact` - 自动总结并压缩当前历史对话，释放 Token 空间（防止超长对话导致 OOM 或 Token 限制）。
- `/export` - 将当前会话历史导出为 Markdown 文件并保存到本地 `output/` 目录。
- `/import <filepath>` - 从本地文件读取上下文并注入到当前对话历史中。
- `/delete` - 清理本地 `output` 目录下的所有生成内容（执行后需输入 `/delete confirm` 确认）。
- `exit` 或 `quit` - 安全退出程序。

## 4. 核心智能体团队 (Core Sub-Agents)

本系统采用 Multi-Agent 架构，各司其职：

1. 🧠 **Orchestrator (总控)**：对接用户需求，调度分配任务，并向用户汇报整体进度。
2. ✍️ **Director (编剧/导演)**：负责前期的题材策划、角色文案设定、场景规划以及撰写详细剧本。
3. 🎬 **Visual Director (视觉导演)**：故事板艺术家。将剧本或核心角色图转化为**连贯的关键帧序列**，输出包含严格构图、用光、运镜规范的“穷尽式 JSON”提示词。
4. 🎨 **Image Gen (生图智能体)**：负责调用底层接口生成角色参考图、多视图、姿势图及最终的分镜网格图。
5. 🎥 **Video Gen (视频智能体)**：负责将生成的关键帧图片转化为动态短视频片段。
6. 🧐 **Vision Analyzer (视觉分析师)**：质量控制。审视生成的视觉资产，把控审美，确保与剧本、光影及逻辑一致。

## 5. 六大制作阶段工作流 (Workflow)

您可以随时向总控询问当前阶段，或者自然语言引导其进入下一步。

### 阶段 1：题材策划与建组
**目标**：确定短剧类型、剧情大纲、世界观，在系统建立项目档案。
> 🗣️ *"我想创建一个新的短剧项目《赛博朋克2077》，帮我构思大纲。"*

### 阶段 2：角色/场景设定
**目标**：设计主角/核心场景详细文案，生成参考图，录入“主体库”。
> 🗣️ *"帮我设计女主角，20岁赛博黑客，生成参考图存入主体库。"*

### 阶段 3：剧本创作
**目标**：撰写具体的单集剧本。
> 🗣️ *"新建第一集(ep01)，并根据大纲撰写剧本。"*

### 阶段 4：图片分镜设计
**目标**：将剧本片段转化为连贯的电影级短镜头序列（JSON 提示词）。
> 🗣️ *"请视觉导演介入，根据第一集剧本和主角参考图，设计10个关键帧的分镜。"*

### 阶段 5：关键帧制作
**目标**：根据分镜设计批量生成实际的图片资产，并可由视觉分析师校验。
> 🗣️ *"让生图智能体根据刚才的分镜提示词生成关键帧网格图，并让分析师检查光影。"*

### 阶段 6：视频合成
**目标**：将关键帧转化为动态视频。
> 🗣️ *"让视频智能体把第一集的所有关键帧生成 5 秒的动态视频。"*

## 6. 状态管理与资产持久化 (State & Assets)

系统会自动在根目录下创建 `output/` 文件夹用于持久化保存生成的所有文本、图片、视频和项目状态。即使您关闭终端，下次启动时只需告诉总控 *"继续《某某项目》的工作"*，它即可自动读取 `state.json` 恢复进度。

目录结构示例：
```text
output/projects/<项目名>/
├── state.json                 # 项目整体进度与多集配置记录
├── subjects/                  # 核心主体库
│   ├── <角色名>/              # 该角色的参考图、角色设计 Markdown 等
│   └── <场景名>/              # 该场景的参考图、场景设计 Markdown 等
└── episodes/<剧集ID>/         # 单集生成资产
    ├── scripts/               # 剧本文稿
    ├── storyboard/            # 分镜设定 (JSON/Markdown)
    ├── keyframes/             # 实际生成的关键帧图片
    └── videos/                # 最终生成的短剧视频片段
```

## 7. 基础生图与生视频能力展示 (Basic Image & Video Generation Capabilities)

PureVis Studio Agent 底层集成了强大的多模态生成模型，支持以下基础生成能力。您可以直接通过自然语言指令调度生图和生视频智能体完成这些任务：

### 7.1 文生图 (Text-to-Image)
通过自然语言描述，智能体能够从零开始生成高质量的图像资产，用于角色设定、场景概念图等。
**示例：** 山上有大象
![文生图 - 山上有大象](demo/山上有大象.jpg)

### 7.2 图生图 (Image-to-Image)
基于已有图像和提示词，智能体可以进行风格迁移、细节修改或角色替换等图生图操作。
**示例：** 大象上的美女
![图生图 - 大象上的美女](demo/大象上的美女.jpg)

### 7.3 图生视频 (Image-to-Video)
智能体可以将静态图像转化为动态视频，支持基于单张图片生成动态效果，或提供首尾两帧进行平滑的过渡视频生成。
**示例：** 山上大象过渡到大象背美女
<video src="demo/山上大象过渡到大象背美女.mp4" width="640" controls></video>
*(注：请在支持 HTML5 的 Markdown 阅读器中查看视频，或直接使用播放器打开 `demo/山上大象过渡到大象背美女.mp4`)*

