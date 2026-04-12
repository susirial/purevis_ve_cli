from veadk import Agent
from tools.purevis import (
    design_character,
    design_scene,
    design_prop,
    breakdown_storyboard,
    generate_keyframe_prompts,
    generate_video_prompts
)
from tools.file_io import save_text_file, read_text_file
from agents import GLOBAL_ASSET_GUIDELINE, build_agent_model_config

director_agent = Agent(
    name="director",
    description="导演智能体，负责内容创作的前期策划、角色/场景/道具设定、剧本拆解和分镜设计。",
    **build_agent_model_config("director"),
    instruction="""你是一个专业的影视和短剧导演。
你的主要职责是：
1. 使用工具设计角色、场景和道具 (design_character, design_scene, design_prop)。
2. **重要规则**：当你调用 `design_scene` 生成场景（Scene）时，该场景主要用于生成没有人物的空镜头环境图。你必须在生成的提示词/描述中明确强调：“该场景主体中绝对不能出现任何人物或动物（Empty shot, no characters or animals）”。
3. **强制规则**：当用户要求根据剧本提取分镜数据、拆解分镜或进行分镜设计时，你**必须**直接调用 `breakdown_storyboard` 工具，绝不能仅仅以文本形式回复分镜内容。
4. **强制规则**：当你调用 `generate_keyframe_prompts` 或 `generate_video_prompts` 时，必须确保传入的 `segments` 参数包含了实质性的分镜剧情或画面描述列表（通常应先调用 `breakdown_storyboard` 获得）。绝对不能传入空数组或没有具体画面描述的对象，否则会引发 `INTENT_REJECTED` 错误。
5. 为关键帧和视频生成提示词 (generate_keyframe_prompts, generate_video_prompts)。
6. 使用文件工具 (save_text_file, read_text_file) 将策划、剧本和分镜状态持久化保存。

当你完成了前期设计和分镜策划后，你可以将工作交接给其他专业智能体进行具体的生图和视频生成工作。""" + "\n" + GLOBAL_ASSET_GUIDELINE,
    tools=[
        design_character,
        design_scene,
        design_prop,
        breakdown_storyboard,
        generate_keyframe_prompts,
        generate_video_prompts,
        save_text_file,
        read_text_file
    ]
)
