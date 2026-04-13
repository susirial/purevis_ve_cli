#!/usr/bin/env python3
"""LibTV provider prototype test script.

This is a standalone prototype that follows the provider/orchestrator split:
- provider only exposes stable atomic capabilities
- composite image capabilities are implemented as constrained wrappers
- unsupported capabilities fail explicitly

Supported in this prototype:
- generate_image
- generate_video
- query_task_status
- generate_reference_image (fixed Lib Nano 2)
- generate_multi_view (fixed Lib Nano 2)
- generate_prop_three_view_sheet (fixed Lib Nano 2)
- generate_storyboard_grid_sheet (fixed Lib Nano Pro)

Test commands in this file:
- multi_view_test: image-only test for character multi-view with Lib Nano 2
- video_test: 5-second video generation test
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBTV_SCRIPTS_DIR = os.path.join(ROOT_DIR, "skills", "libtv-skill", "scripts")
if LIBTV_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, LIBTV_SCRIPTS_DIR)

from _common import build_project_url, change_project, create_session, query_session  # type: ignore
from download_results import extract_urls_from_messages  # type: ignore
from upload_file import upload_file  # type: ignore


class FeatureUnavailableError(Exception):
    pass


class ValidationError(Exception):
    pass


def _download_file(url: str, output_path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "LibTVPrototypeProvider/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(output_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)


class LibTVPrototypeProvider(object):
    supports_reference = True
    supports_multi_view = True
    supports_expression = False
    supports_pose = False

    IMAGE_MODELS = {
        "lib_nano_2": "Lib Nano 2",
        "lib_nano_pro": "Lib Nano Pro",
    }
    VIDEO_MODELS = {
        "seedance_2_0": "Seedance 2.0",
        "seedance_2_0_fast": "Seedance 2.0 Fast",
        "kling_o3": "Kling O3",
    }
    IMAGE_ASPECT_RATIOS = {"1:1", "4:3", "3:4", "16:9", "9:16"}
    VIDEO_ASPECT_RATIOS = {"16:9", "9:16", "1:1"}

    def __init__(self) -> None:
        self._tasks = {}  # type: Dict[str, Dict[str, Any]]

    def capabilities(self) -> Dict[str, bool]:
        return {
            "image_generation": True,
            "video_generation": True,
            "reference_image": True,
            "multi_view": True,
            "expression_sheet": False,
            "pose_sheet": False,
            "prop_three_view_sheet": True,
            "storyboard_grid_sheet": True,
            "character_design": False,
            "scene_design": False,
            "prop_design": False,
            "storyboard_breakdown": False,
            "keyframe_prompting": False,
            "video_prompting": False,
            "image_analysis": False,
        }

    def supported_models(self) -> Dict[str, List[str]]:
        return {
            "image": sorted(self.IMAGE_MODELS.keys()),
            "video": sorted(self.VIDEO_MODELS.keys()),
        }

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
        model: str = "lib_nano_2",
        project_policy: str = "reuse",
        session_id: str = "",
    ) -> Dict[str, Any]:
        self._validate_prompt(prompt)
        normalized_model = self._validate_image_model(model)
        normalized_ratio = self._validate_image_ratio(aspect_ratio)
        reference_urls = self._upload_references(input_images or [])
        project_hint = self._maybe_change_project(project_policy)
        message = self._build_message(
            capability="生图",
            prompt=prompt,
            model_label=self.IMAGE_MODELS[normalized_model],
            aspect_ratio=normalized_ratio,
            duration=None,
            reference_urls=reference_urls,
            extra_requirements=[],
        )
        session_data = create_session(session_id=session_id or "", message=message)
        return self._register_task(
            capability="generate_image",
            model=normalized_model,
            session_data=session_data,
            project_hint=project_hint,
        )

    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
        model: str = "seedance_2_0_fast",
        project_policy: str = "reuse",
        session_id: str = "",
    ) -> Dict[str, Any]:
        self._validate_prompt(prompt)
        normalized_model = self._validate_video_model(model)
        normalized_ratio = self._validate_video_ratio(aspect_ratio)
        normalized_duration = self._validate_video_duration(duration)
        reference_urls = self._upload_references(input_images or [])
        project_hint = self._maybe_change_project(project_policy)
        extra_requirements = [
            "输出视频，不要输出图片。",
            "优先保证镜头运动与主体一致性。",
            "若支持音频生成，则按结构化要求执行；否则忽略音频要求。",
            "测试时长固定为 5 秒。" if normalized_duration == 5 else "",
            "生成音频：是" if generate_audio else "生成音频：否",
        ]
        message = self._build_message(
            capability="生视频",
            prompt=prompt,
            model_label=self.VIDEO_MODELS[normalized_model],
            aspect_ratio=normalized_ratio,
            duration=normalized_duration,
            reference_urls=reference_urls,
            extra_requirements=[item for item in extra_requirements if item],
        )
        session_data = create_session(session_id=session_id or "", message=message)
        return self._register_task(
            capability="generate_video",
            model=normalized_model,
            session_data=session_data,
            project_hint=project_hint,
        )

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            raise ValidationError("未知 task_id，当前原型仅支持查询本进程创建的任务。")

        after_seq = int(task.get("last_seq", 0) or 0)
        data = query_session(task_id, after_seq=after_seq)
        new_messages = data.get("messages", []) or []
        max_seq = after_seq
        for msg in new_messages:
            try:
                max_seq = max(max_seq, int(msg.get("seq", 0) or 0))
            except (TypeError, ValueError):
                pass

        if new_messages:
            task["messages"].extend(new_messages)
            task["last_seq"] = max_seq

        result_urls = extract_urls_from_messages(task["messages"])
        media_type = "video" if task["capability"] == "generate_video" else "image"
        outputs = [{"media_type": media_type, "url": url} for url in result_urls]
        status = "succeeded" if result_urls else "running"

        response = {
            "task_id": task_id,
            "provider": "libtv",
            "capability": task["capability"],
            "model": task["model"],
            "status": status,
            "session_id": task["session_id"],
            "project_id": task["project_uuid"],
            "project_url": task["project_url"],
            "outputs": outputs,
            "message_count": len(task["messages"]),
            "last_seq": task["last_seq"],
        }
        if new_messages:
            response["new_messages"] = new_messages
        return response

    def generate_reference_image(
        self,
        prompt: str,
        entity_type: str,
        reference_variant: str = "pure_character",
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        entity_label = (entity_type or "角色").strip()
        variant_label = (reference_variant or "pure_character").strip()
        full_prompt = (
            prompt.strip()
            + "\n"
            + "请生成高一致性的参考图。"
            + "\n"
            + "要求：单主体、纯净背景、主体完整可见、细节清晰。"
            + "\n"
            + "目标实体类型：%s。参考图版本：%s。" % (entity_label, variant_label)
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio=aspect_ratio or "9:16",
            input_images=input_images,
            model="lib_nano_2",
        )

    def generate_multi_view(self, prompt: str, character_name: str, ref_image: str = "") -> Dict[str, Any]:
        display_name = (character_name or "该角色").strip()
        full_prompt = (
            prompt.strip()
            + "\n"
            + "请生成 %s 的人物多视图设定图。" % display_name
            + "\n"
            + "要求：单张画布内展示正面、侧面、背面三视图，角色身份、服装、发型、配色完全一致。"
            + "\n"
            + "背景尽量纯净，不要额外角色、不要文字、不要水印。"
        )
        input_images = [ref_image] if ref_image else None
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio="16:9",
            input_images=input_images,
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
            + "\n"
            + "请生成 %s 的工业设计三视图设定板。" % display_name
            + "\n"
            + "要求：单张图、纯净背景、正面/侧面/背面三视图均匀排布，不要文字、不要水印。"
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
        normalized_count = panel_count if panel_count in (4, 6, 8, 9, 12, 16, 25) else 16
        full_prompt = (
            prompt.strip()
            + "\n"
            + "请生成单张故事板拼图，严格为 %d 宫格布局。" % normalized_count
            + "\n"
            + "要求：整合在同一张画布内，每格是完整画面，不要文字、不要分镜编号、不要水印。"
        )
        return self.generate_image(
            prompt=full_prompt,
            aspect_ratio=aspect_ratio or "1:1",
            input_images=input_images,
            model="lib_nano_pro",
        )

    def generate_expression_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持表情表生成，请走上层编排能力。")

    def generate_pose_sheet(self, prompt: str, character_name: str, ref_image: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持姿势表生成，请走上层编排能力。")

    def design_character(
        self,
        character_name: str,
        character_brief: str,
        style: str,
        story_context: str = "",
        reference_variant: str = "pure_character",
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持角色设计，请走规划/编排层。")

    def design_scene(self, scene_name: str, scene_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持场景设计，请走规划/编排层。")

    def design_prop(self, prop_name: str, prop_brief: str, style: str, story_context: str = "") -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持道具设计，请走规划/编排层。")

    def breakdown_storyboard(self, script: str, aspect_ratio: str, style: str, target_duration: float) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持分镜拆解，请走规划/编排层。")

    def generate_keyframe_prompts(
        self,
        segments: List[Any],
        entity_names: List[str],
        aspect_ratio: str,
        style: str,
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持关键帧提示词生成，请走规划/编排层。")

    def generate_video_prompts(
        self,
        segments: List[Any],
        entity_names: List[str],
        aspect_ratio: str,
        style: str,
    ) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持视频提示词生成，请走规划/编排层。")

    def analyze_image(self, image_url_or_path: str, analyze_type: str) -> Dict[str, Any]:
        raise FeatureUnavailableError("LibTV 原型 provider 暂不支持图像分析，请走独立分析能力。")

    def wait_for_completion(self, task_id: str, timeout_sec: int = 300, poll_interval_sec: int = 8) -> Dict[str, Any]:
        deadline = time.time() + timeout_sec
        last_status = None
        while time.time() < deadline:
            status = self.query_task_status(task_id)
            last_status = status
            if status["status"] == "succeeded":
                return status
            time.sleep(max(1, poll_interval_sec))

        if not last_status:
            last_status = self.query_task_status(task_id)
        last_status["status"] = "timeout"
        return last_status

    def download_outputs(self, task_id: str, output_dir: str) -> Dict[str, Any]:
        status = self.query_task_status(task_id)
        outputs = status.get("outputs", [])
        if not outputs:
            return {"output_dir": output_dir, "downloaded": [], "total": 0}

        os.makedirs(output_dir, exist_ok=True)
        downloaded = []
        errors = []
        for index, output in enumerate(outputs, 1):
            url = output.get("url", "")
            if not url:
                continue
            ext = os.path.splitext(url.split("?")[0])[-1] or (".mp4" if output["media_type"] == "video" else ".png")
            filename = "%s_%02d%s" % (output["media_type"], index, ext)
            target_path = os.path.join(output_dir, filename)
            try:
                _download_file(url, target_path)
                downloaded.append(target_path)
            except (OSError, urllib.error.URLError) as exc:
                errors.append({"file": target_path, "error": str(exc)})

        response = {"output_dir": output_dir, "downloaded": downloaded, "total": len(downloaded)}
        if errors:
            response["errors"] = errors
        return response

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

    def _register_task(
        self,
        capability: str,
        model: str,
        session_data: Dict[str, Any],
        project_hint: Optional[str],
    ) -> Dict[str, Any]:
        session_id = session_data.get("sessionId", "")
        if not session_id:
            raise ValidationError("LibTV 未返回 sessionId。")

        project_uuid = session_data.get("projectUuid", "") or (project_hint or "")
        project_url = build_project_url(project_uuid)
        self._tasks[session_id] = {
            "session_id": session_id,
            "project_uuid": project_uuid,
            "project_url": project_url,
            "capability": capability,
            "model": model,
            "messages": [],
            "last_seq": 0,
        }
        return {
            "task_id": session_id,
            "provider": "libtv",
            "capability": capability,
            "model": model,
            "status": "submitted",
            "session_id": session_id,
            "project_id": project_uuid,
            "project_url": project_url,
        }

    def _maybe_change_project(self, project_policy: str) -> Optional[str]:
        normalized = (project_policy or "reuse").strip().lower()
        if normalized not in ("reuse", "new"):
            raise ValidationError("project_policy 仅支持 reuse 或 new。")
        if normalized == "new":
            data = change_project()
            return data.get("projectUuid", "")
        return None

    def _upload_references(self, paths: List[str]) -> List[str]:
        urls = []
        for path in paths:
            if not path:
                continue
            if path.startswith("http://") or path.startswith("https://"):
                urls.append(path)
                continue
            try:
                data = upload_file(path)
            except SystemExit as exc:
                raise ValidationError("参考素材上传失败：%s" % path) from exc
            url = data.get("url", "")
            if not url:
                raise ValidationError("参考素材上传后未返回 URL：%s" % path)
            urls.append(url)
        return urls

    def _validate_prompt(self, prompt: str) -> None:
        if not (prompt or "").strip():
            raise ValidationError("prompt 不能为空。")

    def _validate_image_model(self, model: str) -> str:
        normalized = (model or "").strip().lower()
        if normalized not in self.IMAGE_MODELS:
            raise ValidationError("不支持的生图模型：%s" % model)
        return normalized

    def _validate_video_model(self, model: str) -> str:
        normalized = (model or "").strip().lower()
        if normalized not in self.VIDEO_MODELS:
            raise ValidationError("不支持的生视频模型：%s" % model)
        return normalized

    def _validate_image_ratio(self, aspect_ratio: str) -> str:
        normalized = (aspect_ratio or "").strip()
        if not normalized:
            return "1:1"
        if normalized not in self.IMAGE_ASPECT_RATIOS:
            raise ValidationError("不支持的生图画幅比例：%s" % aspect_ratio)
        return normalized

    def _validate_video_ratio(self, aspect_ratio: str) -> str:
        normalized = (aspect_ratio or "16:9").strip()
        if normalized not in self.VIDEO_ASPECT_RATIOS:
            raise ValidationError("不支持的生视频画幅比例：%s" % aspect_ratio)
        return normalized

    def _validate_video_duration(self, duration: int) -> int:
        try:
            normalized = int(duration)
        except (TypeError, ValueError):
            raise ValidationError("视频时长必须是整数。")
        if normalized < 4 or normalized > 15:
            raise ValidationError("视频时长必须在 4 到 15 秒之间。")
        return normalized


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LibTV provider 原型测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试人物多视图（固定 Lib Nano 2）
  python3 libtv_provider_test.py multi_view_test \\
    --character-name "白发剑士" \\
    --ref-image /path/to/ref.png \\
    --prompt "参考这张图，生成角色标准三视图设定图"

  # 测试 5 秒视频（默认 Seedance 2.0 Fast）
  python3 libtv_provider_test.py video_test \\
    --prompt "一个女孩站在海边，轻风吹动发丝，镜头缓慢推进" \\
    --ref-file /path/to/ref.png
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    multi_view = subparsers.add_parser("multi_view_test", help="测试人物多视图，固定 Lib Nano 2")
    multi_view.add_argument("--character-name", required=True, help="角色名称")
    multi_view.add_argument("--ref-image", default="", help="可选，参考图，本地路径或 URL")
    multi_view.add_argument("--prompt", required=True, help="用户原始需求")
    multi_view.add_argument("--project-policy", default="reuse", choices=["reuse", "new"], help="项目策略，默认 reuse")
    multi_view.add_argument("--timeout", type=int, default=240, help="最长等待秒数，默认 240")
    multi_view.add_argument("--poll-interval", type=int, default=8, help="轮询间隔秒数，默认 8")
    multi_view.add_argument("--output-dir", default="", help="可选，下载输出目录")

    video = subparsers.add_parser("video_test", help="测试 5 秒视频生成")
    video.add_argument("--prompt", required=True, help="用户原始需求")
    video.add_argument("--model", default="seedance_2_0_fast", choices=["seedance_2_0", "seedance_2_0_fast", "kling_o3"], help="生视频模型")
    video.add_argument("--ref-file", action="append", default=[], help="可选，参考图片或参考视频，可重复传入")
    video.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16", "1:1"], help="视频画幅比例")
    video.add_argument("--duration", type=int, default=5, help="视频时长，范围 4 到 15 秒，默认 5")
    video.add_argument("--project-policy", default="reuse", choices=["reuse", "new"], help="项目策略，默认 reuse")
    video.add_argument("--timeout", type=int, default=420, help="最长等待秒数，默认 420")
    video.add_argument("--poll-interval", type=int, default=8, help="轮询间隔秒数，默认 8")
    video.add_argument("--output-dir", default="", help="可选，下载输出目录")

    return parser


def _print_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    provider = LibTVPrototypeProvider()

    if args.command == "multi_view_test":
        submitted = provider.generate_multi_view(
            prompt=args.prompt,
            character_name=args.character_name,
            ref_image=args.ref_image,
        )
        if args.project_policy == "new":
            submitted = provider.generate_image(
                prompt=(
                    args.prompt.strip()
                    + "\n请生成 %s 的人物多视图设定图。\n要求：单张画布内展示正面、侧面、背面三视图，角色身份、服装、发型、配色完全一致。\n背景尽量纯净，不要额外角色、不要文字、不要水印。"
                    % args.character_name.strip()
                ),
                aspect_ratio="16:9",
                input_images=[args.ref_image] if args.ref_image else None,
                model="lib_nano_2",
                project_policy="new",
            )
        _print_json({"submitted": submitted})
        final_status = provider.wait_for_completion(
            submitted["task_id"],
            timeout_sec=args.timeout,
            poll_interval_sec=args.poll_interval,
        )
        result = {"final_status": final_status}
        if args.output_dir and final_status.get("status") == "succeeded":
            result["download"] = provider.download_outputs(submitted["task_id"], args.output_dir)
        _print_json(result)
        return

    if args.command == "video_test":
        submitted = provider.generate_video(
            prompt=args.prompt,
            input_images=args.ref_file,
            duration=args.duration,
            aspect_ratio=args.aspect_ratio,
            generate_audio=False,
            model=args.model,
            project_policy=args.project_policy,
        )
        _print_json({"submitted": submitted})
        final_status = provider.wait_for_completion(
            submitted["task_id"],
            timeout_sec=args.timeout,
            poll_interval_sec=args.poll_interval,
        )
        result = {"final_status": final_status}
        if args.output_dir and final_status.get("status") == "succeeded":
            result["download"] = provider.download_outputs(submitted["task_id"], args.output_dir)
        _print_json(result)
        return

    raise ValidationError("未知命令。")


if __name__ == "__main__":
    main()
