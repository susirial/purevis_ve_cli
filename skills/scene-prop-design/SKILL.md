---
name: scene-prop-design
description: 场景与道具设计工作流技能。当任务涉及场景空镜头生成、道具设定图制作、三视图/工业设计图、标准化版式任务识别时触发。
---

# 场景与道具设计工作流

## 场景设计规则

### 空镜头原则
使用 `design_scene` 生成场景时，该场景主要用于生成没有人物的空镜头环境图。必须在生成的提示词/描述中明确强调："该场景主体中绝对不能出现任何人物或动物（Empty shot, no characters or animals）"。

### 场景设计流程
1. 用户描述场景需求
2. 转交 director 调用 `design_scene` 获取提示词
3. 交给 image_gen 生成场景图
4. 由 vision_analyzer 审核
5. 保存至主体库

## 道具设计规则

### 标准化版式意图识别
当用户提到以下表达时，优先识别为"标准化版式生成任务"，不要当作普通自由构图图片需求：
- 三视图 / 道具设定板 / 工业设计图
- 正面侧面背面 / turnaround
- 16宫格 / 25宫格 / 多宫格分镜
- 故事板拼图 / storyboard contact sheet

### 道具三视图路由规则
此类任务优先走 `director -> image_gen` 路径：
- 如果用户道具描述不足，先交给 director 补全描述
- 描述充分时可直接把风格摘要与道具描述转交 image_gen
- 明确要求 image_gen 调用 `generate_prop_three_view_sheet`

### 多宫格分镜拼图路由规则
此类任务优先走 `visual_director -> image_gen` 路径：
- 必须先让 visual_director 输出 panel plan / Grid Sheet Prompt
- 再交给 image_gen 调用 `generate_storyboard_grid_sheet`
- 不要跳过 visual_director 直接让 image_gen 编完整故事板
