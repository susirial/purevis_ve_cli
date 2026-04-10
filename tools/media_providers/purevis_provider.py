from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, List, Optional

import requests

try:
    from tools.image_utils import resize_and_compress_image
except ImportError:
    def resize_and_compress_image(p, **kwargs):
        return p

from tools.media_providers.base import BaseMediaProvider, FeatureUnavailableError
from tools.media_providers.registry import register_provider


PUREVIS_BASE_URL = "https://www.purevis.cn/api/v1"


def _guess_image_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "image/jpeg"


def _encode_image_to_base64(image_path: str) -> str:
    if not os.path.exists(image_path):
        return image_path

    processed_path = resize_and_compress_image(image_path)

    with open(processed_path, "rb") as image_file:
        raw = image_file.read()
    encoded_string = base64.b64encode(raw).decode("utf-8")
    mime = _guess_image_mime(processed_path)
    return f"data:{mime};base64,{encoded_string}"


def _process_input_images(input_images: Optional[List[str]]) -> Optional[List[str]]:
    if not input_images:
        return input_images
    return [_encode_image_to_base64(img) for img in input_images]


def _request_purevis_api(endpoint: str, payload: dict = None, method: str = "POST", max_retries: int = 2) -> dict:
    api_key = os.environ.get("PUREVIS_API_KEY")
    if not api_key:
        raise FeatureUnavailableError("PUREVIS_API_KEY 环境变量未设置，无法使用 PureVis 媒体服务。")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{PUREVIS_BASE_URL}/{endpoint.lstrip('/')}"

    attempt = 0
    while attempt <= max_retries:
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=payload, timeout=60)
            elif method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=60)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            attempt += 1
            if hasattr(e, "response") and e.response is not None:
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise Exception(f"HTTP Error: {e} - Response: {getattr(e.response, 'text', '')}")
            if attempt <= max_retries:
                time.sleep(5)
            else:
                raise Exception(f"Request Error after {max_retries} retries: {e}")


@register_provider("purevis")
class PureVisMediaProvider(BaseMediaProvider):
    supports_multi_view = True
    supports_expression = True
    supports_pose = True
    supports_reference = True

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"prompt": prompt}
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if input_images:
            payload["input_images"] = _process_input_images(input_images)
        return _request_purevis_api("tools/generate-image", payload)

    def generate_reference_image(
        self,
        prompt: str,
        entity_type: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"prompt": prompt, "entity_type": entity_type}
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if input_images:
            payload["input_images"] = _process_input_images(input_images)
        return _request_purevis_api("tools/generate-reference-image", payload)

    def generate_multi_view(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        payload = {"prompt": prompt, "character_name": character_name, "ref_image": _encode_image_to_base64(ref_image)}
        return _request_purevis_api("tools/generate-multi-view", payload)

    def generate_expression_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        payload = {"prompt": prompt, "character_name": character_name, "ref_image": _encode_image_to_base64(ref_image)}
        return _request_purevis_api("tools/generate-expression-sheet", payload)

    def generate_pose_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        payload = {"prompt": prompt, "character_name": character_name, "ref_image": _encode_image_to_base64(ref_image)}
        return _request_purevis_api("tools/generate-pose-sheet", payload)

    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
        }
        if input_images:
            payload["input_images"] = _process_input_images(input_images)
        return _request_purevis_api("tools/generate-video", payload)

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        return _request_purevis_api(f"tasks/{task_id}", method="GET")

    def design_character(self, character_name: str, character_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        payload = {
            "character_name": character_name,
            "character_brief": character_brief,
            "style": style
        }
        if story_context:
            payload["story_context"] = story_context
        return _request_purevis_api("skills/design-character", payload)

    def design_scene(self, scene_name: str, scene_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        payload = {
            "scene_name": scene_name,
            "scene_brief": scene_brief,
            "style": style
        }
        if story_context:
            payload["story_context"] = story_context
        return _request_purevis_api("skills/design-scene", payload)

    def design_prop(self, prop_name: str, prop_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        payload = {
            "prop_name": prop_name,
            "prop_brief": prop_brief,
            "style": style
        }
        if story_context:
            payload["story_context"] = story_context
        return _request_purevis_api("skills/design-prop", payload)

    def breakdown_storyboard(self, script: str, aspect_ratio: str, style: str, target_duration: float) -> Dict[str, Any]:
        payload = {
            "script": script,
            "aspect_ratio": aspect_ratio,
            "style": style,
            "target_duration": target_duration
        }
        return _request_purevis_api("skills/breakdown-storyboard", payload)

    def generate_keyframe_prompts(self, segments: List[Any], entity_names: List[str], aspect_ratio: str, style: str) -> Dict[str, Any]:
        payload = {
            "segments": segments,
            "entity_names": entity_names,
            "aspect_ratio": aspect_ratio,
            "style": style
        }
        return _request_purevis_api("skills/generate-keyframe-prompts", payload)

    def generate_video_prompts(self, segments: List[Any], entity_names: List[str], aspect_ratio: str, style: str) -> Dict[str, Any]:
        payload = {
            "segments": segments,
            "entity_names": entity_names,
            "aspect_ratio": aspect_ratio,
            "style": style
        }
        return _request_purevis_api("skills/generate-video-prompts", payload)

    def analyze_image(self, image_url_or_path: str, analyze_type: str) -> Dict[str, Any]:
        if not image_url_or_path.startswith("http") and not image_url_or_path.startswith("data:image"):
            if os.path.exists(image_url_or_path):
                image_url_or_path = _encode_image_to_base64(image_url_or_path)

        payload = {
            "image_url": image_url_or_path,
            "analyze_type": analyze_type
        }
        return _request_purevis_api("skills/analyze-image", payload)
