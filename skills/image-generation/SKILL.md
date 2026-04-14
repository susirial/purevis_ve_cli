---
name: image-generation
description: 图片生成工作流技能。当任务涉及文生图、图生图、角色参考图、多视图、表情包、姿势图、道具三视图、多宫格分镜拼图的生成和管理时触发。覆盖项目配置前置、图生图规则、标准化版式、异步任务闭环与资产注册。
---

# 图片生成工作流

## 前置步骤（每次生成前必须执行）
1. 调用 `get_project_state` 获取项目全局配置（特别是 `aspect_ratio`）
2. 调用 `get_prompt_style_context_state(project_name, "image")` 获取图片风格注入块
3. 在最终 prompt 中融合风格注入块

## 图生图能力规则（重要）
在以下场景中，必须使用图生图能力：
- 生成分镜图片
- 用户指定了某个已存在的角色/场景/物品进行生图

将主体对应的本地图片路径填入 `input_images` 或 `ref_image` 参数中，底层工具会自动读取本地路径并转换给 API。

## 角色参考图规则
调用 `generate_reference_image` 时，默认使用 `reference_variant="pure_character"`。只有上游明确确认了其他变体时才可更改。

## 标准化版式工具优先规则
- 道具三视图 / 工业设计设定板 → 优先 `generate_prop_three_view_sheet`
- 16宫格 / 25宫格 / 多宫格分镜拼图 → 优先 `generate_storyboard_grid_sheet`
- 不要退化成普通 `generate_image`，除非上游明确要求自由构图

## 分镜拼图前置要求
如果任务是多宫格分镜拼图，优先使用上游 visual_director 已整理好的 panel plan。如果没有结构化输入，先提醒总控补齐分镜规划。

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
