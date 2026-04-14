---
name: character-design
description: 角色设计工作流技能。当任务涉及角色创建、角色参考图生成、角色设定板制作时触发。包含角色参考图变体规则、前置检查逻辑、纯人物参考图默认规则与额外确认规则。
---

# 角色设计工作流

## 前置检查（必须执行）
在生成任何角色图片前，必须先调用 `get_project_state` 检查主体库中是否已存在该角色。
如果已存在，主动询问用户："项目中已存在该角色的图片，是否需要使用已有图片作为参考图来进行图生图生成？"

## 角色参考图默认规则
只要用户没有明确指定其他版本，角色参考图一律默认使用"纯人物参考图"模式（`reference_variant="pure_character"`）：
- 只保留人物本体、服装、发型、体态与必要穿戴式配饰
- 不带武器、坐骑、宠物、伴生体或额外主体

## 额外确认规则
如果用户想生成以下非纯人物版本，必须先向用户明确确认，未确认前不得默认加入：
- **带标志武器版** (`full_character`)：保留角色标志性武器、手持道具
- **带坐骑完整设定版** (`mounted_character`)：含坐骑或伴生物
- **完整角色设定图**：根据用户需求选择对应变体

## 参考图变体三种模式

### pure_character（默认）
单人、单主体、全身完整展示、9:16 竖构图、纯白背景。禁止多视图、角色设定拼板、pose sheet、expression sheet。

### full_character
单角色、单主体、9:16 竖构图、纯白背景。允许标志性武器和身份绑定 props，不引入坐骑或额外角色。

### mounted_character
9:16 竖构图、纯白背景，以单个主角色为中心，仅出现明确指定的坐骑/伴生物/标志性武器。

## 可用工具清单

| 工具 | 所属智能体 | 用途 |
|---|---|---|
| `design_character` | director | 根据角色描述 + reference_variant 生成结构化设计提示词 |
| `generate_reference_image` | image_gen | 根据 director 输出的提示词生成角色参考图，支持 `reference_variant` 参数 |
| `get_project_state` | orchestrator | 前置检查：查询主体库中是否已存在该角色 |

## 工作流路由
1. 用户描述角色需求
2. 加载本技能，执行前置检查（调用 `get_project_state`）
3. 确定 reference_variant（pure_character / full_character / mounted_character）
4. 转交 director → 调用 `design_character` 获取设计提示词（director 需遵循相同的变体规则）
5. 将提示词和变体参数交给 image_gen → 调用 `generate_reference_image` 生图
6. 由 vision_analyzer 审核
7. 审核通过后保存至主体库

## 道具设定板规则
如果用户明确要求"道具三视图""工业设计三视图"等标准化设定板，不要让 image_gen 自由发挥普通单图，应优先使用专门的三视图生成能力（参见 scene-prop-design 技能）。
