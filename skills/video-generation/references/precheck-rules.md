# 视频提交前预检详细规则

## 预检工具
- `suggest_media_route("generate_video", requested_model, intent_tags)` — 确认路由
- `describe_media_capabilities` — 查看详细能力边界

## 检查项

### 1. 时长约束
- 读取当前路由的 `duration_range`
- 如果用户要求时长超出范围，执行以下之一：
  - 调整时长到合法区间后提交
  - 询问用户是否切换 provider / model
  - 如果上游明确指定了模型，保留模型并请求用户改时长

### 2. 画幅约束
- 检查当前路由支持的 `aspect_ratios`
- 如果不支持用户指定的画幅，提前告知

### 3. 模型能力
- 不同模型支持的功能集不同
- 部分模型支持双图（首帧+尾帧），部分仅支持单图参考

### 4. 参数类型校验
- `duration` 必须是整数
- `input_images` 必须是路径数组
- `generate_audio` 必须是布尔值
- `audio_mode` 必须是合法枚举（ambient_only / speech）
- `aspect_ratio` 必须是合法枚举（16:9 / 9:16 / 1:1 等）
