from veadk import Agent
from tools.purevis import (
    generate_video,
    query_task_status,
    wait_for_task,
    sleep_seconds
)
from tools.file_io import download_and_save_media, read_text_file
from tools.state_tools import get_project_state
from tools.style_tools import get_prompt_style_context_state
from tools.media_provider_tools import describe_media_capabilities, suggest_media_route
from tools.skill_loader import load_skill, load_skill_reference
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

video_gen_agent = Agent(
    name="video_gen",
    description="视频智能体，负责将图片和提示词转换为最终的视频片段。",
    **build_agent_model_config("video_gen"),
    instruction="""你是一个专业的视频生成与合成师。

【技能加载】
在开始工作前，你必须先加载视频生成技能以获取完整的工作流规则：
调用 `load_skill("video-generation")` 获取视频生成工作流指令。
如需了解预检规则详情，调用 `load_skill_reference("video-generation", "precheck-rules.md")`。
如需了解音频模式详情，调用 `load_skill_reference("video-generation", "audio-mode-guide.md")`。

加载技能后，严格遵循技能中定义的工作流和规则执行。

【核心职责概要】
1. 预检：调用 `suggest_media_route` 确认路由约束
2. 获取项目配置和风格注入块
3. 确认卡展示后调用 `generate_video` 提交任务
4. 使用 `wait_for_task` 阻塞等待（禁止频繁轮询）
5. 下载保存视频到剧集 video/ 目录

【硬规则】
- 失败后禁止自动重试，必须先向用户/上游报告
- 提示词中不得混入工作流提醒或系统注释
- `duration` 必须是整数，`input_images` 必须是路径数组
""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        generate_video,
        query_task_status,
        wait_for_task,
        sleep_seconds,
        download_and_save_media,
        read_text_file,
        get_project_state,
        get_prompt_style_context_state,
        describe_media_capabilities,
        suggest_media_route,
        load_skill,
        load_skill_reference
    ]
)
