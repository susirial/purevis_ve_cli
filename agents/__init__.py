GLOBAL_ASSET_GUIDELINE = """
【全局项目资产保存规范 (必读)】
整个系统生成的任何项目资产文件（包括设定文档、剧本、分镜 JSON、角色图片、视频片段等）**必须且只能**保存在项目根目录的 `output/projects/<项目名称>/` 路径下。
具体目录结构分类如下：
1. 角色/场景/物品等主体库设定与参考图：保存至 `output/projects/<项目名称>/subjects/`
2. 剧集剧本文档与分镜描述：保存至 `output/projects/<项目名称>/episodes/<剧集ID（例如 ep01）>/scripts/` 或 `output/projects/<项目名称>/episodes/<剧集ID（例如 ep01）>/storyboard/`
3. AI 视频的关键帧图片：保存至 `output/projects/<项目名称>/episodes/<剧集ID（例如 ep01）>/keyframes/`
4. 最终生成的视频片段：保存至 `output/projects/<项目名称>/episodes/<剧集ID（例如 ep01）>/video/`

绝对禁止在工作目录中随意创建类似“角色设计”、“项目”、“程序员德鲁伊”等不规范的中英文文件夹。在调用文件保存、读取和图片下载工具时，必须严格提供符合上述规范的完整相对路径（例如：`output/projects/我的短剧/subjects/林逸_参考图.jpg`）。
"""