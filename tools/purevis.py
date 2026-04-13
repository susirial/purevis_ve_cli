import os
import time
import json
import base64
import requests
from typing import Optional, List, Dict, Any

try:
    from tools.image_utils import resize_and_compress_image
except ImportError:
    def resize_and_compress_image(p, **kwargs): return p

from tools.media_providers.base import FeatureUnavailableError, normalize_audio_mode
from tools.media_providers.registry import (
    get_media_provider as _get_media_provider,
    get_media_provider_by_name,
)
from tools.media_providers.router import resolve_media_provider, resolve_provider_for_task

PUREVIS_BASE_URL = "https://www.purevis.cn/api/v1"


def get_media_provider():
    return _get_media_provider()


def _raise_route_error(route_result: dict) -> None:
    error = route_result.get("error", {}) if isinstance(route_result, dict) else {}
    message = error.get("message") or "媒体路由失败。"
    code = error.get("code")
    provider = error.get("provider")
    requested_model = error.get("requested_model")
    requires_env = error.get("requires_env") or []

    details = []
    if code:
        details.append(f"code={code}")
    if provider:
        details.append(f"provider={provider}")
    if requested_model:
        details.append(f"requested_model={requested_model}")
    if requires_env:
        details.append("requires_env=" + ",".join(requires_env))

    if details:
        message = f"{message} ({'; '.join(details)})"
    raise FeatureUnavailableError(message)


def _log_media_route(capability: str, provider_name: str, model_name: str = "", reason: str = "") -> None:
    parts = [f"capability={capability}", f"provider={provider_name}"]
    if model_name:
        parts.append(f"model={model_name}")
    if reason:
        parts.append(f"reason={reason}")
    print("[MediaRoute] " + " | ".join(parts))


def _resolve_provider_for_execution(capability: str, requested_model: str = "", intent_tags: Optional[List[str]] = None):
    route_result = resolve_media_provider(
        capability=capability,
        requested_model=requested_model,
        intent_tags=intent_tags or [],
    )
    if not route_result.get("ok"):
        _raise_route_error(route_result)
    provider_name = route_result["provider"]
    provider = get_media_provider_by_name(provider_name)
    effective_model = requested_model or route_result.get("model", "") or ""
    _log_media_route(
        capability=capability,
        provider_name=provider_name,
        model_name=effective_model,
        reason=route_result.get("reason", ""),
    )
    return provider, route_result


def _resolve_provider_for_task_execution(task_id: str):
    route_result = resolve_provider_for_task(task_id)
    if not route_result.get("ok"):
        _raise_route_error(route_result)
    provider_name = route_result["provider"]
    provider = get_media_provider_by_name(provider_name)
    _log_media_route(
        capability="query_task_status",
        provider_name=provider_name,
        reason=route_result.get("reason", ""),
    )
    return provider


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
    """Read a local image and return a Data URI (or pass through https URL strings)."""
    if not os.path.exists(image_path):
        return image_path  # If it's not a local file (e.g., a URL), return as is

    # 核心修复：压缩图片，防止 Base64 Payload 过大撑爆服务器网关导致 SSLEOFError
    processed_path = resize_and_compress_image(image_path)

    try:
        with open(processed_path, "rb") as image_file:
            raw = image_file.read()
        encoded_string = base64.b64encode(raw).decode("utf-8")
        # 纯 Base64 常以 "/9j/"（JPEG）开头，易被下游误判为 URL；文档支持 Data URI
        mime = _guess_image_mime(processed_path)
        return f"data:{mime};base64,{encoded_string}"
    except Exception as e:
        print(f"[Warning] Failed to encode local image {image_path}: {e}")
        return image_path

def _process_input_images(input_images: list) -> list:
    """Helper function to process a list of image paths/URLs into Base64 strings if they are local files."""
    if not input_images:
        return input_images
    return [_encode_image_to_base64(img) for img in input_images]

def _request_purevis_api(endpoint: str, payload: dict = None, method: str = "POST", max_retries: int = 2) -> dict:
    """
    Helper function to send HTTP requests to PureVis API with retry logic.
    Retries up to `max_retries` times on connection errors or 5xx server errors, sleeping 5 seconds between retries.
    """
    api_key = os.environ.get("PUREVIS_API_KEY")
    if not api_key:
        raise FeatureUnavailableError("PUREVIS_API_KEY 环境变量未设置，无法使用 PureVis 技能工具。")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
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
            error_msg = f"HTTP Error: {e}"
            if hasattr(e, 'response') and e.response is not None and e.response.text:
                error_msg += f" - Response: {e.response.text}"
            
            # 如果是 4xx 客户端错误（除了 429 频率限制），通常重试也没用，直接抛出
            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise Exception(error_msg)
            
            if attempt <= max_retries:
                print(f"[Retry {attempt}/{max_retries}] PureVis API request failed. Retrying in 5 seconds... ({error_msg})")
                time.sleep(5)
            else:
                raise Exception(f"Request Error after {max_retries} retries: {error_msg}")
        except Exception as e:
            raise Exception(f"Unexpected Request Error: {e}")

# ==========================================
# Task 3: Skill APIs (Synchronous)
# ==========================================

def _normalize_reference_variant(reference_variant: str) -> str:
    variant = (reference_variant or "pure_character").strip().lower()
    if variant in {"full", "full_character", "full_character_sheet", "complete", "complete_character"}:
        return "full_character"
    if variant in {"mounted", "with_mount", "mount"}:
        return "mounted_character"
    return "pure_character"


def _character_reference_variant_instruction(reference_variant: str) -> str:
    variant = _normalize_reference_variant(reference_variant)
    if variant == "full_character":
        return (
            "角色参考图版本要求：完整角色设定图。画面必须是单角色、单主体、9:16 竖构图、纯白背景、单张图中只出现一个完整人物，"
            "只允许一个站姿或一个默认展示姿态，禁止多视图、禁止多人拼贴、禁止角色 lineup、禁止 pose sheet、禁止 expression sheet。"
            "允许保留角色的标志性武器、手持道具、挂件或其他与身份强绑定的 props，但除非用户明确要求，不要引入坐骑或额外角色。"
        )
    if variant == "mounted_character":
        return (
            "角色参考图版本要求：带坐骑/伴生体的完整角色设定图。画面必须是 9:16 竖构图、纯白背景，以单个主角色为中心，"
            "只允许出现明确指定的坐骑、伴生物或标志性武器，禁止额外角色、禁止 crowd、禁止多视图、禁止拼贴、禁止多个不同站姿版本同时出现在一张图内。"
        )
    return (
        "角色参考图版本要求：默认纯人物参考图。画面必须是单人、单主体、全身完整展示、9:16 竖构图、纯白背景、studio lighting、单张图中只出现一个角色，"
        "只允许一个默认站姿或一个轻微转身展示姿态；禁止多视图、禁止角色设定拼板、禁止 turnaround sheet、禁止 pose sheet、禁止 expression sheet、禁止 collage、禁止同一角色出现多个不同站姿。"
        "只保留人物本体、服装、发型、体态与必要的穿戴式配饰；不得出现武器、坐骑、宠物、伴生体、额外角色、额外手持道具或环境叙事元素。"
    )


def design_character(
    character_name: str,
    character_brief: str,
    style: str,
    story_context: str = "",
    reference_variant: str = "pure_character",
) -> dict:
    """
    Generate a character t2i prompt and Chinese description.
    
    Args:
        character_name: Name of the character.
        character_brief: Brief description of the character.
        style: Visual style (e.g., "Japanese anime", "realistic").
        story_context: Optional context of the story.
        reference_variant: pure_character | full_character | mounted_character
    """
    provider, _ = _resolve_provider_for_execution(
        capability="design_character",
        intent_tags=["high_level_workflow"],
    )
    variant_instruction = _character_reference_variant_instruction(reference_variant)
    merged_story_context = f"{story_context}\n{variant_instruction}".strip() if story_context else variant_instruction
    return provider.design_character(
        character_name=character_name,
        character_brief=character_brief,
        style=style,
        story_context=merged_story_context,
        reference_variant=_normalize_reference_variant(reference_variant),
    )

def design_scene(scene_name: str, scene_brief: str, style: str, story_context: str = "") -> dict:
    """
    Generate a scene t2i prompt and Chinese description.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="design_scene",
        intent_tags=["high_level_workflow"],
    )
    return provider.design_scene(
        scene_name=scene_name,
        scene_brief=scene_brief,
        style=style,
        story_context=story_context
    )

def design_prop(prop_name: str, prop_brief: str, style: str, story_context: str = "") -> dict:
    """
    Generate a prop t2i prompt and Chinese description.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="design_prop",
        intent_tags=["high_level_workflow"],
    )
    return provider.design_prop(
        prop_name=prop_name,
        prop_brief=prop_brief,
        style=style,
        story_context=story_context
    )

def breakdown_storyboard(script: str, aspect_ratio: str, style: str, target_duration: float) -> dict:
    """
    Break down a script into structured storyboard segments with shot timelines.
    
    Args:
        script: The story script.
        aspect_ratio: 16:9 | 9:16 | 1:1
        style: Visual style.
        target_duration: Expected duration in seconds (10-300).
    """
    provider, _ = _resolve_provider_for_execution(
        capability="breakdown_storyboard",
        intent_tags=["high_level_workflow"],
    )
    return provider.breakdown_storyboard(
        script=script,
        aspect_ratio=aspect_ratio,
        style=style,
        target_duration=target_duration
    )

def generate_keyframe_prompts(segments: list, entity_names: list, aspect_ratio: str, style: str) -> dict:
    """
    Generate per-segment keyframe t2i prompts with grid layout instructions.
    
    Args:
        segments: 必须是一个包含具体剧本情节或画面分镜描述的列表（例如从 `breakdown_storyboard` 返回的结果）。严禁传入空列表或无实质剧情内容的参数，否则接口会报错 INTENT_REJECTED。
        entity_names: List of entity names to be included.
        aspect_ratio: 16:9 | 9:16 | 1:1
        style: Visual style.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_keyframe_prompts",
        intent_tags=["high_level_workflow"],
    )
    return provider.generate_keyframe_prompts(
        segments=segments,
        entity_names=entity_names,
        aspect_ratio=aspect_ratio,
        style=style
    )

def generate_video_prompts(segments: list, entity_names: list, aspect_ratio: str, style: str) -> dict:
    """
    Generate per-segment video timeline prompts and recommended merged clip plans.
    
    Args:
        segments: 必须是一个包含具体剧本情节或画面分镜描述的列表（例如从 `breakdown_storyboard` 返回的结果）。严禁传入空列表或无实质剧情内容的参数，否则接口会报错 INTENT_REJECTED。
        entity_names: List of entity names to be included.
        aspect_ratio: 16:9 | 9:16 | 1:1
        style: Visual style.

    Returns:
        通常包含逐分镜 `prompts`，以及一份 `recommended_video_groups`。
        后者用于把 2-5 个相邻分镜按连续动作、统一场景和统一光影逻辑合并成一个 8-15 秒的较长视频段，
        更适合 Kling O3、Seedance 2.0 这类支持更长连贯镜头的视频模型。
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_video_prompts",
        intent_tags=["high_level_workflow"],
    )
    return provider.generate_video_prompts(
        segments=segments,
        entity_names=entity_names,
        aspect_ratio=aspect_ratio,
        style=style
    )

def analyze_image(image_url_or_path: str, analyze_type: str) -> dict:
    """
    Analyze an image and extract structured information or describe it in detail. (Asynchronous)
    This endpoint returns immediately with a task id.
    
    Args:
        image_url_or_path: HTTP(S) URL, or Local File Path (e.g. output/projects/...), or Base64 Data URI. The tool will automatically convert local paths to Base64.
        analyze_type: FULL, CHARACTER, ENVIRONMENT, or READ_IMAGE.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="analyze_image",
        intent_tags=["high_level_workflow"],
    )
    return provider.analyze_image(
        image_url_or_path=image_url_or_path,
        analyze_type=analyze_type
    )

# ==========================================
# Task 4: Tool APIs (Asynchronous)
# ==========================================

def generate_image(prompt: str, aspect_ratio: str = "", input_images: list = None, model: str = "") -> dict:
    """
    Submit a general-purpose image generation task (Text-to-Image or Image-to-Image).
    Returns task_id to poll later.
    
    Args:
        prompt: 提示词描述。
        aspect_ratio: 画幅比，例如 "16:9"、"9:16"、"1:1" 等。
        input_images: 【重要】如果要进行图生图（如参考已有的角色/场景图片），请将该图片的本地路径（如 "output/projects/.../xxx.jpg"）作为一个字符串放入此列表中传入（例如：["output/.../img.jpg"]）。工具会自动读取并转为 Base64。如果不使用图生图，留空即可。
        model: 可选，显式指定底层图片模型。不同 provider 仅接受自身支持的模型名。
    """
    intent_tags = ["explicit_model_control"] if model else []
    provider, route_result = _resolve_provider_for_execution(
        capability="generate_image",
        requested_model=model,
        intent_tags=intent_tags,
    )
    effective_model = model or route_result.get("model", "") or ""
    return provider.generate_image(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
        model=effective_model,
    )

def generate_reference_image(
    prompt: str,
    entity_type: str,
    reference_variant: str = "pure_character",
    aspect_ratio: str = "",
    input_images: list = None,
) -> dict:
    """
    Submit a reference sheet generation task with composition constraints.
    
    Args:
        prompt: 提示词描述。
        entity_type: character | scene | prop
        reference_variant: 角色参考图模式，支持 pure_character | full_character | mounted_character
        aspect_ratio: 画幅比
        input_images: 如果需要基于已有图片生成参考图，可传入本地路径列表（同 generate_image）。
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_reference_image",
        intent_tags=["standardized_layout"],
    )
    normalized_variant = _normalize_reference_variant(reference_variant)
    target_aspect_ratio = aspect_ratio
    if (entity_type or "").strip().lower() == "character" and not target_aspect_ratio:
        target_aspect_ratio = "9:16"
    return provider.generate_reference_image(
        prompt=prompt,
        entity_type=entity_type,
        reference_variant=normalized_variant,
        aspect_ratio=target_aspect_ratio,
        input_images=input_images,
    )

def generate_multi_view(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character multi-view turnaround sheet generation task.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_multi_view",
        intent_tags=["standardized_layout"],
    )
    return provider.generate_multi_view(prompt=prompt, character_name=character_name, ref_image=ref_image)

def generate_expression_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character expression sheet generation task.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_expression_sheet",
        intent_tags=["standardized_layout"],
    )
    return provider.generate_expression_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)

def generate_pose_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character pose sheet generation task.
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_pose_sheet",
        intent_tags=["standardized_layout"],
    )
    return provider.generate_pose_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)


def generate_prop_three_view_sheet(
    prompt: str,
    prop_name: str = "",
    input_images: list = None,
    aspect_ratio: str = "16:9",
) -> dict:
    """
    Submit a single-canvas industrial three-view prop sheet generation task.

    Args:
        prompt: 提示词描述，建议已包含风格与材质描述。
        prop_name: 道具名称，用于补充版式说明。
        input_images: 如果需要参考现有道具图片，可传入本地路径列表。
        aspect_ratio: 画幅比，默认 16:9 横向以容纳三视图排版。
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_prop_three_view_sheet",
        intent_tags=["standardized_layout"],
    )
    return provider.generate_prop_three_view_sheet(
        prompt=prompt,
        prop_name=prop_name,
        input_images=input_images,
        aspect_ratio=aspect_ratio,
    )


def generate_storyboard_grid_sheet(
    prompt: str,
    panel_count: int = 16,
    aspect_ratio: str = "1:1",
    input_images: list = None,
) -> dict:
    """
    Submit a single-canvas storyboard contact-sheet generation task.

    Args:
        prompt: 提示词描述，建议已融合每格的镜头说明与连续性约束。
        panel_count: 宫格数，当前推荐 16 或 25，也兼容少量常见多格布局。
        aspect_ratio: 画幅比，默认 1:1 以适配 4x4 / 5x5 网格。
        input_images: 如果需要参考已有角色或场景图片，可传入本地路径列表。
    """
    provider, _ = _resolve_provider_for_execution(
        capability="generate_storyboard_grid_sheet",
        intent_tags=["standardized_layout"],
    )
    return provider.generate_storyboard_grid_sheet(
        prompt=prompt,
        panel_count=panel_count,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
    )

def generate_video(
    prompt: str,
    input_images: list = None,
    duration: int = 12,
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
    audio_mode: str = "ambient_only",
    model: str = "",
) -> dict:
    """
    Submit a video generation task.
    
    Args:
        prompt: 提示词描述。
        input_images: 【重要】最多包含2个本地图片路径的列表，默认语义是“参考素材”，工具会自动读取并转为 Base64。
            如果上游已经明确指定关键帧或镜头图，优先传入该关键帧。
            如果没有明确关键帧，而同一主体同时存在“多视图设定图”和“纯角色参考图”，默认优先使用“多视图设定图”作为 input_images。
            只有在用户明确要求“首帧/尾帧控制”，且当前 provider 支持双图时，才将双图解释为首帧参考 + 尾帧参考；否则应视为普通参考素材。
        duration: 视频时长（秒）。不同 provider 支持范围不同；当前 LibTV 为 4-15 秒，默认 12。
            调用前建议先通过 suggest_media_route / describe_media_capabilities 预检当前路由的时长约束。
        aspect_ratio: 画幅比，支持 '16:9', '9:16', '1:1' 等，默认 '16:9'。
        generate_audio: 是否生成音频，默认 True。
        audio_mode: 音频模式。`ambient_only` 表示无台词，仅环境音/音乐；`speech` 表示包含口播/旁白/对白。
        model: 可选，显式指定底层视频模型。不同 provider 仅接受自身支持的模型名。
    """
    intent_tags = ["explicit_model_control"] if model else []
    provider, route_result = _resolve_provider_for_execution(
        capability="generate_video",
        requested_model=model,
        intent_tags=intent_tags,
    )
    effective_model = model or route_result.get("model", "") or ""
    normalized_audio_mode = normalize_audio_mode(audio_mode)
    try:
        return provider.generate_video(
            prompt=prompt,
            input_images=input_images,
            duration=duration,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
            audio_mode=normalized_audio_mode,
            model=effective_model,
        )
    except FeatureUnavailableError as exc:
        provider_name = route_result.get("provider", "") or "unknown_provider"
        model_name = effective_model or "default"
        raise FeatureUnavailableError(
            "当前视频任务已路由到 %s / %s，duration=%s，aspect_ratio=%s，generate_audio=%s，audio_mode=%s。%s"
            % (provider_name, model_name, duration, aspect_ratio, generate_audio, normalized_audio_mode, str(exc))
        ) from exc

def query_task_status(task_id: str) -> dict:
    """
    Query task status and result by task_id.
    """
    provider = _resolve_provider_for_task_execution(task_id)
    return provider.query_task_status(task_id)


def _extract_query_error(raw_payload: Any) -> str:
    if isinstance(raw_payload, dict):
        direct_error = raw_payload.get("error")
        if direct_error:
            return str(direct_error)
        messages = raw_payload.get("messages") or []
        if isinstance(messages, list):
            for item in reversed(messages[-5:]):
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                try:
                    parsed = json.loads(content)
                except (TypeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    if parsed.get("error"):
                        return str(parsed.get("error"))
                    if parsed.get("isError"):
                        text_parts = []
                        for block in parsed.get("content") or []:
                            if isinstance(block, dict) and block.get("text"):
                                text_parts.append(str(block.get("text")))
                        if text_parts:
                            return " | ".join(text_parts)
                        return json.dumps(parsed, ensure_ascii=False)
    return ""


def _build_query_debug_payload(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {"raw_result": result}
    result_payload = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
    raw_payload = result.get("raw", {}) if isinstance(result.get("raw"), dict) else {}
    messages = raw_payload.get("messages") or []
    tail_messages = messages[-3:] if isinstance(messages, list) else []
    return {
        "task_id": result.get("task_id"),
        "status": result.get("status"),
        "message": result.get("message"),
        "result": {
            "session_id": result_payload.get("session_id"),
            "project_id": result_payload.get("project_id"),
            "project_url": result_payload.get("project_url"),
            "capability": result_payload.get("capability"),
            "model": result_payload.get("model"),
            "after_seq": result_payload.get("after_seq"),
            "max_seq": result_payload.get("max_seq"),
            "url_count": len(result_payload.get("urls") or []),
            "url": result_payload.get("url"),
        },
        "raw_error": _extract_query_error(raw_payload),
        "raw_messages_tail": tail_messages,
    }


def _should_retry_libtv_transient_failure(task_id: str, result: Any) -> bool:
    if not isinstance(task_id, str) or not task_id.startswith("libtv:"):
        return False
    if not isinstance(result, dict):
        return False
    if result.get("status") != "failed":
        return False
    raw_payload = result.get("raw", {}) if isinstance(result.get("raw"), dict) else {}
    error_text = " ".join(
        [
            str(result.get("message") or ""),
            str(raw_payload.get("error") or ""),
            _extract_query_error(raw_payload),
        ]
    ).lower()
    return "params is required" in error_text

def wait_for_task(task_id: str, timeout: int = 240, poll_interval: int = 10) -> dict:
    """
    [业界最佳实践] 阻塞等待一个异步任务完成。
    为了避免 Agent 频繁消耗 LLM token 和触发 API 频率限制，本工具会在内部每隔 `poll_interval` 秒轮询一次，
    直到任务状态变为 completed 或 failed，或者达到 `timeout` 超时时间。
    
    Args:
        task_id: The ID of the task to wait for.
        timeout: Maximum time to wait in seconds (default 240s).
        poll_interval: Seconds to sleep between polls (default 10s).
    """
    start_time = time.time()
    poll_count = 0
    transient_retry_used = False
    while True:
        # 1. 查询状态
        result = query_task_status(task_id)
        status = result.get("status", "")
        poll_count += 1
        result_payload = result.get("result", {}) if isinstance(result, dict) else {}
        url_count = len((result_payload.get("urls") or [])) if isinstance(result_payload, dict) else 0
        print(
            "[WaitForTask] poll=%s | status=%s | url_count=%s | session_id=%s | project_id=%s"
            % (
                poll_count,
                status or "unknown",
                url_count,
                result_payload.get("session_id", "") if isinstance(result_payload, dict) else "",
                result_payload.get("project_id", "") if isinstance(result_payload, dict) else "",
            )
        )
        if status in ["failed", "timeout", "expired"]:
            debug_payload = _build_query_debug_payload(result)
            print("[WaitForTask] query_result_debug=\n%s" % json.dumps(debug_payload, ensure_ascii=False, indent=2))
            if not transient_retry_used and _should_retry_libtv_transient_failure(task_id, result):
                transient_retry_used = True
                print("[WaitForTask] detected transient LibTV error 'params is required'; sleep 5s then re-check task status once.")
                time.sleep(5)
                continue
        
        # 2. 判断是否结束
        if status in ["completed", "succeeded", "failed", "timeout", "expired"]:
            return result
            
        # 3. 检查是否超时
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            return {"task_id": task_id, "status": "timeout", "message": f"Task did not complete within {timeout} seconds."}
            
        # 4. 阻塞等待
        time.sleep(poll_interval)

def sleep_seconds(seconds: int) -> str:
    """
    Pause execution for a given number of seconds.
    Use this if you explicitly need to wait before proceeding.
    """
    time.sleep(seconds)
    return f"Successfully waited for {seconds} seconds."

# List of all tools for easy import
purevis_tools = [
    design_character,
    design_scene,
    design_prop,
    breakdown_storyboard,
    generate_keyframe_prompts,
    generate_video_prompts,
    analyze_image,
    generate_image,
    generate_reference_image,
    generate_multi_view,
    generate_expression_sheet,
    generate_pose_sheet,
    generate_prop_three_view_sheet,
    generate_storyboard_grid_sheet,
    generate_video,
    query_task_status,
    wait_for_task,
    sleep_seconds
]
