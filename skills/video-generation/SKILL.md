---
name: video-generation
description: 视频生成工作流技能。当任务涉及图生视频、视频提交、视频参数确认、音频模式选择、视频任务失败处理时触发。覆盖预检规则、确认卡流程、音频模式、失败处理、长视频编排与输入图优先级。
---

# 视频生成工作流

## 职责边界（硬规则）
orchestrator 自身没有 `generate_video`、`query_task_status`、`wait_for_task` 这类工具。所有视频执行操作必须通过 transfer 交给 video_gen。

## 提交前确认规则（硬规则）
每次把任务交给 video_gen 前，必须先向用户展示最终参数摘要（确认卡），至少包含：
- 最终 prompt
- input_images 路径
- duration
- aspect_ratio
- model
- generate_audio
- audio_mode
- 是否含台词

只有用户明确确认后才允许 transfer 给 video_gen 提交。

## 音频模式规则
必须显式区分：
- `audio_mode="ambient_only"`：无台词，仅环境音/音乐
- `audio_mode="speech"`：包含口播/对白/旁白

如果用户没有要求人声，默认使用 `ambient_only`。

## 图生视频输入图优先级
当同一主体同时存在"多视图设定图"和"纯角色参考图"时：
1. 默认优先使用"多视图设定图"作为 input_images
2. 仅在以下情况退回使用纯角色参考图：
   - 缺少多视图设定图
   - 用户明确要求锁定某张参考图
   - 当前任务需要复现某张特定静帧
3. 如果缺少多视图设定图，必须先向用户说明并确认

## 长视频段编排规则
当视频模型支持较长时长（如 8-15 秒）且多个相邻分镜满足以下条件时，优先合并为一个连续视频段：
- 同一场景
- 同一角色连续动作
- 同一光影逻辑

不要默认一镜一视频提交。

## 失败处理规则（硬规则）
如果 video_gen 返回 `failed` / `timeout` / `expired`：
- 绝对不能在未经用户确认的情况下再次提交
- 不能擅自改模型、改时长、拆镜头或换素材重试
- 必须先把失败摘要、关键报错、project_url 告知用户
- 询问用户是否要重试或调整方案

## 视频提交执行边界（硬规则）
当用户已明确确认"参数确认无误，直接提交"时，下一步动作必须是 transfer 给 video_gen，不能自己调用 generate_video。
