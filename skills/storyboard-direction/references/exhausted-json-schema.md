# 穷尽式 JSON 提示词规范（核心交付）

当用户需要可直接喂给下游工具/模型的结构化提示词时，你必须为每一个关键帧输出一段独立、合法 JSON（UTF-8，双引号，无注释，无尾逗号）。

## 顶层结构（每帧一份 JSON 对象）

须至少包含以下键：

### meta
- type, style, quality, version
- keyframe_id
- suggested_duration_s
- shot_scale
- composition_technique: { id, name_en, name_zh, execution_notes }

### subject / subjects[]
- name
- resemblance（可选）
- physical
- clothing
- pose_action

### props
- name
- material
- state
- interaction_with_subject

### environment
- location
- time_of_day
- weather
- details
- background
- atmosphere

### lighting
- setup
- key_light
- fill
- rim_or_back
- practicals
- contrast
- highlight_placement
- shadow_placement
- continuity_note

### composition
- shot_type
- framing
- aspect_ratio
- focal_point
- leading_lines_or_frame
- screen_direction

### technical_style
- camera: { 镜头与焦段 }
- depth_of_field
- effects
- rendering

### prompt_bundle
- **prompt_zh_flat**（必填）：融合后的单段中文提示，包含画幅等所有关键信息
- prompt_en_flat
- lighting_keywords
- negative
