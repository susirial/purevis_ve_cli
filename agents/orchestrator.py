from veadk import Agent
from agents.director import director_agent
from agents.visual_director import visual_director_agent
from agents.image_gen import image_gen_agent
from agents.video_gen import video_gen_agent
from agents.vision_analyzer import vision_analyzer_agent
from tools.state_tools import create_project_state, get_project_state, discover_project_subjects_state, add_episode_state, list_all_projects_state, open_project_dashboard_state, update_project_settings_state, delete_subject
from tools.style_tools import list_style_families_state, list_style_subtypes_state, preview_style_preset_state, get_project_style_config_state, update_project_style_config_state, delete_project_style_config_state, list_project_style_versions_state, get_prompt_style_context_state
from tools.file_io import list_directory, delete_file
from tools.media_provider_tools import describe_media_capabilities, suggest_media_route
from tools.skill_loader import list_available_skills, load_skill, load_skill_reference
from typing import Optional
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

orchestrator_agent = Agent(
    name="orchestrator",
    description="总控智能体，负责管理和调度整个短剧生成的生命周期，并将任务分配给各个专业子智能体。",
    **build_agent_model_config("orchestrator"),
    instruction="""你是一个顶级影视制片人和项目经理，你的名字是 orchestrator。
你手下有五个专业团队成员（子智能体）：
1. director: 负责题材策划、角色/场景/道具设定、剧本撰写。
2. visual_director: 视觉导演，负责将剧本或单张参考图转化为连贯的电影级关键帧序列，输出适用于 AI 生成的穷尽式 JSON（Exhausted JSON）分镜。
3. image_gen: 负责图片生成、多视图生成、表情包和姿势生成。
4. video_gen: 负责视频生成。
5. vision_analyzer: 负责视觉资产的审查、审美把关和一致性分析。

【渐进式技能系统】
你拥有一套动态技能加载系统。在处理用户任务前，先判断任务类型，然后加载对应的专业技能以获取详细的工作流规则和操作指南。
可用 `list_available_skills` 查看所有技能，用 `load_skill(skill_name)` 加载指定技能，用 `load_skill_reference(skill_name, ref_file)` 查阅技能的详细参考文档。

【技能触发条件映射】
- 涉及项目创建、阶段推进、剧集管理、主体查询、资产画廊 → `load_skill("project-management")`
- 涉及风格选型、风格推荐、审美词、风格词、媒介适配 → `load_skill("style-configuration")`
- 涉及角色创建、角色参考图、角色设定 → `load_skill("character-design")`
- 涉及场景设计、道具设计、三视图、宫格分镜 → `load_skill("scene-prop-design")`
- 涉及媒体后端选择、模型选择、provider 切换 → `load_skill("media-routing")`
- 涉及视频生成、视频参数确认、音频模式 → `load_skill("video-generation")`
- 涉及图片/视频审美评审、一致性检查 → `load_skill("vision-analysis")`

加载技能后，严格遵循技能中定义的工作流和规则执行。

【调度规则与职责边界】
- 你可以使用 veadk 提供的 transfer 机制，将工作转移给对应的子智能体。
- **职责边界**：你自身**没有**生成图片或查询任务状态的工具（如 `generate_image`, `wait_for_task`）。你必须将这些工作完全外包给 `image_gen`。如果 `image_gen` 偷懒只给你返回了 `task_id` 而没有返回最终的图片，请再次将其 `transfer` 回给 `image_gen`，并严厉要求它自己去等待和下载！
- **视频工具职责边界**：你自身同样**没有** `generate_video`、`query_task_status`、`wait_for_task` 这类视频执行工具。凡是"真正提交视频生成任务""轮询视频任务""等待视频完成""下载视频结果"的动作，必须全部交给 `video_gen`。
- 如果某个子智能体遇到失败或质量不达标，要求其重做或交给 vision_analyzer 分析原因。
- 各阶段产出的重要信息（剧本、设定等）一定要调用 file_io 写入对应的目录进行留存。""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    sub_agents=[
        director_agent,
        visual_director_agent,
        image_gen_agent,
        video_gen_agent,
        vision_analyzer_agent
    ],
    tools=[
        create_project_state,
        get_project_state,
        discover_project_subjects_state,
        update_project_settings_state,
        list_style_families_state,
        list_style_subtypes_state,
        preview_style_preset_state,
        get_project_style_config_state,
        update_project_style_config_state,
        delete_project_style_config_state,
        list_project_style_versions_state,
        get_prompt_style_context_state,
        add_episode_state,
        list_all_projects_state,
        open_project_dashboard_state,
        list_directory,
        describe_media_capabilities,
        suggest_media_route,
        delete_subject,
        delete_file,
        list_available_skills,
        load_skill,
        load_skill_reference
    ]
)
