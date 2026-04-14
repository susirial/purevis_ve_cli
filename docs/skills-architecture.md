# PureVis 渐进式披露技能架构文档

> 最后更新：2026-04-14 (v1.0.1 工具覆盖审计修复)

## 一、架构概述

本项目基于 VeADK 多智能体框架，采用 **渐进式披露（Progressive Disclosure）** 技能系统替代原有的"重指令 + 硬编码工具"架构。核心思想来自 [Anthropic Agent Skills 规范](https://agentskills.io/specification)：将领域知识从智能体 instruction 中抽离为独立的 Skill 文件，按需加载而非一次性注入。

### 设计理念

```
L1 元数据层（~20 tokens/skill）  ← 始终可见：name + description
        ↓ 意图匹配
L2 指令层（~200-400 tokens/skill） ← 按需加载：SKILL.md 正文
        ↓ 执行时读取
L3 资源层（按需）                ← 深度参考：references/ 下的详细文档
```

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                  orchestrator（总控）                     │
│  ~35 行核心指令 + 技能触发映射表                          │
│  21 个工具（18 核心 + 3 skill loader）                    │
├────────┬────────┬────────┬────────┬─────────────────────┤
│        │        │        │        │                     │
│  director  visual_  image_  video_  vision_             │
│  ~48 行    director  gen     gen     analyzer            │
│  10 工具   ~26 行   ~40 行  ~40 行  ~27 行               │
│            7 工具   20 工具  12 工具  8 工具              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                   skills/ 技能层                         │
│  9 个 Skill + 12 个 Reference 文档                       │
│  L1: ~189 tokens  L2: ~2611 tokens  L3: ~1694 tokens    │
└─────────────────────────────────────────────────────────┘
```

---

## 二、智能体清单与职责

### 2.1 orchestrator（总控智能体）

- **文件**：`agents/orchestrator.py`（80 行）
- **职责**：管理调度短剧生成全生命周期，将任务分配给子智能体
- **技能触发映射**：

| 任务类型 | 加载技能 |
|---------|---------|
| 项目创建/管理/阶段推进 | `load_skill("project-management")` |
| 风格选型/推荐/审美适配 | `load_skill("style-configuration")` |
| 角色创建/参考图 | `load_skill("character-design")` |
| 场景/道具设计/三视图 | `load_skill("scene-prop-design")` |
| 媒体后端/模型选择 | `load_skill("media-routing")` |
| 视频生成/参数确认 | `load_skill("video-generation")` |
| 审美评审/一致性检查 | `load_skill("vision-analysis")` |

- **注册工具**（21 个）：

| 类别 | 工具 |
|------|------|
| 项目状态 | `create_project_state`, `get_project_state`, `discover_project_subjects_state`, `update_project_settings_state`, `add_episode_state`, `list_all_projects_state`, `open_project_dashboard_state`, `delete_subject`, `delete_file` |
| 风格配置 | `list_style_families_state`, `list_style_subtypes_state`, `preview_style_preset_state`, `get_project_style_config_state`, `update_project_style_config_state`, `delete_project_style_config_state`, `list_project_style_versions_state`, `get_prompt_style_context_state` |
| 文件与媒体 | `list_directory`, `describe_media_capabilities`, `suggest_media_route` |
| 技能加载器 | `list_available_skills`, `load_skill`, `load_skill_reference` |

### 2.2 director（导演智能体）

- **文件**：`agents/director.py`（61 行）
- **职责**：前期策划、角色/场景/道具设定、剧本拆解、分镜设计
- **按需加载技能**：`character-design`、`scene-prop-design`
- **注册工具**（10 个）：`design_character`, `design_scene`, `design_prop`, `breakdown_storyboard`, `generate_keyframe_prompts`, `generate_video_prompts`, `save_text_file`, `read_text_file`, `load_skill`, `load_skill_reference`

### 2.3 visual_director（视觉导演智能体）

- **文件**：`agents/visual_director.py`（28 行）
- **职责**：将参考图/剧本转化为电影级关键帧序列，输出 Exhausted JSON
- **按需加载技能**：`storyboard-direction`（含 3 个参考文档）
- **注册工具**（7 个）：`save_text_file`, `read_text_file`, `list_directory`, `get_project_state`, `get_prompt_style_context_state`, `load_skill`, `load_skill_reference`
- **工具白名单约束**：严格限制只能使用已注册工具

### 2.4 image_gen（图片生成智能体）

- **文件**：`agents/image_gen.py`（63 行）
- **职责**：文生图/图生图、参考图、多视图、表情包、姿势图、三视图、宫格分镜
- **按需加载技能**：`image-generation`
- **注册工具**（20 个）：`generate_image`, `generate_reference_image`, `generate_multi_view`, `generate_expression_sheet`, `generate_pose_sheet`, `generate_prop_three_view_sheet`, `generate_storyboard_grid_sheet`, `query_task_status`, `wait_for_task`, `sleep_seconds`, `download_and_save_media`, `read_text_file`, `list_directory`, `add_subject_image_state`, `get_project_state`, `get_prompt_style_context_state`, `open_file_natively`, `format_clickable_link`, `load_skill`, `load_skill_reference`

### 2.5 video_gen（视频生成智能体）

- **文件**：`agents/video_gen.py`（55 行）
- **职责**：图生视频、任务等待、下载保存
- **按需加载技能**：`video-generation`
- **注册工具**（12 个）：`generate_video`, `query_task_status`, `wait_for_task`, `sleep_seconds`, `download_and_save_media`, `read_text_file`, `get_project_state`, `get_prompt_style_context_state`, `describe_media_capabilities`, `suggest_media_route`, `load_skill`, `load_skill_reference`

### 2.6 vision_analyzer（视觉分析智能体）

- **文件**：`agents/vision_analyzer.py`（38 行）
- **职责**：审美把控、一致性检查、修改建议
- **按需加载技能**：`vision-analysis`
- **注册工具**（8 个）：`analyze_image`, `wait_for_task`, `query_task_status`, `read_text_file`, `list_directory`, `open_file_natively`, `load_skill`, `load_skill_reference`

---

## 三、技能（Skill）体系

### 3.1 目录结构

```
skills/
├── project-management/
│   ├── SKILL.md                         # 项目生命周期管理
│   └── references/
│       └── directory-conventions.md     # 目录规范
├── style-configuration/
│   ├── SKILL.md                         # 风格治理工作流
│   └── references/
│       └── style-families-guide.md      # 风格家族指南
├── character-design/
│   ├── SKILL.md                         # 角色设计工作流
│   └── references/
│       └── reference-variant-rules.md   # 变体详细规则
├── scene-prop-design/
│   ├── SKILL.md                         # 场景/道具设计
│   └── references/
│       └── three-view-layout.md         # 三视图版式参考
├── storyboard-direction/
│   ├── SKILL.md                         # 分镜/视觉导演
│   └── references/
│       ├── exhausted-json-schema.md     # 穷尽式 JSON 规范
│       ├── composition-techniques.md    # 七种电影构图技法
│       └── lighting-vocabulary.md       # 用光术语表
├── image-generation/
│   ├── SKILL.md                         # 图片生成工作流
│   └── references/
│       └── standardized-layout-rules.md # 标准化版式规则
├── video-generation/
│   ├── SKILL.md                         # 视频生成工作流
│   └── references/
│       ├── precheck-rules.md            # 提交前预检规则
│       └── audio-mode-guide.md          # 音频模式指南
├── vision-analysis/
│   ├── SKILL.md                         # 视觉审美分析
│   └── references/
│       └── review-criteria.md           # 审核标准
└── media-routing/
    ├── SKILL.md                         # 媒体 Provider 路由
    └── references/
        └── provider-comparison.md       # Provider 对比参考
```

### 3.2 Skill 规模明细

| Skill 名称 | Description 长度 | SKILL.md 正文 | Reference 文件 |
|------------|-----------------|---------------|----------------|
| project-management | 87 字符 | 1613 字符（~403 tokens） | directory-conventions.md（556 字符） |
| style-configuration | 110 字符 | 1527 字符（~381 tokens） | style-families-guide.md（488 字符） |
| character-design | 76 字符 | 1381 字符（~345 tokens） | reference-variant-rules.md（584 字符） |
| scene-prop-design | 57 字符 | 1212 字符（~303 tokens） | three-view-layout.md（434 字符） |
| storyboard-direction | 101 字符 | 1678 字符（~419 tokens） | 3 个文件共 2270 字符 |
| image-generation | 97 字符 | 2378 字符（~594 tokens） | standardized-layout-rules.md（2147 字符） |
| video-generation | 87 字符 | 1965 字符（~491 tokens） | 2 个文件共 854 字符 |
| vision-analysis | 58 字符 | 653 字符（~163 tokens） | review-criteria.md（351 字符） |
| media-routing | 99 字符 | 1022 字符（~255 tokens） | provider-comparison.md（473 字符） |

### 3.3 各 Skill 核心内容

#### project-management
从 orchestrator 原指令中提取的六大阶段工作流编排逻辑、主体查询兜底规则、删除规则、结构化命名规范等。orchestrator 在接收到项目管理类任务时加载。

#### style-configuration
完整的风格治理工作流：触发条件识别、槽位提取、工具调用顺序（`list_style_families_state` → `list_style_subtypes_state` → `preview_style_preset_state`）、反馈格式、写入规则、禁止行为和转交条件。

#### character-design
角色参考图变体规则（pure_character / full_character / mounted_character）、前置检查逻辑、额外确认规则。包含"可用工具清单"表（`design_character`、`generate_reference_image`、`get_project_state`），工作流每步均标注具体工具名。消除了原来在 orchestrator、director、image_gen 三处重复注入同一规则的冗余。

#### scene-prop-design
场景空镜头原则、标准化版式意图识别、道具三视图路由规则（director → image_gen）、多宫格分镜路由规则（visual_director → image_gen）。包含"可用工具清单"表（`design_scene`、`design_prop`、`generate_prop_three_view_sheet`、`generate_storyboard_grid_sheet`、`generate_image`）。

#### storyboard-direction
visual_director 的核心工作流，分为 SKILL.md 主体和 3 个参考文档。主体包含连贯性规则、五步输出结构、多宫格专项规则；参考文档包含构图技法、用光术语和 Exhausted JSON Schema 详细规范。

#### image-generation
包含完整"任务 → 工具"映射表，覆盖全部 7 个生图工具（`generate_image`、`generate_reference_image`、`generate_multi_view`、`generate_expression_sheet`、`generate_pose_sheet`、`generate_prop_three_view_sheet`、`generate_storyboard_grid_sheet`），每个工具均标注场景、关键参数和使用优先级。图片生成闭环流程（提交 → 等待 → 下载 → 预览 → 注册）、图生图能力规则、防甩锅约束。

#### video-generation
包含完整 10 工具清单表和"标准执行流程"6 步伪代码（预检 → 配置 → 确认 → 提交 → 等待 → 保存）。视频提交前确认卡规则（硬规则）、音频模式区分、输入图优先级、长视频段编排、失败处理规则（禁止自动重试）。

#### vision-analysis
审美评审维度（构图、光影、色彩、一致性、技术质量）、输出格式（通过/打回）、工具使用流程。

#### media-routing
Provider 路由决策规则、显式模型优先、能力分流、配置引导、可用性验证、视频提交前预检。

---

## 四、技能加载器（Skill Loader）

### 4.1 文件位置

`tools/skill_loader.py`（132 行）

### 4.2 提供的工具函数

| 函数 | 用途 | 加载层 |
|------|------|--------|
| `list_available_skills()` | 返回所有 skill 的 name + description | L1 |
| `load_skill(skill_name)` | 返回 SKILL.md 正文 + 可用参考文档列表 | L2 |
| `load_skill_reference(skill_name, ref_file)` | 返回指定参考文档内容 | L3 |

### 4.3 技术实现

- 通过正则解析 SKILL.md 的 YAML frontmatter 提取 name/description
- 自动发现 `skills/` 目录下所有合法 skill（含 SKILL.md 的子目录）
- 对不存在的 skill 或 reference 返回友好错误信息并附带可用列表
- 所有函数都是纯读取操作，无副作用

### 4.4 注册方式

所有智能体在 `tools=[]` 中注册了 `load_skill` 和 `load_skill_reference`，使其可以在运行时按需加载技能。

---

## 五、上下文 Benchmark

### 5.1 三层加载量

| 层级 | 内容 | Token 估算 |
|------|------|-----------|
| L1（始终加载） | 9 个 skill 的 name + description | ~189 tokens |
| L2（单个 skill 按需加载） | 最大 image-generation ~594 tokens | 典型 ~300-500 tokens |
| L3（单个 reference 按需） | 最大 exhausted-json-schema ~243 tokens | 典型 ~100-200 tokens |

### 5.2 典型场景上下文开销

| 场景 | 加载的 skill | 额外上下文 |
|------|-------------|-----------|
| 用户询问风格推荐 | style-configuration | ~381 tokens |
| 用户要求创建项目 | project-management | ~403 tokens |
| 用户要求设计角色 | character-design | ~345 tokens |
| visual_director 制作分镜 | storyboard-direction + 3 refs | ~419 + ~567 = ~986 tokens |
| image_gen 生成图片 | image-generation | ~594 tokens |
| video_gen 生成视频 | video-generation + precheck | ~491 + ~146 = ~637 tokens |

### 5.3 改造前后对比

| 指标 | 改造前 | 改造后 | 变化 |
|------|--------|--------|------|
| orchestrator instruction 行数 | ~97 行 | ~35 行 | -64% |
| visual_director instruction 行数 | ~145 行 | ~18 行 | -88% |
| 首轮总上下文（所有智能体 instruction） | ~17500 tokens | ~4400 tokens | -75% |
| 首轮 orchestrator 上下文 | ~4000 tokens | ~1300 tokens | -67% |

---

## 六、工具分类矩阵

### 保留为工具的（执行副作用）

需要执行 API 调用、文件操作、状态修改的函数保留为 VeADK 工具：

- 项目状态 CRUD：`create_project_state`, `get_project_state` 等
- 风格配置 CRUD：`list_style_families_state`, `update_project_style_config_state` 等
- 文件 I/O：`save_text_file`, `read_text_file`, `download_and_save_media` 等
- 媒体生成：`generate_image`, `generate_video`, `wait_for_task` 等
- 媒体路由：`describe_media_capabilities`, `suggest_media_route`
- 显示：`open_file_natively`, `format_clickable_link`
- 技能加载：`list_available_skills`, `load_skill`, `load_skill_reference`

### 移入 Skill 的（纯知识/规则）

纯编排逻辑、决策规则、领域知识移入 SKILL.md：

- 六阶段工作流编排
- 风格治理全套规则（触发、槽位提取、反馈格式、写入、禁止行为）
- 角色参考图变体规则
- 标准化版式路由规则
- 媒体路由决策规则
- 视频预检/确认卡/失败处理规则
- 穷尽式 JSON 规范
- 七种电影构图技法
- 用光术语表

---

## 七、数据流：典型任务执行路径

### 示例：用户要求"帮我设计一个赛博朋克风格的女主角"

```
1. orchestrator 接收消息
2. 识别任务涉及"风格 + 角色"
3. 调用 load_skill("style-configuration") → 获取风格治理规则
4. 按规则调用风格工具推荐 2-3 个赛博朋克子类
5. 用户确认风格方案
6. 调用 load_skill("character-design") → 获取角色设计规则
7. 执行前置检查（get_project_state 检查主体库）
8. transfer → director（director 调用 load_skill("character-design")）
9. director 调用 design_character 获取提示词
10. transfer → image_gen（image_gen 调用 load_skill("image-generation")）
11. image_gen 执行闭环：generate_reference_image → wait_for_task → download → preview → register
12. transfer → vision_analyzer（调用 load_skill("vision-analysis")）
13. vision_analyzer 评审 → 通过/打回
14. 结果返回 orchestrator → 汇报用户
```

---

## 八、维护指南

### 8.1 新增 Skill

1. 在 `skills/` 下创建新目录（如 `skills/my-new-skill/`）
2. 创建 `SKILL.md`，包含 YAML frontmatter（name + description）和正文指令
3. 如有详细参考文档，放入 `references/` 子目录
4. 技能加载器会自动发现新 skill，无需修改任何代码

### 8.2 修改现有 Skill

直接编辑对应的 `SKILL.md` 或 `references/*.md` 文件即可。技能加载器每次调用时都会读取最新文件内容，支持热更新。

### 8.3 为智能体注册 Skill Loader

在智能体的 `tools=[]` 中添加：

```python
from tools.skill_loader import load_skill, load_skill_reference

Agent(
    tools=[..., load_skill, load_skill_reference]
)
```

在 instruction 中添加技能加载指引即可。

### 8.4 验证

运行 `python3 tests/test_skill_system.py` 可验证：
- 所有 skill 可正确解析
- 所有 reference 可正确加载
- 错误处理正常工作
- 上下文大小 benchmark

---

## 九、已知限制与后续优化方向

| 项目 | 当前状态 | 优化方向 |
|------|---------|---------|
| Skill 加载需额外工具调用轮次 | 方案 A（工具调用） | 高频 skill 可探索方案 B（动态 instruction 注入） |
| LLM 可能忘记加载 skill | 在 instruction 中写了触发映射表 | 可加 before_agent callback 自动注入 |
| 跨 skill 引用 | 各 skill 独立 | 可在 SKILL.md 中引用其他 skill 名称 |
| Skill 版本管理 | 无版本号 | 可在 metadata 中增加 version 字段 |
| A/B 测试 | 不支持 | 可通过目录命名或环境变量切换 |
| SKILL.md 工具覆盖 | v1.0.1 已通过审计脚本修复 | 建议每次新增/修改 Skill 后运行审计脚本 |
| 与 libtv-skill 整合 | 独立存在于 libtv-skills-main/ | 可将其 SKILL.md 符号链接到 skills/ |
