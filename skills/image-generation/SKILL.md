---
name: image-generation
description: 图片生成工作流技能。当任务涉及文生图、图生图、角色参考图、多视图、表情包、姿势图、道具三视图、多宫格分镜拼图的生成和管理时触发。覆盖项目配置前置、图生图规则、标准化版式、异步任务闭环与资产注册。
---

# 图片生成工作流

## 可用生图工具清单（任务 → 工具 映射）

你拥有以下 7 个图像生成工具，根据任务类型选择正确的工具：

| 任务场景 | 工具 | 关键参数 |
|---------|------|---------|
| 通用文生图 / 图生图 | `generate_image` | prompt, aspect_ratio, input_images, model |
| 角色/场景/道具参考图 | `generate_reference_image` | prompt, entity_type, reference_variant, aspect_ratio, input_images, model |
| 角色多视图转身设定板 | `generate_multi_view` | prompt, character_name, ref_image, model |
| 角色表情包设定板 | `generate_expression_sheet` | prompt, character_name, ref_image, model |
| 角色姿势设定板 | `generate_pose_sheet` | prompt, character_name, ref_image, model |
| 道具三视图 / 工业设计设定板 | `generate_prop_three_view_sheet` | prompt, prop_name, input_images, aspect_ratio(默认16:9), model |
| 多宫格分镜拼图 / storyboard | `generate_storyboard_grid_sheet` | prompt, panel_count(16或25), aspect_ratio(默认1:1), input_images, model |

如需了解每个工具的详细参数和使用注意事项，调用 `load_skill_reference("image-generation", "standardized-layout-rules.md")`。

## 模型选择规则

所有生图工具均支持可选的 `model` 参数，用于显式指定底层图片生成模型。

### 合法模型名（必须使用内部 key，不接受显示名）

| 内部 key | 显示名 | 说明 |
|----------|--------|------|
| `lib_nano_2` | Lib Nano 2 | LibTV 默认生图模型 |
| `lib_nano_pro` | Lib Nano Pro | LibTV 高质量生图模型 |

### 使用规则
- 不传 `model` 时使用系统默认路由（由环境配置决定）
- 传入时**必须使用上表中的「内部 key」**（如 `model="lib_nano_2"`），不要使用显示名（如 "Lib Nano 2"、"LibTv nano 2"）
- 传入不合法的模型名会返回错误信息，其中包含当前可用的合法模型名列表
- 如不确定当前可用模型，可先调用 `describe_media_capabilities()` 查询

## 前置步骤（每次生成前必须执行）
1. 调用 `get_project_state` 获取项目全局配置（特别是 `aspect_ratio`）
2. 调用 `get_prompt_style_context_state(project_name, "image")` 获取图片风格注入块
3. 在最终 prompt 中融合风格注入块，确保画幅与风格符合项目统一设定

## 图生图能力规则（重要）
在以下场景中，**必须使用图生图能力**：
- 生成分镜图片（将关键帧参考图传入 `input_images`）
- 用户指定了某个已存在的角色/场景/物品进行生图

将主体对应的本地图片路径填入 `input_images` 或 `ref_image` 参数中，底层工具会自动读取本地路径并转换为 Base64 给 API。

## 工具选择优先级规则

### 角色参考图
调用 `generate_reference_image`，默认 `reference_variant="pure_character"`。只有上游明确确认了其他变体时才可更改。角色默认 `aspect_ratio="9:16"` 竖构图。

### 标准化版式（强优先）
当任务命中以下关键词时，**禁止退化为普通 `generate_image`**：
- 道具三视图 / 工业设计设定板 / 正侧背 → `generate_prop_three_view_sheet`
- 16宫格 / 25宫格 / 多宫格分镜 / storyboard contact sheet → `generate_storyboard_grid_sheet`
- 角色多视图 / turnaround → `generate_multi_view`
- 角色表情包 / expression sheet → `generate_expression_sheet`
- 角色姿势 / pose sheet → `generate_pose_sheet`

仅在上游明确要求自由构图时才使用通用 `generate_image`。

### 分镜拼图前置要求
如果任务是多宫格分镜拼图，优先使用上游 visual_director 已整理好的 panel plan、镜头说明和角色连续性约束。如果没有这些结构化输入，先提醒总控补齐分镜规划，不要自行编造完整故事。

## 异步任务闭环（防甩锅约束）
1. 调用生成工具提交任务，获取 task_id
2. **必须**立刻调用 `wait_for_task(task_id)` 阻塞等待（不要用 query_task_status 循环轮询）
3. **禁止**在 processing 状态时就将控制权交还总控
4. 等待完成后，提取图片 URL
5. 调用 `download_and_save_media` 保存到本地
6. 调用 `open_file_natively` 打开预览
7. 调用 `format_clickable_link` 生成终端可点击链接
8. 如果是主体库资产，调用 `add_subject_image_state` 注册到状态库

## 资产注册规则
调用 `add_subject_image_state` 时，根据图片类型准确填写 `variant_desc`（如"人物参考图""多视图""三视图设定板"），系统自动构建结构化名称。

## 完成条件
只有在完成全部闭环（提交 → 等待 → 下载 → 预览 → 保存 → 注册）后，才可通知总控或交接回总控。
