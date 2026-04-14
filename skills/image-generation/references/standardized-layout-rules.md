# 图像生成工具详细参数与使用规则

## 1. generate_image（通用文生图 / 图生图）
- **场景**：自由构图的通用图片生成，或未命中任何专用版式时的默认选项
- **参数**：
  - `prompt`: 提示词描述
  - `aspect_ratio`: 画幅比（"16:9"、"9:16"、"1:1" 等）
  - `input_images`: 图生图时传入本地路径列表（如 `["output/.../img.jpg"]`），工具自动转 Base64
  - `model`: 可选，显式指定底层图片模型
- **注意**：当任务明确是标准化版式（三视图、多视图、宫格等）时，禁止使用此工具

## 2. generate_reference_image（角色/场景/道具参考图）
- **场景**：生成符合构图约束的角色参考图、场景参考图、道具参考图
- **参数**：
  - `prompt`: 提示词描述
  - `entity_type`: `character` | `scene` | `prop`
  - `reference_variant`: `pure_character`（默认）| `full_character` | `mounted_character`
  - `aspect_ratio`: 角色默认 9:16 竖构图
  - `input_images`: 可选，基于已有图片生成参考图
- **规则**：角色类型默认 pure_character，未经上游确认不得擅自切换变体

## 3. generate_multi_view（角色多视图转身设定板）
- **场景**：需要角色从多个角度展示（正面、侧面、背面、3/4 角度）的转身设定板
- **参数**：
  - `prompt`: 提示词描述
  - `character_name`: 角色名称
  - `ref_image`: 已有角色参考图的本地路径（必填）
- **注意**：必须已有角色参考图才能生成多视图

## 4. generate_expression_sheet（角色表情包设定板）
- **场景**：需要同一角色的多种表情变化（喜怒哀乐等）
- **参数**：
  - `prompt`: 提示词描述
  - `character_name`: 角色名称
  - `ref_image`: 已有角色参考图的本地路径（必填）

## 5. generate_pose_sheet（角色姿势设定板）
- **场景**：需要同一角色的多种动作姿势展示
- **参数**：
  - `prompt`: 提示词描述
  - `character_name`: 角色名称
  - `ref_image`: 已有角色参考图的本地路径（必填）

## 6. generate_prop_three_view_sheet（道具三视图 / 工业设计设定板）
- **场景**：道具或物品的正面/侧面/背面三视图标准化版式
- **参数**：
  - `prompt`: 提示词描述，建议包含材质与风格
  - `prop_name`: 道具名称
  - `input_images`: 可选，参考已有道具图片
  - `aspect_ratio`: 默认 16:9 横向以容纳三视图排版
- **触发关键词**：三视图、道具设定板、工业设计图、正侧背

## 7. generate_storyboard_grid_sheet（多宫格分镜拼图 / storyboard contact sheet）
- **场景**：将多个分镜画面排列在同一张画布上
- **参数**：
  - `prompt`: 提示词描述，建议融合每格镜头说明与连续性约束
  - `panel_count`: 宫格数，推荐 16（4×4）或 25（5×5）
  - `aspect_ratio`: 默认 1:1 适配网格
  - `input_images`: 可选，参考已有角色或场景图片
- **前置要求**：应优先使用 visual_director 输出的 panel plan
- **触发关键词**：16宫格、25宫格、多宫格、故事板拼图、storyboard contact sheet

## 工具选择决策树

```
用户需求
  ├─ 明确要求标准化版式？
  │   ├─ 道具三视图/工业设计 → generate_prop_three_view_sheet
  │   ├─ 多宫格分镜拼图 → generate_storyboard_grid_sheet
  │   ├─ 多视图/turnaround → generate_multi_view
  │   ├─ 表情包 → generate_expression_sheet
  │   └─ 姿势图 → generate_pose_sheet
  ├─ 角色/场景/道具的参考图？ → generate_reference_image
  └─ 自由构图/其他 → generate_image
```
