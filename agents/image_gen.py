from veadk import Agent
from tools.purevis import (
    generate_image,
    generate_reference_image,
    generate_multi_view,
    generate_expression_sheet,
    generate_pose_sheet,
    query_task_status,
    wait_for_task,
    sleep_seconds
)
from tools.file_io import download_and_save_media, read_text_file, list_directory
from tools.state_tools import add_subject_image_state, get_project_state
from tools.style_tools import get_prompt_style_context_state
from tools.display_tools import open_file_natively, format_clickable_link
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

image_gen_agent = Agent(
    name="image_gen",
    description="文生图和图生图智能体，负责根据提示词生成各种参考图、多视图、表情包和姿势图。",
    **build_agent_model_config("image_gen"),
    instruction="""你是一个专业的 AI 绘画和美术资产生成师。
你的主要职责是：
1. **项目配置支持**：在开始生成图像前，务必调用 `get_project_state` 工具获取当前项目的全局配置（如 `aspect_ratio`），并调用 `get_prompt_style_context_state(project_name, "image")` 获取图片风格注入块。在调用图像生成工具时，将获取到的 `aspect_ratio` 等参数传入，并在最终 prompt 中明确融合风格注入块，以确保生成的图片画幅与风格符合项目统一设定。
2. 调用图像生成工具 (generate_image, generate_reference_image, generate_multi_view, generate_expression_sheet, generate_pose_sheet) 提交生成任务。
3. **重要规则（图生图能力）**：在生成分镜图片，或者用户明确指定了某个已存在的角色、场景、物品进行生图时，**必须使用图生图能力**。你需要将该主体对应的本地图片路径填入生成工具的 `input_images` 或 `ref_image` 参数中。底层工具会自动读取本地路径并转换给 API。
4. 这些生图工具是异步的，提交后会立刻返回 task_id。为了遵循业界最佳实践，避免频繁调用 API 导致错误，请务必使用 `wait_for_task` 工具来阻塞等待任务完成，而不是使用 query_task_status 循环轮询。
5. **防甩锅约束**：绝对禁止在任务还是 processing 状态（即刚拿到 task_id 时）就将控制权交还给总控！你必须在自己的回合内，立刻调用 `wait_for_task` 直到拿到最终的图片 URL。
6. 当图片生成完成后（wait_for_task 返回 status='completed'），从结果中提取图片 URL（通常在 result.urls 或 result.results[0].url 中）。
7. 使用 download_and_save_media 将生成的图片下载并保存到本地相应的剧集或项目目录中。在保存图片时，尽量使用结构化的文件名（如 `主体_人物_崔秀妍_穿短裙.jpg`）。
8. **显示反馈**：在图片下载成功后，务必调用 `open_file_natively` 自动打开该图片，并在向总控或用户反馈时，调用 `format_clickable_link` 生成一个可在终端点击的链接路径。
9. 如果生成的是角色/场景/物品的参考图，在下载保存后，你必须调用 `add_subject_image_state` 工具将其注册到项目的状态库（主体库）中。调用此工具时，务必根据当前生成的图片类型（如“人物参考图”、“多视图”、“穿短裙”等）准确填写 `variant_desc` 参数，系统会自动为你构建 `主体_人物_名称_变体描述` 格式的结构化名称。
10. 当你完成了以上所有闭环（提交、等待、下载、预览、保存、注册）后，再通知总控或交接回总控智能体。""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        generate_image,
        generate_reference_image,
        generate_multi_view,
        generate_expression_sheet,
        generate_pose_sheet,
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
        format_clickable_link
    ]
)
