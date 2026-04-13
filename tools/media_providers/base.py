from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class FeatureUnavailableError(Exception):
    pass


def normalize_audio_mode(audio_mode: str) -> str:
    normalized = (audio_mode or "ambient_only").strip().lower()
    aliases = {
        "ambient": "ambient_only",
        "ambient_only": "ambient_only",
        "music": "ambient_only",
        "music_only": "ambient_only",
        "no_speech": "ambient_only",
        "speech": "speech",
        "voiceover": "speech",
        "dialogue": "speech",
        "dialogue_or_voiceover": "speech",
    }
    resolved = aliases.get(normalized, normalized)
    if resolved not in {"ambient_only", "speech"}:
        raise FeatureUnavailableError(
            "audio_mode 不合法：%s。仅支持 ambient_only（无台词，仅环境音/音乐）或 speech（包含口播/对白）。"
            % audio_mode
        )
    return resolved


def build_audio_mode_instruction(generate_audio: bool, audio_mode: str) -> str:
    normalized = normalize_audio_mode(audio_mode)
    if not generate_audio:
        return "音频要求：不生成音频。"
    if normalized == "ambient_only":
        return "音频要求：仅环境音/音乐，无口播、无旁白、无对白。"
    return "音频要求：包含口播/对白或旁白；如需人声内容，必须在提示词中明确写出台词或口播文本。"


class BaseMediaProvider(ABC):
    supports_multi_view: bool = False
    supports_expression: bool = False
    supports_pose: bool = False
    supports_reference: bool = False

    def capabilities(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "reference_image": self.supports_reference,
            "multi_view": self.supports_multi_view,
            "expression_sheet": self.supports_expression,
            "pose_sheet": self.supports_pose,
            "prop_three_view_sheet": False,
            "storyboard_grid_sheet": False,
            "character_design": False,
            "scene_design": False,
            "prop_design": False,
            "storyboard_breakdown": False,
            "keyframe_prompting": False,
            "video_prompting": False,
            "image_analysis": False,
        }

    def supported_models(self) -> Dict[str, List[str]]:
        return {"image": [], "video": []}

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
        model: str = "",
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
        audio_mode: str = "ambient_only",
        model: str = "",
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

    def generate_prop_three_view_sheet(
        self,
        prompt: str,
        prop_name: str = "",
        input_images: Optional[List[str]] = None,
        aspect_ratio: str = "16:9",
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持道具三视图设定板生成。")

    def generate_storyboard_grid_sheet(
        self,
        prompt: str,
        panel_count: int = 16,
        aspect_ratio: str = "1:1",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("当前媒体提供方不支持多宫格分镜拼板生成。")

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
