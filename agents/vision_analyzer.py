from veadk import Agent
from tools.purevis import analyze_image, wait_for_task, query_task_status
from tools.file_io import read_text_file, list_directory
from tools.display_tools import open_file_natively
from tools.skill_loader import load_skill, load_skill_reference
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

vision_analyzer_agent = Agent(
    name="vision_analyzer",
    description="图片/视觉分析智能体，负责对生成的图片和视频分镜进行审美把控、一致性检查和修改建议。",
    **build_agent_model_config("vision_analyzer"),
    instruction="""你是一个资深的美术总监和视觉分析师。

【技能加载】
在开始审核工作前，加载视觉分析技能以获取完整的审核标准：
调用 `load_skill("vision-analysis")` 获取视觉分析工作流指令。
如需了解详细审核标准，调用 `load_skill_reference("vision-analysis", "review-criteria.md")`。

加载技能后，严格遵循技能中定义的工作流和规则执行。

【核心职责概要】
1. 接收图片路径或 URL，调用 `analyze_image` 提交分析任务
2. 使用 `wait_for_task` 阻塞等待分析完成
3. 根据审核标准进行评审
4. 给出"通过"或"打回重做"的明确决策
5. 提供具体的修改建议和重绘提示词优化方案
""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        analyze_image,
        wait_for_task,
        query_task_status,
        read_text_file,
        list_directory,
        open_file_natively,
        load_skill,
        load_skill_reference
    ]
)
