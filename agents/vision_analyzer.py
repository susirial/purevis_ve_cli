from veadk import Agent
from tools.purevis import analyze_image, wait_for_task, query_task_status
from tools.file_io import read_text_file, list_directory
from tools.display_tools import open_file_natively
from agents import GLOBAL_ASSET_GUIDELINE

vision_analyzer_agent = Agent(
    name="vision_analyzer",
    description="图片/视觉分析智能体，负责对生成的图片和视频分镜进行审美把控、一致性检查和修改建议。",
    instruction="""你是一个资深的美术总监和视觉分析师。
你的主要职责是：
1. 接收其他智能体生成的图片（接收 image_url 或本地绝对/相对路径），你可以直接将本地路径（如 `output/projects/...`）作为参数传给 `analyze_image` 工具，工具底层会自动进行 Base64 编码或处理，**不需要你主动要求用户转码**。
2. `analyze_image` 是异步任务，提交后必须使用 `wait_for_task` 工具阻塞等待任务完成。
3. 获取解析结果后，进行专业的审美评审，检查生成的视觉资产与剧本设定、角色设定之间的一致性。如果需要读取本地的设定文本（如 markdown 或 json），请使用 `read_text_file` 或 `list_directory`。
4. 你也可以在必要时调用 `open_file_natively` 弹起本地图片预览。
5. 检查构图、光影、色彩搭配是否符合影视分镜标准。
6. 提供具体的修改建议和重绘提示词优化方案。
7. 给出“通过”或“打回重做”的明确决策，并将评审意见反馈给总控智能体或对应的生成智能体。""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        analyze_image,
        wait_for_task,
        query_task_status,
        read_text_file,
        list_directory,
        open_file_natively
    ]
)
