# PureVis Studio Agent

[English](README.md) | [简体中文](README_zh.md)

PureVis Studio Agent 是一个面向 AI 短剧与视频生产的多模态、多智能体 CLI。它把自然语言需求编排成一条可执行的创作流水线，覆盖题材策划、角色与场景设计、剧本撰写、分镜规划、关键帧生成、视频合成、视觉审核以及本地资产落盘。

项目基于 `VeADK` 构建，但定位并不是单一模型的封装，而是一个创作工作流编排层。文本策划、图片生成、视频生成和视觉分析彼此解耦，因此你可以在不改变上层交互方式的前提下，自由组合 `PureVis`、`Volcengine Ark`、`LibTV`、`Z.ai` 等不同提供方能力。

## 核心亮点

- 用自然语言驱动完整的创作链路，从概念到成片。
- 通过专业子智能体拆分编排、写作、分镜、出图、生视频和视觉质检职责。
- 使用渐进式技能系统，按需加载领域知识，避免首轮上下文过重。
- 在 `output/projects/` 下维护本地项目状态、风格配置和可复用资产。
- 提供流式 CLI 体验，包括工具调用面板、历史导入导出和自动上下文压缩。
- 将文本模型与媒体生成后端解耦，便于按成本、质量和稳定性切换 provider。

## 模型与提供方生态

<p align="center">
  <img src="demo/volcengine-color.png" height="56" alt="Volcengine" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="demo/libtv-logo.svg" height="38" alt="LibTV" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://z-cdn.chatglm.cn/z-ai/static/logo.svg" height="42" alt="Z.ai" />
</p>

- `Volcengine Ark`：推荐的生产级默认底座，可承接文本、图片和视频能力。
- `LibTV`：可选媒体后端，支持显式生图 / 生视频模型路由。
- `PureVis`：可选的高级媒体工作流提供方。
- `Z.ai`：可选的 OpenAI 兼容文本模型来源，适合替换 Agent 或文本工具侧推理。

## 视觉展示

下面的示例说明 PureVis 产出的不是一次性图片，而是可直接进入后续生产的可复用资产，例如角色参考图、多视图和封面 Key Art。

### 封面探索

<p align="center">
  <img src="demo/sky_verse_cover_epic.jpg" width="32%" alt="Key Art - Epic Confrontation" />
  <img src="demo/sky_verse_cover_duet.jpg" width="32%" alt="Key Art - Duet" />
  <img src="demo/sky_verse_cover_ruins.jpg" width="32%" alt="Key Art - Ruins Narrative" />
</p>

### 角色参考图

<p align="center">
  <img src="demo/armed_diva_xingyao_ref.jpg" width="48%" alt="Character Reference - Xingyao" />
  <img src="demo/armed_diva_shuangren_ref.jpg" width="48%" alt="Character Reference - Shuangren" />
</p>

### 多视图一致性素材

<p align="center">
  <img src="demo/armed_diva_xingyao_multiview.jpg" width="48%" alt="Multi-view Sheet - Xingyao" />
  <img src="demo/armed_diva_shuangren_multiview.jpg" width="48%" alt="Multi-view Sheet - Shuangren" />
</p>

### 基础生图与生视频示例

**文生图**

![文生图示例](demo/山上有大象.jpg)

**图生图**

![图生图示例](demo/大象上的美女.jpg)

**图生视频**

<table>
  <tr>
    <td width="220" valign="top">
      <a href="https://github.com/susirial/purevis_ve_cli/blob/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">
        <img src="demo/大象上的美女.jpg" width="220" alt="图生视频封面" />
      </a>
    </td>
    <td valign="top">
      <strong>内容：</strong>山上大象过渡到骑象少女<br/>
      <strong>形式：</strong>GitHub 友好的视频预览卡片<br/>
      <strong>链接：</strong>
      <a href="https://github.com/susirial/purevis_ve_cli/raw/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">直接打开 MP4</a>
      ·
      <a href="https://github.com/susirial/purevis_ve_cli/blob/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">GitHub 页面</a>
    </td>
  </tr>
</table>

## 架构概览

入口文件是 `purevis_agent.py`，运行机制可以概括为六层：

1. **CLI 交互层**：用 `rich` 渲染欢迎页、状态动画、流式文本和工具调用面板。
2. **会话执行层**：通过统一的 `Runner` 维护 `orchestrator_agent` 与会话状态。
3. **命令解析层**：把 `/...` 命令交给本地管理逻辑，把普通请求交给总控智能体。
4. **多智能体调度层**：将任务分派给 `director`、`visual_director`、`image_gen`、`video_gen`、`vision_analyzer`。
5. **技能层**：按需加载技能元数据、指令和参考文档，降低首轮 prompt 成本。
6. **工具与状态层**：负责项目状态、风格配置、文件持久化、媒体生成和任务轮询。

## 智能体分工

| 智能体 | 职责 |
| --- | --- |
| `orchestrator` | 理解用户意图，判断当前制作阶段，并路由任务。 |
| `director` | 负责策划、剧本、角色 / 场景 / 道具设计，以及提示词前处理。 |
| `visual_director` | 将剧本或参考图扩展为电影级关键帧序列和结构化分镜 JSON。 |
| `image_gen` | 生成参考图、关键帧、多视图、表情表和姿势表。 |
| `video_gen` | 将关键帧或参考图转成短视频片段。 |
| `vision_analyzer` | 对视觉资产做审美、一致性和修改建议审核。 |

## 端到端工作流

默认生产链路分为六个阶段：

1. **项目策划**：确定题材、世界观和项目基础配置。
2. **角色与场景设定**：生成设定文案和参考素材。
3. **剧本创作**：创建如 `ep01` 这样的剧集并生成脚本。
4. **分镜设计**：把剧本或参考图转成关键帧方案和结构化 JSON。
5. **关键帧制作**：批量出图并完成视觉审核。
6. **视频合成**：基于审批后的素材生成动态片段。

示例提示词：

```text
我想创建一个新的短剧项目《赛博朋克2077》，帮我构思大纲。
```

```text
帮我设计女主角，20 岁赛博黑客，生成参考图并存入主体库。
```

```text
新建第一集 ep01，并根据大纲撰写剧本。
```

```text
请视觉导演根据剧本和主角参考图设计 10 个关键帧分镜。
```

```text
让生图智能体根据分镜提示词生成关键帧网格图，并请分析师检查光影和一致性。
```

```text
让视频智能体把第一集通过审核的关键帧生成 5 秒动态视频。
```

## 安装

### 环境要求

- `Python 3.10+`
- 至少接入一个可用文本模型和一个可用媒体 provider
- 强烈建议使用虚拟环境

### 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows：

```bash
.venv\Scripts\activate
```

### 安装依赖

```bash
pip install veadk-python google-genai python-dotenv rich tiktoken pillow requests
```

### 初始化环境变量

先复制模板：

```bash
cp .example_env .env
```

最小推荐配置如下：

```bash
MODEL_AGENT_PROVIDER=openai
MODEL_AGENT_NAME=doubao-seed-2-0-pro-260215
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
MODEL_AGENT_API_KEY=<your_text_model_key>

MODEL_TOOL_VISION_ANALYZER_PROVIDER=openai
MODEL_TOOL_VISION_ANALYZER_NAME=doubao-seed-2-0-pro-260215
MODEL_TOOL_VISION_ANALYZER_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
MODEL_TOOL_VISION_ANALYZER_API_KEY=<your_vision_model_key>

VOLCENGINE_ARK_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
VOLCENGINE_ARK_API_KEY=<your_media_key>

LOGGING_LEVEL=ERROR
LITELLM_LOG=CRITICAL
MEDIA_PROVIDER=volcengine_ark
```

推荐实践：

- 不要把真实密钥提交到仓库。
- 使用 `MODEL_AGENT_*` 管理编排与写作模型，把媒体密钥单独治理。
- 如果图片和视频需要走不同后端，优先使用 `MEDIA_IMAGE_PROVIDER` 和 `MEDIA_VIDEO_PROVIDER`。
- 只有在某个智能体确实需要特殊模型时，再使用 `MODEL_<AGENT_NAME>_*` 覆盖。

### 启动 CLI

```bash
python purevis_agent.py
```

CLI 会在导入 `veadk` 前先加载 `.env`，然后初始化运行器并进入支持流式输出的交互循环。

## 核心能力

| 能力 | 作用 | 典型输出 |
| --- | --- | --- |
| 多智能体编排 | 按制作阶段自动路由到专业智能体 | 工具调用链、中间结果、最终回复 |
| 项目状态管理 | 创建项目目录，追踪剧集、主体、配置和进度 | `state.json`、目录结构、状态摘要 |
| 结构化风格治理 | 管理风格家族、子类、目标范围和版本历史 | 风格快照与复用约束 |
| 角色 / 场景 / 道具设计 | 生成后续可复用的设定文本和提示词 | 设定文档、提示词、参考说明 |
| 分镜预处理 | 将剧本转为结构化视觉段落 | 时间线分段和分镜基础数据 |
| Exhaustive JSON 分镜 | 从剧本或参考图生成结构化关键帧方案 | 逐帧 JSON 和分镜摘要 |
| 图片生成 | 支持文生图、图生图、关键帧和参考图 | 任务 ID、图片 URL、本地文件 |
| 一致性辅助资产 | 生成多视图、表情表、姿势表 | 可复用的角色一致性素材 |
| 图生视频 | 将 1 到 2 张静态图转成动态片段 | 任务 ID、视频 URL、本地视频 |
| 视觉质检 | 审核审美、光影、一致性和返工建议 | 分析报告和通过 / 打回建议 |
| 会话历史管理 | 导出、导入、清空和压缩长会话 | Markdown 历史和摘要状态 |
| Provider 路由 | 通过配置切换底层媒体后端 | 统一工具接口和稳定工作流 |

## CLI 命令

CLI 支持两类入口：

- 以 `/` 开头的本地管理命令
- 交给 `orchestrator` 处理的自然语言创作请求

常用命令如下：

| 命令 | 说明 |
| --- | --- |
| `/help` | 查看本地 CLI 帮助 |
| `/history` | 以 Markdown 打印当前会话历史 |
| `/clear` | 重置当前会话 |
| `/compact` | 压缩长对话上下文 |
| `/export` | 导出当前会话到 `output/chat_history_<timestamp>.md` |
| `/import <filepath>` | 导入已保存的历史摘要 |
| `/delete` | 预览 `output/` 下可删除内容 |
| `/delete confirm` | 二次确认后删除 `output/` 顶层内容 |
| `/style families` | 查看风格家族列表 |
| `/style subtypes <family>` | 查看某个家族下的子类 |
| `/style show <family> <subtype>` | 查看风格预设详情 |
| `/style current <project>` | 查看项目当前风格配置 |
| `/style versions <project>` | 查看风格变更历史 |
| `/style apply <project> <target> <family> <subtype>` | 给 `image`、`video` 或 `keyframe` 应用风格 |
| `/style delete <project> [target]` | 删除风格配置 |
| `exit` / `quit` | 安全退出 |

## 仓库结构

```text
agents/                  # 智能体定义
core/                    # 模型配置、状态和风格管理
docs/                    # 技能架构与排障文档
skills/                  # 渐进式披露技能与参考文档
tools/                   # CLI、状态、媒体、文件与路由工具
demo/                    # README 使用的演示素材
output/                  # 运行时生成的项目、资产和历史
purevis_agent.py         # CLI 入口
.example_env             # 环境变量模板
```

典型项目输出目录：

```text
output/projects/<项目名>/
├── state.json
├── subjects/
│   ├── <主体名>/
│   └── <场景名>/
└── episodes/<剧集ID>/
    ├── scripts/
    ├── storyboard/
    ├── keyframes/
    └── videos/
```

## 媒体路由逻辑

Provider 选择顺序如下：

1. 如果设置了 `MEDIA_IMAGE_PROVIDER` 或 `MEDIA_VIDEO_PROVIDER`，优先使用能力级 provider。
2. 否则回退到 `MEDIA_PROVIDER`。
3. 如果 `MEDIA_PROVIDER=auto`，则优先 `PUREVIS_API_KEY`，再回退到 `LIBTV_ACCESS_KEY`，最后回退到 `VOLCENGINE_ARK_API_KEY`。
4. 如果调用中显式指定了 `model`，则优先尊重该模型。
5. 如果默认模型与 provider 不兼容，系统会直接报配置错误，不会静默切换。

常用 LibTV 模型：

- 生图：`lib_nano_2`、`lib_nano_pro`
- 生视频：`seedance_2_0`、`seedance_2_0_fast`、`kling_o3`

## 会话安全与恢复

- CLI 启动时会尝试创建或恢复会话；如果底层 API 表现不同，会通过一次轻量 `hello` 调用兜底初始化。
- 当上下文估算超过 `250000` tokens 时，系统会自动压缩历史。
- 终端中的工具返回会被截断显示，以降低噪音但保留核心信息。
- `/delete` 采用两步式安全删除，只允许操作工作区内安全的 `output/` 目录。
- 导入与导出命令在修改会话状态前都会先校验文件访问权限。

## 完整案例

`demo/完整演示/` 目录记录了一条从自然语言需求到最终视频成片的完整链路。这里我把它展开成中文可独立阅读的案例说明，方便中文读者不跳转也能完整理解 PureVis 的工作方式。

### 案例目标

目标项目是一个 15 秒的“短剧创作智能体宣传片”。重点不是简单生成一段视频，而是用一条完整工作流把创意、风格、角色、分镜和视频资产串起来。

### 一句话到成片的操作顺序

```text
1. 提出一个 15 秒宣传片需求，说明电影感、层次感和镜头变化要求。
2. 查看系统给出的多套导演风格方案，并选择其中一种。
3. 让系统生成角色设定文案和官方参考图。
4. 复用已落盘的分镜文件，让视觉导演产出生视频提示词。
5. 确认参数。
6. 调用视频工具生成最终成片。
```

### 1. 先给出创作需求，而不是直接写底层提示词

用户起手并不是输入一句生视频 prompt，而是给出一个带制作要求的自然语言目标，例如 15 秒、电影感、前中后景分层、镜头有远近变化，并希望系统先给出多个风格版本。

<p align="center">
  <img src="demo/完整演示/1-1-用户输入需求.png" width="96%" alt="用户输入 15 秒宣传片需求" />
</p>

### 2. 由 Orchestrator 判断阶段并调度 Director

总控 `orchestrator` 会先理解当前任务是“前期策划 + 宣传脚本 + 分镜规划”，然后把任务转给 `director`。这样用户不需要自己判断该先找谁，也不需要手动拆解工作步骤。

<p align="center">
  <img src="demo/完整演示/1-2-orchestrator调用导演.png" width="96%" alt="Orchestrator 调度导演智能体" />
</p>

### 3. 先出宣传脚本，再给出多套风格方案与分镜结构

`director` 会先生成宣传脚本，再把脚本拆解成适合后续视觉处理的分镜结构。在这个案例里，系统给出了 5 套不同导演气质的版本，并自动保存到项目目录中，便于回看和筛选。

<p align="center">
  <img src="demo/完整演示/1-3-导演智能体给出文案设计.png" width="96%" alt="导演给出多套宣传方案" />
</p>

<p align="center">
  <img src="demo/完整演示/1-4-给出分镜方案.png" width="96%" alt="根据脚本拆解分镜" />
</p>

<p align="center">
  <img src="demo/完整演示/1-5-按照要求给出5中策划方案.png" width="62%" alt="系统保存多套脚本与分镜文件" />
</p>

最终案例选择的是“张艺谋国风美学风格”，这一路线强调：

- 朱砂红、赤金、墨黑的高对比色彩关系，
- 更强的景深层次和电影式构图，
- 丝绸、宣纸、水墨、宫殿等具象东方视觉符号，
- 更适合产品宣传片的庄重感与仪式感。

<p align="center">
  <img src="demo/完整演示/1-6-选择国风设计.png" width="70%" alt="选择张艺谋国风风格" />
</p>

### 4. 风格确定后，继续生成角色设定文案

风格一旦确定，用户就可以继续让 `director` 进入角色设计阶段。这里得到的不只是描述文字，还包括后续可直接用于出图的设定语言和提示词资产。

<p align="center">
  <img src="demo/完整演示/1-7-开始角色设计.png" width="96%" alt="开始角色设计" />
</p>

<p align="center">
  <img src="demo/完整演示/1-8-角色设计文案.png" width="54%" alt="角色设定文案已落盘" />
</p>

<p align="center">
  <img src="demo/完整演示/1-8-2-角色设计方案.png" width="96%" alt="角色设定与文生图提示词" />
</p>

### 5. 基于设定文案生成官方参考图

当角色设定已经存在时，用户只需要再说一句“生成该角色的官方参考图”。系统会把上一步的设计文案转成标准化参考图提示词，并路由到底层媒体 provider。在案例中，这一步通过 `LibTV` 的 `lib_nano_2` 执行。

<p align="center">
  <img src="demo/完整演示/1-9-用户要求给出角色参考图.png" width="62%" alt="用户要求生成官方参考图" />
</p>

<p align="center">
  <img src="demo/完整演示/1-10-调用工具生图.png" width="96%" alt="调用工具生成参考图" />
</p>

<p align="center">
  <img src="demo/完整演示/1-11-角色参考图.png" width="62%" alt="生成的角色官方参考图" />
</p>

这个结果不是简单的人像，而是面向生产的参考资产，包含服装结构、材质细节和一致性约束，更适合后续继续复用。

如果还想进一步降低角色漂移风险，可以继续生成多视图一致性素材：

<p align="center">
  <img src="demo/完整演示/1-12-角色多视图.png" width="96%" alt="角色多视图一致性素材" />
</p>

### 6. 分镜已有时，直接交给视觉导演生成生视频提示词

当分镜文件已经落盘后，用户不需要重新解释镜头内容，只要把已有分镜路径告诉系统，`visual_director` 就可以基于现有结构做视频生成前的复核与提示词转换。

<p align="center">
  <img src="demo/完整演示/1-13-视觉导演确认图生视频参数.png" width="96%" alt="视觉导演确认视频参数" />
</p>

视觉导演通常会返回一张“视频生成确认卡”，里面会把关键信息结构化展开，包括：

- 镜头语言，如近景、中景、大全景、推近、平移、俯拍等，
- 分段时间结构，如 `S01-S06`，
- 参考输入，如角色主体图或多视图图，
- 视频参数，如 `duration`、`aspect_ratio`、`model` 和音频模式，
- 可选的旁白或环境声建议。

<p align="center">
  <img src="demo/完整演示/1-13-2-视觉导演确认参数说明.png" width="96%" alt="视频生成确认卡" />
</p>

### 7. 参数确认后，生成最终宣传片

确认无误后，系统调用 `generate_video` 正式生成视频。此时前面已经落盘的角色参考资产、多视图素材和分镜文件，就会真正进入最终生产链路，而不是只停留在展示层。

<p align="center">
  <img src="demo/完整演示/1-14-调用工具生成视频.png" width="96%" alt="调用 generate_video 生成视频" />
</p>

成片预览：

<table>
  <tr>
    <td width="220" valign="top">
      <a href="demo/完整演示/1-15-生成的视频.mp4">
        <img src="demo/完整演示/1-11-角色参考图.png" width="220" alt="15 秒宣传片预览封面" />
      </a>
    </td>
    <td valign="top">
      <strong>项目：</strong>短剧创作智能体宣传片<br/>
      <strong>风格：</strong>张艺谋国风美学<br/>
      <strong>时长：</strong>15 秒<br/>
      <strong>价值：</strong>从一句需求直接推进到脚本、角色资产、生视频提示词和最终视频<br/>
      <strong>打开方式：</strong><a href="demo/完整演示/1-15-生成的视频.mp4">本地 MP4</a>
    </td>
  </tr>
</table>

### 这个案例说明了什么

这个案例说明，PureVis 的价值不只是“能接一个生图模型”或“能接一个生视频模型”，而是把整条创作过程做成了可复用、可追踪、可持续迭代的工程化流水线：

- 用户表达目标，而不是手动拆任务，
- `orchestrator` 自动判断阶段并调度合适的智能体，
- 中间产物会自动落盘并在后续步骤继续复用，
- 角色、分镜和视频生成保持前后连贯，
- 底层 provider 可以切换，但上层创作方式保持一致。

## 相关文档

- `docs/skills-architecture.md`：渐进式技能架构说明
- `docs/skills-changelog.md`：技能系统变更记录
- `docs/skills-troubleshooting.md`：技能系统排障指南
- `VEADK_DEV_GUIDE.md`：VeADK 集成说明

## FAQ

### 为什么一句自然语言会触发这么多工具？

因为请求会先经过 `orchestrator`，由它判断当前制作阶段，再把任务分配给合适的智能体与工具。

### 为什么 `/delete` 不会立刻删文件？

这是出于安全考虑。CLI 会先预览待删内容，只有执行 `/delete confirm` 才会真正删除。

### 为什么系统有时会自动压缩历史？

长链路创作会迅速抬高上下文成本。估算超过 `250000` tokens 后，系统会自动总结旧历史，以保证稳定性。

### 没有 `PUREVIS_API_KEY` 还能继续生图或生视频吗？

可以。路由层会根据当前可用凭证回退到 `LibTV` 或 `Volcengine Ark`。

### 当前有哪些已知限制？

- 入口程序使用固定的 `user_id` 和 `session_id`，更适合本地单用户连续创作。
- `video_gen` 目前最多支持两张输入图片。
- 剧集编号需要使用 `ep01`、`ep02` 这类格式。
- 结构化分镜和提示词工具需要足够明确的输入，过空或过弱的请求可能被拒绝。
