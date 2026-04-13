from __future__ import annotations

from typing import Dict, List

from tools.media_providers.catalog import get_media_provider_catalog
from tools.media_providers.router import resolve_media_provider


def describe_media_capabilities() -> Dict:
    """
    返回当前系统注册的媒体 provider 目录、可用性、能力清单与模型支持情况。
    适合给 orchestrator 在做媒体后端推荐、配置引导或模型选择解释时读取。
    """
    return get_media_provider_catalog()


def suggest_media_route(capability: str, requested_model: str = "", intent_tags: List[str] = None) -> Dict:
    """
    根据 capability、可选模型与用户意图，返回建议的 provider 路由结果。

    Args:
        capability: 例如 generate_image / generate_video / generate_multi_view
        requested_model: 用户显式指定的模型名，可留空
        intent_tags: 可选意图标签，例如 ["explicit_model_control", "high_level_workflow"]
    """
    return resolve_media_provider(
        capability=capability,
        requested_model=requested_model,
        intent_tags=intent_tags or [],
    )
