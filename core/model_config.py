import json
import os
from typing import Any, Dict

DEFAULT_AGENT_MODEL_PROVIDER = "openai"
DEFAULT_AGENT_MODEL_NAME = "doubao-seed-2-0-pro-260215"
DEFAULT_AGENT_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_TOOL_VISION_ANALYZER_PROVIDER = "openai"
DEFAULT_TOOL_VISION_ANALYZER_NAME = "doubao-seed-2-0-pro-260215"
DEFAULT_TOOL_VISION_ANALYZER_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_VOLCENGINE_ARK_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_TOOL_TEXT_TEMPERATURE = 0.45
DEFAULT_TOOL_TEMPERATURES: Dict[str, float] = {
    "DESIGN_CHARACTER": 0.75,
    "DESIGN_SCENE": 0.65,
    "DESIGN_PROP": 0.60,
    "BREAKDOWN_STORYBOARD": 0.40,
    "GENERATE_KEYFRAME_PROMPTS": 0.45,
    "GENERATE_VIDEO_PROMPTS": 0.45,
    "VISION_ANALYZER": 0.15,
}
                                  

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


def _parse_float(raw_value: str | None, env_name: str, minimum: float = 0.0, maximum: float = 2.0) -> float | None:
    if raw_value is None:
        return None

    try:
        parsed_value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} 必须是合法数字。") from exc

    if not minimum <= parsed_value <= maximum:
        raise ValueError(f"{env_name} 必须位于 {minimum} 到 {maximum} 之间。")

    return parsed_value


def _pick_env_value(*env_names: str) -> str | None:
    for env_name in env_names:
        value = _get_env_value(env_name)
        if value:
            return value
    return None


def _build_model_config(
    primary_prefix: str,
    fallback_prefixes: list[str],
    default_provider: str,
    default_name: str,
    default_api_base: str,
) -> Dict[str, Any]:
    prefixes = [primary_prefix, *fallback_prefixes]

    model_name = _pick_env_value(*[f"{prefix}_NAME" for prefix in prefixes]) or default_name
    model_provider = _pick_env_value(*[f"{prefix}_PROVIDER" for prefix in prefixes]) or default_provider
    model_api_base = _pick_env_value(*[f"{prefix}_API_BASE" for prefix in prefixes]) or default_api_base
    model_api_key = _pick_env_value(*[f"{prefix}_API_KEY" for prefix in prefixes])

    extra_config_env_names = [f"{prefix}_EXTRA_CONFIG" for prefix in prefixes]
    raw_extra_config = _pick_env_value(*extra_config_env_names)
    model_extra_config = _parse_extra_config(raw_extra_config, extra_config_env_names[0])

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


def build_agent_model_config(agent_name: str) -> Dict[str, Any]:
    agent_key = agent_name.upper().replace("-", "_")
    return _build_model_config(
        primary_prefix=f"MODEL_{agent_key}",
        fallback_prefixes=["MODEL_AGENT"],
        default_provider=DEFAULT_AGENT_MODEL_PROVIDER,
        default_name=DEFAULT_AGENT_MODEL_NAME,
        default_api_base=DEFAULT_AGENT_MODEL_API_BASE,
    )


def build_tool_text_model_config() -> Dict[str, Any]:
    return _build_model_config(
        primary_prefix="MODEL_TOOL_TEXT",
        fallback_prefixes=["MODEL_AGENT"],
        default_provider=DEFAULT_AGENT_MODEL_PROVIDER,
        default_name=DEFAULT_AGENT_MODEL_NAME,
        default_api_base=DEFAULT_AGENT_MODEL_API_BASE,
    )


def build_tool_vision_analyzer_model_config() -> Dict[str, Any]:
    return _build_model_config(
        primary_prefix="MODEL_TOOL_VISION_ANALYZER",
        fallback_prefixes=[],
        default_provider=DEFAULT_TOOL_VISION_ANALYZER_PROVIDER,
        default_name=DEFAULT_TOOL_VISION_ANALYZER_NAME,
        default_api_base=DEFAULT_TOOL_VISION_ANALYZER_API_BASE,
    )


def build_volcengine_ark_api_config() -> Dict[str, str]:
    api_base = (
        _get_env_value("VOLCENGINE_ARK_API_BASE")
        or _get_env_value("MODEL_TOOL_VISION_ANALYZER_API_BASE")
        or _get_env_value("ARK_API_BASE")
        or DEFAULT_VOLCENGINE_ARK_API_BASE
    )
    api_key = (
        _get_env_value("VOLCENGINE_ARK_API_KEY")
        or _get_env_value("MODEL_TOOL_VISION_ANALYZER_API_KEY")
        or _get_env_value("MODEL_AGENT_API_KEY")
        or ""
    )

    return {
        "api_base": api_base,
        "api_key": api_key,
    }


def get_tool_temperature(tool_name: str) -> float:
    tool_key = tool_name.upper().replace("-", "_")

    if tool_key == "VISION_ANALYZER":
        env_names = ["MODEL_TOOL_VISION_ANALYZER_TEMPERATURE"]
        default_temperature = DEFAULT_TOOL_TEMPERATURES["VISION_ANALYZER"]
    else:
        env_names = [
            f"MODEL_TOOL_{tool_key}_TEMPERATURE",
            "MODEL_TOOL_TEXT_TEMPERATURE_DEFAULT",
        ]
        default_temperature = DEFAULT_TOOL_TEMPERATURES.get(tool_key, DEFAULT_TOOL_TEXT_TEMPERATURE)

    raw_value = _pick_env_value(*env_names)
    parsed_value = _parse_float(raw_value, env_names[0]) if raw_value is not None else None
    return parsed_value if parsed_value is not None else default_temperature
