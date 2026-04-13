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
_ACTIVE_SESSION_CONTEXT: Dict[str, str] = {}


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

    def _debug_log(self, event: str, **fields: Any) -> None:
        parts = [f"event={event}"]
        for key, value in fields.items():
            if value is None or value == "":
                continue
            parts.append(f"{key}={value}")
        print("[LibTV] " + " | ".join(parts))

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
        session_context = self._ensure_active_session()
        start_seq = self._get_latest_seq(session_context["session_id"])
        message = self._build_message(
            capability="生图",
            prompt=prompt,
            model_label=self.IMAGE_MODEL_LABELS[normalized_model],
            aspect_ratio=normalized_ratio,
            duration=None,
            reference_urls=reference_urls,
            extra_requirements=[],
        )
        session_data = self._create_session(message, session_id=session_context["session_id"])
        self._update_active_session_context(session_data)
        self._debug_log(
            "submit_image",
            session_id=session_context["session_id"],
            project_id=session_context["project_id"],
            start_seq=start_seq,
            model=normalized_model,
            aspect_ratio=normalized_ratio,
            ref_count=len(reference_urls),
        )
        return self._build_submitted_response(
            capability="generate_image",
            model=normalized_model,
            session_data=session_data,
            fallback_project_uuid=session_context["project_id"],
            start_seq=start_seq,
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
        session_context = self._ensure_active_session()
        start_seq = self._get_latest_seq(session_context["session_id"])
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
        session_data = self._create_session(message, session_id=session_context["session_id"])
        self._update_active_session_context(session_data)
        self._debug_log(
            "submit_video",
            session_id=session_context["session_id"],
            project_id=session_context["project_id"],
            start_seq=start_seq,
            model=normalized_model,
            aspect_ratio=normalized_ratio,
            duration=normalized_duration,
            ref_count=len(reference_urls),
        )
        return self._build_submitted_response(
            capability="generate_video",
            model=normalized_model,
            session_data=session_data,
            fallback_project_uuid=session_context["project_id"],
            start_seq=start_seq,
        )

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self._decode_task_token(task_id)
        session_id = task["session_id"]
        project_id = task.get("project_id", "")
        capability = task.get("capability", "")
        model = task.get("model", "")
        after_seq = int(task.get("after_seq", 0) or 0)

        try:
            data = self._query_session(session_id, after_seq=after_seq)
        except FeatureUnavailableError as exc:
            message = str(exc)
            if "会话不存在或无效" in message:
                self._debug_log(
                    "query_session_missing",
                    session_id=session_id,
                    project_id=project_id,
                    after_seq=after_seq,
                    capability=capability,
                    model=model,
                )
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "message": "LibTV 会话不存在或已失效，无法继续查询该任务。",
                    "result": {
                        "urls": [],
                        "url": None,
                        "outputs": [],
                        "session_id": session_id,
                        "project_id": project_id,
                        "project_url": _build_project_url(project_id),
                        "capability": capability,
                        "model": model,
                    },
                    "raw": {"error": message},
                }
            raise
        messages = data.get("messages", []) or []
        urls = self._extract_urls_from_messages(messages)
        media_type = "video" if capability == "generate_video" else "image"
        outputs = [self._build_output_item(url, media_type) for url in urls]
        status = self._normalize_status(messages, outputs)
        max_seq = self._extract_max_seq(messages)
        self._debug_log(
            "query_status",
            session_id=session_id,
            project_id=project_id,
            capability=capability,
            model=model,
            after_seq=after_seq,
            max_seq=max_seq,
            message_count=len(messages),
            url_count=len(urls),
            status=status,
        )

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
                "after_seq": after_seq,
                "max_seq": max_seq,
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
            + "\n请生成 %s 的角色多视图拼图（单张图，16:9 横向）。" % display_name
            + "\n版式要求：左侧 1/3 为一张角色大脸特写；右侧 2/3 依次为角色正面全身图、3/4 左侧面全身图、背面全身图。"
            + "\n左侧头像要求：正面视角，脸部占比大，必须包含完整头部轮廓，头发不得裁切出画框，清晰展示五官、发型与妆容细节。"
            + "\n右侧三视图要求：三个视角都必须从头到脚完整展示，包含完整发型、双手、双脚和鞋子，不得裁切肢体。"
            + "\n一致性要求：四个视图必须是同一角色、同一身份、同一服饰、同一发型、同一配色、同一画风。"
            + "\n严格参考输入参考图，不得改变角色身份，不得新增武器、坐骑、宠物、手持道具、额外角色或环境叙事元素。"
            + "\n背景必须为纯白或干净中性背景。无任何分割线、无文字、无标签、无色卡、无水印、无 UI 元素。"
        )
        self._debug_log(
            "normalize_multi_view_prompt",
            character_name=display_name,
            layout="headshot_plus_front_three_quarter_back",
            has_ref_image=bool(ref_image),
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
        start_seq: int,
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
            after_seq=start_seq,
        )
        self._debug_log(
            "task_created",
            capability=capability,
            model=model,
            session_id=session_id,
            project_id=project_uuid,
            after_seq=start_seq,
        )
        return {"task_id": token, "session_id": session_id, "project_id": project_uuid, "after_seq": start_seq}

    def _encode_task_token(
        self,
        capability: str,
        model: str,
        session_id: str,
        project_id: str,
        after_seq: int,
    ) -> str:
        payload = {
            "v": 2,
            "provider": "libtv",
            "capability": capability,
            "model": model,
            "session_id": session_id,
            "project_id": project_id,
            "after_seq": int(after_seq or 0),
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
        try:
            payload["after_seq"] = int(payload.get("after_seq", 0) or 0)
        except (TypeError, ValueError):
            payload["after_seq"] = 0
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

    def _create_session(self, message: str = "", session_id: str = "") -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if session_id:
            body["sessionId"] = session_id
        if message:
            body["message"] = message
        response = self._request_json("POST", "/openapi/session", body=body)
        return response.get("data", {}) or {}

    def _query_session(self, session_id: str, after_seq: int = 0) -> Dict[str, Any]:
        path = "/openapi/session/%s" % session_id
        if after_seq > 0:
            path += "?afterSeq=%s" % after_seq
        response = self._request_json("GET", path)
        return response.get("data", {}) or {}

    def _ensure_active_session(self) -> Dict[str, str]:
        session_id = _ACTIVE_SESSION_CONTEXT.get("session_id", "")
        project_id = _ACTIVE_SESSION_CONTEXT.get("project_id", "")
        if session_id:
            self._debug_log("reuse_session", session_id=session_id, project_id=project_id)
            return {"session_id": session_id, "project_id": project_id}

        project_id = self._change_project_for_isolation()
        session_data = self._create_session()
        session_id = session_data.get("sessionId", "")
        project_id = session_data.get("projectUuid", "") or project_id
        if not session_id:
            raise FeatureUnavailableError("LibTV 初始化会话失败，未返回 sessionId。")
        _ACTIVE_SESSION_CONTEXT["session_id"] = session_id
        _ACTIVE_SESSION_CONTEXT["project_id"] = project_id
        self._debug_log("start_session", session_id=session_id, project_id=project_id)
        return {"session_id": session_id, "project_id": project_id}

    def _update_active_session_context(self, session_data: Dict[str, Any]) -> None:
        session_id = (session_data.get("sessionId") or "").strip()
        project_id = (session_data.get("projectUuid") or "").strip()
        if session_id:
            _ACTIVE_SESSION_CONTEXT["session_id"] = session_id
        if project_id:
            _ACTIVE_SESSION_CONTEXT["project_id"] = project_id

    def _get_latest_seq(self, session_id: str) -> int:
        try:
            data = self._query_session(session_id)
        except FeatureUnavailableError as exc:
            message = str(exc)
            if "会话不存在或无效" in message:
                self._debug_log("session_invalid_reset", session_id=session_id)
                _ACTIVE_SESSION_CONTEXT.clear()
                return 0
            raise
        messages = data.get("messages", []) or []
        max_seq = self._extract_max_seq(messages)
        self._debug_log("session_seq", session_id=session_id, max_seq=max_seq, message_count=len(messages))
        return max_seq

    def _extract_max_seq(self, messages: List[Dict[str, Any]]) -> int:
        max_seq = 0
        for msg in messages:
            try:
                max_seq = max(max_seq, int(msg.get("seq", 0) or 0))
            except (TypeError, ValueError):
                continue
        return max_seq

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
