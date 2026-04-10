from veadk import Agent
from tools.purevis import (
    generate_video,
    query_task_status,
    wait_for_task,
    sleep_seconds
)
from tools.file_io import download_and_save_media, read_text_file
from agents import GLOBAL_ASSET_GUIDELINE

video_gen_agent = Agent(
    name="video_gen",
    description="视频智能体，负责将图片和提示词转换为最终的视频片段。",
    instruction="""你是一个专业的视频生成与合成师。
你的主要职责是：
1. 接收图片分镜和关键帧，调用 `generate_video` 工具生成视频片段。**重要**：生成视频时必须将关键帧图片的本地路径作为一个列表传递给 `input_images` 参数（例如 `["/Users/.../output/projects/..."]`）。底层工具会自动将其转换为 Base64 数据提交给接口，你不需要做任何额外处理。
2. 视频生成是异步的，提交任务后请务必使用 `wait_for_task` 工具阻塞等待任务完成，不要频繁调用 query_task_status。
3. 任务完成后，提取视频 URL。
4. 使用 download_and_save_media 将视频保存到剧集输出的 video/ 目录中。""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        generate_video,
        query_task_status,
        wait_for_task,
        sleep_seconds,
        download_and_save_media,
        read_text_file
    ]
)
