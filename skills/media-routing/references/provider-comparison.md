# 媒体 Provider 能力对比参考

## 查询方法

实际 provider 能力信息应通过 `describe_media_capabilities` 工具获取，本文档仅提供理解框架。

## 对比维度

| 维度 | 说明 |
|------|------|
| 支持的 capability | 该 provider 可执行的操作类型（generate_image, generate_video 等） |
| 模型透明度 | 是否支持显式指定底层模型 |
| 工作流能力 | 是否支持高阶编排（角色设计、分镜拆解等） |
| 环境变量依赖 | 使用该 provider 需要配置的环境变量 |
| 时长约束 | 视频生成的 duration_range |
| 画幅约束 | 支持的 aspect_ratio 列表 |

## 路由优先级逻辑

1. 如果用户显式指定了模型 → 路由到支持该模型的 provider
2. 如果用户指定了 intent_tags → 按标签权重路由
3. 否则按默认 provider 配置路由
