---
name: media-routing
description: 媒体 Provider 路由决策技能。当任务涉及媒体后端选择、模型选择、默认 provider 切换、生成能力查询、媒体配置引导时触发。覆盖 provider 感知、路由决策、能力分流与可用性验证。
---

# 媒体 Provider 路由决策

## 核心原则
当前系统底层存在多个媒体 provider，不同 provider 的能力范围、模型透明度与配置方式不同。不要凭记忆硬编码判断，优先调用工具获取实时信息。

## 决策规则

### 能力查询
- 需要了解当前系统可用的媒体能力 → 调用 `describe_media_capabilities`
- 需要确认某个任务会路由到哪个 provider / model → 调用 `suggest_media_route(capability, requested_model, intent_tags)`

### 显式模型优先规则
当用户明确指定模型时，必须优先尊重模型约束，不得静默替换。如果当前 provider 不支持该模型，必须明确说明原因并给出配置建议。

### 媒体路由意图识别
当用户没有指定模型，但表达了目标（更快 / 更强质量 / 更低成本 / 更稳定 / 更适合完整工作流），应先识别为媒体路由意图，结合 provider catalog 做推荐。

### 能力分流规则
- 高阶工作流能力（角色设计、分镜拆解、提示词生成、图像分析）→ 优先考虑工作流能力更完整的 provider
- 显式指定生图/生视频模型 → 优先考虑支持显式模型选择的 provider

### 配置引导规则
- 切换默认媒体后端 → 引导配置 `MEDIA_PROVIDER`
- 已配置能力级 provider → 可进一步区分 `MEDIA_IMAGE_PROVIDER` / `MEDIA_VIDEO_PROVIDER`

### 可用性规则
不得把未接入、未配置或仅占位的 provider 说成"当前可直接使用"。只有在 provider catalog 显示可用且所需环境变量满足时，才可以向用户承诺该能力当前可用。

### 澄清规则
当媒体能力选择存在不确定性时，先解释当前可选路线，再询问用户是要"切默认后端"还是"本次任务显式指定模型"。

## 视频提交前预检（硬规则）
当任务涉及图生视频时长、模型能力或画幅限制时，必须在提交前通过 `suggest_media_route` 或 `describe_media_capabilities` 读取当前路由约束。若发现 duration 超出合法区间，不要直接转交一个必然失败的参数组合给 video_gen。
