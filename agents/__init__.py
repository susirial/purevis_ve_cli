import json
import os
from typing import Any, Dict

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

DEFAULT_AGENT_MODEL_PROVIDER = "openai"
DEFAULT_AGENT_MODEL_NAME = "doubao-seed-2-0-pro-260215"
DEFAULT_AGENT_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"


def _get_env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _parse_extra_config(raw_value: str | None, env_name: str) -> Dict[str, Any] | None:
    if not raw_value:
        return None

    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_name} 必须是合法 JSON 对象字符串。") from exc

    if not isinstance(parsed_value, dict):
        raise ValueError(f"{env_name} 必须是 JSON 对象。")

    return parsed_value


def build_agent_model_config(agent_name: str) -> Dict[str, Any]:
    agent_key = agent_name.upper().replace("-", "_")

    model_name = _get_env_value(f"MODEL_{agent_key}_NAME") or _get_env_value("MODEL_AGENT_NAME") or DEFAULT_AGENT_MODEL_NAME
    model_provider = _get_env_value(f"MODEL_{agent_key}_PROVIDER") or _get_env_value("MODEL_AGENT_PROVIDER") or DEFAULT_AGENT_MODEL_PROVIDER
    model_api_base = _get_env_value(f"MODEL_{agent_key}_API_BASE") or _get_env_value("MODEL_AGENT_API_BASE") or DEFAULT_AGENT_MODEL_API_BASE
    model_api_key = _get_env_value(f"MODEL_{agent_key}_API_KEY") or _get_env_value("MODEL_AGENT_API_KEY")
    model_extra_config = _parse_extra_config(
        _get_env_value(f"MODEL_{agent_key}_EXTRA_CONFIG") or _get_env_value("MODEL_AGENT_EXTRA_CONFIG"),
        f"MODEL_{agent_key}_EXTRA_CONFIG",
    )

    model_config: Dict[str, Any] = {
        "model_name": model_name,
        "model_provider": model_provider,
        "model_api_base": model_api_base,
    }

    if model_api_key:
        model_config["model_api_key"] = model_api_key

    if model_extra_config:
        model_config["model_extra_config"] = model_extra_config

    return model_config
