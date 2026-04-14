from veadk import Agent
from tools.purevis import (
    generate_image,
    generate_reference_image,
    generate_multi_view,
    generate_expression_sheet,
    generate_pose_sheet,
    generate_prop_three_view_sheet,
    generate_storyboard_grid_sheet,
    query_task_status,
    wait_for_task,
    sleep_seconds
)
from tools.file_io import download_and_save_media, read_text_file, list_directory
from tools.state_tools import add_subject_image_state, get_project_state
from tools.style_tools import get_prompt_style_context_state
from tools.display_tools import open_file_natively, format_clickable_link
from tools.skill_loader import load_skill, load_skill_reference
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

image_gen_agent = Agent(
    name="image_gen",
    description="文生图和图生图智能体，负责根据提示词生成各种参考图、多视图、表情包和姿势图。",
    **build_agent_model_config("image_gen"),
    instruction="""你是一个专业的 AI 绘画和美术资产生成师。

【技能加载】
在开始工作前，你必须先加载图片生成技能以获取完整的工作流规则：
调用 `load_skill("image-generation")` 获取图片生成工作流指令。
如需了解标准化版式的详细规则，调用 `load_skill_reference("image-generation", "standardized-layout-rules.md")`。

加载技能后，严格遵循技能中定义的工作流和规则执行。

【核心职责概要】
1. 调用图像生成工具提交生成任务
2. 使用 `wait_for_task` 阻塞等待任务完成（禁止在 processing 状态时交还控制权）
3. 下载保存图片、打开预览、生成可点击链接
4. 如果是主体库资产，注册到项目状态
5. 完成全部闭环后才可交接回总控
""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        generate_image,
        generate_reference_image,
        generate_multi_view,
        generate_expression_sheet,
        generate_pose_sheet,
        generate_prop_three_view_sheet,
        generate_storyboard_grid_sheet,
        query_task_status,
        wait_for_task,
        sleep_seconds,
        download_and_save_media,
        read_text_file,
        list_directory,
        add_subject_image_state,
        get_project_state,
        get_prompt_style_context_state,
        open_file_natively,
        format_clickable_link,
        load_skill,
        load_skill_reference
    ]
)
