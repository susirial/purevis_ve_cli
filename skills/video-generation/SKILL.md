---
name: video-generation
description: 视频生成工作流技能。当任务涉及图生视频、视频提交、视频参数确认、音频模式选择、视频任务失败处理时触发。覆盖预检规则、确认卡流程、音频模式、失败处理、长视频编排与输入图优先级。
---

# 视频生成工作流

## 可用工具清单（video_gen 智能体）

| 工具 | 用途 |
|---|---|
| `generate_video` | 提交图生视频任务（核心生成工具） |
| `wait_for_task` | 阻塞等待异步任务完成（推荐用法，禁止频繁轮询） |
| `query_task_status` | 查询任务状态（仅在需要非阻塞检查时使用） |
| `sleep_seconds` | 等待指定秒数（配合轮询时使用） |
| `download_and_save_media` | 下载生成的视频文件并保存到本地剧集 video/ 目录 |
| `read_text_file` | 读取剧本、分镜等文本文件 |
| `get_project_state` | 获取项目配置（角色图路径、画幅、风格等） |
| `get_prompt_style_context_state` | 获取视频风格注入块（`target="video"`） |
| `describe_media_capabilities` | 查询当前系统可用的媒体生成能力与约束 |
| `suggest_media_route` | 预检路由：确认当前任务会走哪个 provider/model，获取时长/画幅约束 |

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

## 标准执行流程

```
1. 预检  → suggest_media_route("generate_video", model, intent_tags)  确认路由约束
2. 配置  → get_project_state + get_prompt_style_context_state(project, "video")  获取项目配置和风格注入
3. 确认  → 向用户展示确认卡（prompt / input_images / duration / model / audio_mode 等）
4. 提交  → generate_video(...)  提交生成任务
5. 等待  → wait_for_task(task_id)  阻塞等待完成
6. 保存  → download_and_save_media(url, save_path)  下载视频到剧集 video/ 目录
```

## 视频提交执行边界（硬规则）
当用户已明确确认"参数确认无误，直接提交"时，下一步动作必须是 transfer 给 video_gen，不能自己调用 generate_video。
