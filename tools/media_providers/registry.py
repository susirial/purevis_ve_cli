from __future__ import annotations

import os
from typing import Callable, Dict, Type

from core.model_config import build_volcengine_ark_api_config
from tools.media_providers.base import BaseMediaProvider, FeatureUnavailableError


_PROVIDERS: Dict[str, Type[BaseMediaProvider]] = {}


def register_provider(name: str) -> Callable[[Type[BaseMediaProvider]], Type[BaseMediaProvider]]:
    def decorator(provider_cls: Type[BaseMediaProvider]) -> Type[BaseMediaProvider]:
        _PROVIDERS[name] = provider_cls
        return provider_cls

    return decorator


def get_media_provider() -> BaseMediaProvider:
    provider_name = os.environ.get("MEDIA_PROVIDER", "auto").strip().lower()
    if not provider_name:
        provider_name = "auto"

    if provider_name == "auto":
        if os.environ.get("PUREVIS_API_KEY"):
            provider_name = "purevis"
        elif build_volcengine_ark_api_config().get("api_key"):
            provider_name = "volcengine_ark"
        else:
            raise FeatureUnavailableError(
                "未检测到可用的媒体生成服务：请设置 PUREVIS_API_KEY，或设置 VOLCENGINE_ARK_API_KEY。"
                "兼容场景下也支持回退使用 MODEL_TOOL_VISION_ANALYZER_API_KEY 或 MODEL_AGENT_API_KEY，"
                "并可选设置 MEDIA_PROVIDER 指定提供方。"
            )

    provider_cls = _PROVIDERS.get(provider_name)
    if not provider_cls:
        raise FeatureUnavailableError(f"未知的媒体提供方：{provider_name}")

    return provider_cls()


from tools.media_providers import purevis_provider as _purevis_provider
from tools.media_providers import volcengine_provider as _volcengine_provider
from tools.media_providers import vidu_provider as _vidu_provider
from tools.media_providers import kling_provider as _kling_provider
