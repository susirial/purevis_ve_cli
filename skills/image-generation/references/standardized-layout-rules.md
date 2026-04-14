# 标准化版式生成规则详解

## generate_prop_three_view_sheet
用于道具三视图 / 工业设计设定板：
- 默认画幅 16:9 横向
- 单画布输出正面/侧面/背面三视图
- 参数：prompt, prop_name, input_images(可选), aspect_ratio

## generate_storyboard_grid_sheet
用于多宫格分镜拼图 / storyboard contact sheet：
- 支持 16 宫格(4×4) 或 25 宫格(5×5)
- 默认画幅 1:1
- 参数：prompt, panel_count, aspect_ratio, input_images(可选)

## generate_reference_image
用于角色/场景/道具参考图：
- 参数：prompt, entity_type, reference_variant, aspect_ratio, input_images
- 角色默认 9:16 竖构图

## generate_multi_view
用于角色多视图转身设定板：
- 参数：prompt, character_name, ref_image

## generate_expression_sheet
用于角色表情包设定板：
- 参数：prompt, character_name, ref_image

## generate_pose_sheet
用于角色姿势设定板：
- 参数：prompt, character_name, ref_image

## 路由决策原则
1. 用户明确要求标准化版式 → 使用对应专用工具
2. 用户未指定 → 根据任务语义判断
3. 不确定时 → 使用通用 generate_image
