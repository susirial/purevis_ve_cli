from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class FeatureUnavailableError(Exception):
    pass


class BaseMediaProvider(ABC):
    supports_multi_view: bool = False
    supports_expression: bool = False
    supports_pose: bool = False
    supports_reference: bool = False

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_reference_image(
        self,
        prompt: str,
        entity_type: str,
        reference_variant: str = "pure_character",
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持参考图生成。")

    def generate_multi_view(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持多视图生成。")

    def generate_expression_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持表情表生成。")

    def generate_pose_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持姿势表生成。")

    def design_character(
        self,
        character_name: str,
        character_brief: str,
        style: str,
        story_context: str = "",
        reference_variant: str = "pure_character",
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持角色设计。")

    def design_scene(self, scene_name: str, scene_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持场景设计。")

    def design_prop(self, prop_name: str, prop_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持道具设计。")

    def breakdown_storyboard(self, script: str, aspect_ratio: str, style: str, target_duration: float) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持分镜拆解。")

    def generate_keyframe_prompts(self, segments: List[Any], entity_names: List[str], aspect_ratio: str, style: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持关键帧提示词生成。")

    def generate_video_prompts(self, segments: List[Any], entity_names: List[str], aspect_ratio: str, style: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持视频提示词生成。")

    def analyze_image(self, image_url_or_path: str, analyze_type: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持图像分析。")
