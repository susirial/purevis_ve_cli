from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from tools.media_providers.base import BaseMediaProvider, FeatureUnavailableError
from tools.media_providers.registry import register_provider


IM_BASE = "https://im.liblib.tv"
PROJECT_CANVAS_BASE = "https://www.liblib.tv/canvas?projectId="
URL_PATTERN = re.compile(r'https://libtv-res\.liblib\.art/[^\s"\'<>]+\.(?:png|jpg|jpeg|webp|mp4|mov|webm)')
UPLOAD_ALLOWED_PREFIXES = ("image/", "video/")


def _build_project_url(project_id: str) -> str:
    if not project_id:
        return ""
    return PROJECT_CANVAS_BASE + project_id.strip()


def _urlsafe_b64encode(data: Dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _urlsafe_b64decode(token: str) -> Dict[str, Any]:
    padding = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    return json.loads(raw.decode("utf-8"))


@register_provider("libtv")
class LibTVMediaProvider(BaseMediaProvider):
    supports_multi_view = True
    supports_expression = False
    supports_pose = False
    supports_reference = True

    IMAGE_MODEL_LABELS = {
        "lib_nano_2": "Lib Nano 2",
        "lib_nano_pro": "Lib Nano Pro",
    }
    VIDEO_MODEL_LABELS = {
        "seedance_2_0": "Seedance 2.0",
        "seedance_2_0_fast": "Seedance 2.0 Fast",
        "kling_o3": "Kling O3",
    }
    IMAGE_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "4:5", "5:4", "21:9"}
    VIDEO_ASPECT_RATIOS = {"16:9", "9:16", "1:1"}
    TASK_TOKEN_PREFIX = "libtv:"

    def capabilities(self) -> Dict[str, bool]:
        data = super().capabilities()
        data.update(
            {
                "prop_three_view_sheet": True,
                "storyboard_grid_sheet": True,
            }
        )
        return data

    def supported_models(self) -> Dict[str, List[str]]:
        return {
            "image": sorted(self.IMAGE_MODEL_LABELS.keys()),
            "video": sorted(self.VIDEO_MODEL_LABELS.keys()),
        }

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
        model: str = "",
    ) -> Dict[str, Any]:
        self._validate_prompt(prompt)
        normalized_model = self._normalize_image_model(model)
        normalized_ratio = self._normalize_image_ratio(aspect_ratio)
        reference_urls = self._upload_references(input_images or [])
        project_uuid = self._change_project_for_isolation()
        message = self._build_message(
            capability="生图",
            prompt=prompt,
            model_label=self.IMAGE_MODEL_LABELS[normalized_model],
            aspect_ratio=normalized_ratio,
            duration=None,
            reference_urls=reference_urls,
            extra_requirements=[],
        )
        session_data = self._create_session(message)
        return self._build_submitted_response(
            capability="generate_image",
            model=normalized_model,
            session_data=session_data,
            fallback_project_uuid=project_uuid,
        )

    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
        model: str = "",
    ) -> Dict[str, Any]:
        self._validate_prompt(prompt)
        normalized_model = self._normalize_video_model(model)
        normalized_duration = self._normalize_video_duration(duration)
        normalized_ratio = self._normalize_video_ratio(aspect_ratio)
        reference_urls = self._upload_references(input_images or [])
        project_uuid = self._change_project_for_isolation()
        extra_requirements = [
            "输出视频，不要输出图片。",
            "优先保证镜头运动与主体一致性。",
            "生成音频：是" if generate_audio else "生成音频：否",
        ]
        message = self._build_message(
            capability="生视频",
            prompt=prompt,
            model_label=self.VIDEO_MODEL_LABELS[normalized_model],
            aspect_ratio=normalized_ratio,
            duration=normalized_duration,
            reference_urls=reference_urls,
            extra_requirements=extra_requirements,
        )
        session_data = self._create_session(message)
        return self._build_submitted_response(
            capability="generate_video",
            model=normalized_model,
            session_data=session_data,
            fallback_project_uuid=project_uuid,
        )

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self._decode_task_token(task_id)
        session_id = task["session_id"]
        project_id = task.get("project_id", "")
        capability = task.get("capability", "")
        model = task.get("model", "")

        data = self._query_session(session_id)
        messages = data.get("messages", []) or []
        urls = self._extract_urls_from_messages(messages)
        media_type = "video" if capability == "generate_video" else "image"
        outputs = [self._build_output_item(url, media_type) for url in urls]
        status = self._normalize_status(messages, outputs)

        result: Dict[str, Any] = {
            "task_id": task_id,
            "status": status,
            "result": {
                "urls": urls,
                "url": urls[0] if urls else None,
                "outputs": outputs,
                "session_id": session_id,
                "project_id": project_id,
                "project_url": _build_project_url(project_id),
                "capability": capability,
                "model": model,
            },
            "raw": {"messages": messages},
        }
        return result

    def generate_reference_image(
        self,
        prompt: str,
        entity_type: str,
        reference_variant: str = "pure_character",
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized_entity = (entity_type or "").strip().lower() or "character"
        normalized_variant = (reference_variant or "pure_character").strip().lower() or "pure_character"
        normalized_ratio = aspect_ratio or ("9:16" if normalized_entity == "character" else "1:1")
        full_prompt = (
            prompt.strip()
            + "\n请生成高一致性的参考图。"
            + "\n要求：单主体、主体完整可见、构图清晰、背景干净，便于后续一致性生成。"
            + "\n目标实体类型：%s。参考图版本：%s。" % (normalized_entity, normalized_variant)
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio=normalized_ratio,
            input_images=input_images,
            model="lib_nano_2",
        )

    def generate_multi_view(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        display_name = (character_name or "该角色").strip()
        full_prompt = (
            prompt.strip()
            + "\n请生成 %s 的人物多视图设定图。" % display_name
            + "\n要求：单张画布内展示正面、侧面、背面三视图，角色身份、服装、发型、配色完全一致。"
            + "\n背景尽量纯净，不要额外角色、不要文字、不要水印。"
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio="16:9",
            input_images=[ref_image] if ref_image else None,
            model="lib_nano_2",
        )

    def generate_prop_three_view_sheet(
        self,
        prompt: str,
        prop_name: str = "",
        input_images: Optional[List[str]] = None,
        aspect_ratio: str = "16:9",
    ) -> Dict[str, Any]:
        display_name = (prop_name or "该道具").strip()
        full_prompt = (
            prompt.strip()
            + "\n请生成 %s 的工业设计三视图设定板。" % display_name
            + "\n要求：单张图、纯净背景、正面/侧面/背面三视图均匀排布，不要文字、不要水印。"
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio=aspect_ratio or "16:9",
            input_images=input_images,
            model="lib_nano_2",
        )

    def generate_storyboard_grid_sheet(
        self,
        prompt: str,
        panel_count: int = 16,
        aspect_ratio: str = "1:1",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized_count = panel_count if panel_count in {4, 6, 8, 9, 12, 16, 25} else 16
        full_prompt = (
            prompt.strip()
            + "\n请生成单张故事板拼图，严格为 %d 宫格布局。" % normalized_count
            + "\n要求：整合在同一张画布内，每格是完整画面，不要文字、不要分镜编号、不要水印。"
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio=aspect_ratio or "1:1",
            input_images=input_images,
            model="lib_nano_pro",
        )

    def _build_submitted_response(
        self,
        capability: str,
        model: str,
        session_data: Dict[str, Any],
        fallback_project_uuid: str,
    ) -> Dict[str, Any]:
        session_id = session_data.get("sessionId", "")
        if not session_id:
            raise FeatureUnavailableError("LibTV 未返回 sessionId，无法跟踪任务。")
        project_uuid = session_data.get("projectUuid", "") or fallback_project_uuid
        token = self._encode_task_token(
            capability=capability,
            model=model,
            session_id=session_id,
            project_id=project_uuid,
        )
        return {"task_id": token}

    def _encode_task_token(
        self,
        capability: str,
        model: str,
        session_id: str,
        project_id: str,
    ) -> str:
        payload = {
            "v": 1,
            "provider": "libtv",
            "capability": capability,
            "model": model,
            "session_id": session_id,
            "project_id": project_id,
        }
        return self.TASK_TOKEN_PREFIX + _urlsafe_b64encode(payload)

    def _decode_task_token(self, task_id: str) -> Dict[str, Any]:
        if not task_id.startswith(self.TASK_TOKEN_PREFIX):
            raise FeatureUnavailableError("LibTV task_id 非法，无法解析任务上下文。")
        try:
            payload = _urlsafe_b64decode(task_id[len(self.TASK_TOKEN_PREFIX):])
        except (ValueError, json.JSONDecodeError, base64.binascii.Error) as exc:
            raise FeatureUnavailableError("LibTV task_id 解码失败。") from exc
        if payload.get("provider") != "libtv":
            raise FeatureUnavailableError("task_id 不属于 libtv provider。")
        if not payload.get("session_id"):
            raise FeatureUnavailableError("task_id 缺少 session_id。")
        return payload

    def _build_message(
        self,
        capability: str,
        prompt: str,
        model_label: str,
        aspect_ratio: str,
        duration: Optional[int],
        reference_urls: List[str],
        extra_requirements: List[str],
    ) -> str:
        lines = [
            "用户需求：",
            prompt.strip(),
            "",
            "结构化要求：",
            "- 能力：%s" % capability,
            "- 指定模型：%s" % model_label,
        ]
        if aspect_ratio:
            lines.append("- 画幅比例：%s" % aspect_ratio)
        if duration is not None:
            lines.append("- 视频时长：%s 秒" % duration)
        if reference_urls:
            lines.append("- 参考素材：")
            for url in reference_urls:
                lines.append("  - %s" % url)
        if extra_requirements:
            lines.append("- 附加要求：")
            for item in extra_requirements:
                lines.append("  - %s" % item)
        return "\n".join(lines).strip()

    def _normalize_image_model(self, model: str) -> str:
        normalized = (model or "lib_nano_2").strip().lower()
        if normalized not in self.IMAGE_MODEL_LABELS:
            raise FeatureUnavailableError("LibTV 不支持该生图模型：%s" % model)
        return normalized

    def _normalize_video_model(self, model: str) -> str:
        normalized = (model or "seedance_2_0_fast").strip().lower()
        if normalized not in self.VIDEO_MODEL_LABELS:
            raise FeatureUnavailableError("LibTV 不支持该生视频模型：%s" % model)
        return normalized

    def _normalize_image_ratio(self, aspect_ratio: str) -> str:
        normalized = (aspect_ratio or "1:1").strip()
        if normalized not in self.IMAGE_ASPECT_RATIOS:
            raise FeatureUnavailableError("LibTV 不支持该图片画幅比例：%s" % aspect_ratio)
        return normalized

    def _normalize_video_ratio(self, aspect_ratio: str) -> str:
        normalized = (aspect_ratio or "16:9").strip()
        if normalized not in self.VIDEO_ASPECT_RATIOS:
            raise FeatureUnavailableError("LibTV 不支持该视频画幅比例：%s" % aspect_ratio)
        return normalized

    def _normalize_video_duration(self, duration: int) -> int:
        try:
            normalized = int(duration)
        except (TypeError, ValueError) as exc:
            raise FeatureUnavailableError("LibTV 视频时长必须是整数。") from exc
        if normalized < 4 or normalized > 15:
            raise FeatureUnavailableError("LibTV 视频时长必须在 4 到 15 秒之间。")
        return normalized

    def _validate_prompt(self, prompt: str) -> None:
        if not (prompt or "").strip():
            raise FeatureUnavailableError("prompt 不能为空。")

    def _change_project_for_isolation(self) -> str:
        response = self._request_json("POST", "/openapi/session/change-project", body={})
        project_uuid = (response.get("data") or {}).get("projectUuid", "")
        if not project_uuid:
            raise FeatureUnavailableError("LibTV 切换项目失败，未返回 projectUuid。")
        return project_uuid

    def _create_session(self, message: str) -> Dict[str, Any]:
        response = self._request_json("POST", "/openapi/session", body={"message": message})
        return response.get("data", {}) or {}

    def _query_session(self, session_id: str) -> Dict[str, Any]:
        response = self._request_json("GET", "/openapi/session/%s" % session_id)
        return response.get("data", {}) or {}

    def _upload_references(self, items: List[str]) -> List[str]:
        urls = []
        for item in items:
            if not item:
                continue
            if item.startswith("http://") or item.startswith("https://"):
                urls.append(item)
                continue
            urls.append(self._upload_file(item))
        return urls

    def _upload_file(self, file_path: str) -> str:
        access_key = self._get_access_key()
        if not os.path.isfile(file_path):
            raise FeatureUnavailableError("LibTV 参考素材不存在：%s" % file_path)

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and not any(mime_type.startswith(prefix) for prefix in UPLOAD_ALLOWED_PREFIXES):
            raise FeatureUnavailableError("LibTV 仅支持上传图片或视频：%s" % file_path)

        boundary = "----LibTVUpload%s" % uuid.uuid4().hex
        filename = os.path.basename(file_path)
        content_type = mime_type or "application/octet-stream"
        body_parts: List[bytes] = []
        body_parts.append(("--%s\r\n" % boundary).encode("utf-8"))
        body_parts.append(b'Content-Disposition: form-data; name="accessKey"\r\n\r\n')
        body_parts.append((access_key + "\r\n").encode("utf-8"))
        body_parts.append(("--%s\r\n" % boundary).encode("utf-8"))
        body_parts.append(('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode("utf-8"))
        body_parts.append(("Content-Type: %s\r\n\r\n" % content_type).encode("utf-8"))
        with open(file_path, "rb") as f:
            body_parts.append(f.read())
        body_parts.append(b"\r\n")
        body_parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
        payload = b"".join(body_parts)

        response = self._request_raw(
            method="POST",
            path="/openapi/upload",
            data=payload,
            headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
            timeout=120,
        )
        result = json.loads(response.decode("utf-8"))
        url = (result.get("data") or {}).get("url", "")
        if not url:
            raise FeatureUnavailableError("LibTV 上传成功但未返回素材 URL。")
        return url

    def _request_json(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        raw = self._request_raw(method=method, path=path, data=data, headers=headers, timeout=timeout)
        return json.loads(raw.decode("utf-8"))

    def _request_raw(
        self,
        method: str,
        path: str,
        data: Optional[bytes],
        headers: Optional[Dict[str, str]],
        timeout: int,
    ) -> bytes:
        access_key = self._get_access_key()
        merged_headers = {"Authorization": "Bearer %s" % access_key}
        if headers:
            merged_headers.update(headers)
        url = IM_BASE.rstrip("/") + path
        req = urllib.request.Request(url, data=data, method=method, headers=merged_headers)
        last_error: Optional[Exception] = None

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                should_retry = exc.code == 429 or exc.code >= 500
                if attempt < 2 and should_retry:
                    time.sleep(1 + attempt)
                    continue
                raise FeatureUnavailableError("LibTV API 错误 %s: %s" % (exc.code, error_body)) from exc
            except (urllib.error.URLError, TimeoutError, ConnectionResetError, socket.timeout, ssl.SSLError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                break

        raise FeatureUnavailableError("LibTV 网络请求失败：%s" % last_error)

    def _get_access_key(self) -> str:
        access_key = os.environ.get("LIBTV_ACCESS_KEY", "").strip()
        if not access_key:
            raise FeatureUnavailableError("使用 libtv provider 时必须设置 LIBTV_ACCESS_KEY。")
        return access_key

    def _extract_urls_from_messages(self, messages: List[Dict[str, Any]]) -> List[str]:
        urls: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if not content or not isinstance(content, str):
                continue
            if msg.get("role") == "tool":
                try:
                    data = json.loads(content)
                except (TypeError, ValueError):
                    data = None
                if isinstance(data, dict):
                    task_result = data.get("task_result", {})
                    if isinstance(task_result, dict):
                        for img in task_result.get("images", []) or []:
                            preview = img.get("previewPath", "")
                            if preview:
                                urls.append(preview)
                        for vid in task_result.get("videos", []) or []:
                            preview = vid.get("previewPath", "") or vid.get("url", "")
                            if preview:
                                urls.append(preview)
            if msg.get("role") == "assistant":
                urls.extend(URL_PATTERN.findall(content))

        deduped: List[str] = []
        seen = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def _normalize_status(self, messages: List[Dict[str, Any]], outputs: List[Dict[str, Any]]) -> str:
        if outputs:
            return "completed"
        recent_messages = messages[-5:]
        for msg in recent_messages:
            if msg.get("role") != "tool":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("error"):
                return "failed"
        return "processing"

    def _build_output_item(self, url: str, media_type_hint: str) -> Dict[str, Any]:
        lower_url = url.lower().split("?")[0]
        media_type = media_type_hint
        if lower_url.endswith((".png", ".jpg", ".jpeg", ".webp")):
            media_type = "image"
        elif lower_url.endswith((".mp4", ".mov", ".webm")):
            media_type = "video"
        return {"media_type": media_type, "url": url}
