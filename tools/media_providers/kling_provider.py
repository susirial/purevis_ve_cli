from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.media_providers.base import BaseMediaProvider, FeatureUnavailableError
from tools.media_providers.registry import register_provider


@register_provider("kling")
class KlingMediaProvider(BaseMediaProvider):
    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
        model: str = "",
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("Kling 媒体提供方尚未接入。")

    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
        model: str = "",
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("Kling 媒体提供方尚未接入。")

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("Kling 媒体提供方尚未接入。")
