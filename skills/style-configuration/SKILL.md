---
name: style-configuration
description: 结构化风格配置管理技能。当用户输入包含风格词、审美词、参考风格、媒介适配诉求，或表达"推荐风格""偏二次元/写实/诗意""有没有相关设定""这种风格适合什么"等语义时触发。负责风格意图识别、槽位提取、候选推荐与项目写入。
---

# 风格配置管理

## 触发条件

当用户输入命中以下任意信号时，优先识别为"结构化风格配置意图"，不要立刻转交给 director：
- 风格词 / 审美词（二次元、写实、诗意、赛博朋克、水墨、油画、胶片感…）
- "有没有相关设定" "推荐一下风格" "这种风格适合什么" "偏XX风格"
- 媒介适配诉求（适合做竖屏短剧、电影画幅、横屏MV…）
- 参考风格提及（像宫崎骏、像新海诚、美漫风…）

## 工作流

### Step 1: 槽位提取
从用户输入中提取或推断以下字段：
- `art_style_family`（风格家族）
- `art_style_subtype`（二级子类）
- `media_family` / `media_subtype`（媒介家族 / 子类）
- 推荐色板、推荐镜头、推荐材质、受众标签
- 风格 × 媒介的设计文案方向

### Step 2: 工具调用顺序
1. `list_style_families_state()` — 获取所有风格家族
2. `list_style_subtypes_state(family)` — 获取目标家族下的二级子类
3. `preview_style_preset_state(family, subtype)` — 预览具体预设元数据

根据用户语义选择 2~3 个最接近的结构化风格候选。

### Step 3: 反馈格式
按以下顺序回复用户：
1. 已识别的风格倾向
2. 候选结构化风格方案（2~3 个）
3. 每个方案的核心元数据（family / subtype、适配媒介、推荐色板、推荐镜头、推荐材质、受众标签）
4. 建议下一步（例如选择 image / keyframe / video 目标，或是否继续交给 director 做内容设定）

### Step 4: 写入规则
- 有项目名且用户确认 → 调用 `update_project_style_config_state` 写入项目状态
- 无项目名 → 仅推荐，不强制写入
- 写入时需分别为 `video`、`image`、`keyframe` 三类资产确定风格

### Step 5: 查询与回滚
- 查看当前配置 → `get_project_style_config_state`
- 切换 / 覆盖配置 → `update_project_style_config_state`
- 删除配置 → `delete_project_style_config_state`
- 查看历史版本 → `list_project_style_versions_state`
- 获取提示词注入块 → `get_prompt_style_context_state(project_name, target)`

## 禁止行为
- 不要直接转交 director（除非用户明确要求跳过风格推荐）
- 不要跳过风格工具直接凭印象手写风格结论
- 不要将零散的风格字符串直接覆盖整个 settings

## 转交条件
满足以下之一才可转交 director：
1. 用户已确认某个风格方案
2. 用户明确表示先别做风格推荐，直接做内容设定
3. 当前任务纯粹是角色、场景、剧情内容创作，不涉及风格选型

## 转交摘要要求
如果后续需要转交给 director，必须先总结一段风格摘要，至少包含：
- 已选 `art_style_family` + `art_style_subtype`
- 目标媒介或目标资产类型
- 推荐色板 / 镜头 / 材质关键词
- 用户提出的内容关键词
