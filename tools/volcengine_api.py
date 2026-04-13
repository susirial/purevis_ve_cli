from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict, List, Optional

import requests

from core.model_config import (
    build_tool_text_model_config,
    build_tool_vision_analyzer_model_config,
    build_volcengine_ark_api_config,
)

try:
    from tools.image_utils import resize_and_compress_image
except ImportError:
    def resize_and_compress_image(p, **kwargs):
        return p

from tools.media_providers.base import FeatureUnavailableError, build_audio_mode_instruction, normalize_audio_mode


DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
IMAGE_MODEL_NAME = "doubao-seedream-4-5-251128"
VIDEO_MODEL_NAME = "doubao-seedance-1-5-pro-251215"


def get_tool_text_model_name() -> str:
    return build_tool_text_model_config()["model_name"]


def get_tool_vision_model_name() -> str:
    return build_tool_vision_analyzer_model_config()["model_name"]


def _guess_image_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "image/jpeg"


def _encode_image_to_data_uri(image_path: str) -> str:
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
    return [_encode_image_to_data_uri(img) for img in input_images]


def _get_ark_api_key() -> Optional[str]:
    return build_volcengine_ark_api_config()["api_key"] or None


def _get_api_base() -> str:
    return build_volcengine_ark_api_config()["api_base"].rstrip("/")


def _request_ark(endpoint: str, method: str = "POST", payload: Optional[dict] = None, max_retries: int = 2) -> dict:
    api_key = _get_ark_api_key()
    if not api_key:
        raise FeatureUnavailableError(
            "未设置可用的 Volcengine ARK API Key，无法使用媒体或固定视觉分析能力。"
            "请优先设置 VOLCENGINE_ARK_API_KEY，或设置 MODEL_TOOL_VISION_ANALYZER_API_KEY，"
            "兼容场景下也可回退使用 MODEL_AGENT_API_KEY。"
        )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{_get_api_base()}/{endpoint.lstrip('/')}"

    attempt = 0
    while attempt <= max_retries:
        try:
            if method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=payload, timeout=180, proxies={"http": None, "https": None})
            elif method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=180, proxies={"http": None, "https": None})
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            attempt += 1
            if hasattr(e, "response") and e.response is not None:
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise Exception(f"HTTP Error: {e} - Response: {getattr(e.response, 'text', '')}")
            if attempt <= max_retries:
                time.sleep(5)
            else:
                raise Exception(f"Request Error after {max_retries} retries: {e}")


def _request_openai_compatible(
    *,
    api_base: str,
    api_key: str,
    endpoint: str,
    payload: Dict[str, Any],
    max_retries: int = 2,
) -> Dict[str, Any]:
    if not api_key:
        raise FeatureUnavailableError("未设置对应模型的 API Key，无法发起文本或视觉模型请求。")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{api_base.rstrip('/')}/{endpoint.lstrip('/')}"

    attempt = 0
    while attempt <= max_retries:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180, proxies={"http": None, "https": None})
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            attempt += 1
            if hasattr(e, "response") and e.response is not None:
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise Exception(f"HTTP Error: {e} - Response: {getattr(e.response, 'text', '')}")
            if attempt <= max_retries:
                time.sleep(5)
            else:
                raise Exception(f"Request Error after {max_retries} retries: {e}")


def local_generate_image(prompt: str, aspect_ratio: str = "", input_images: Optional[List[str]] = None) -> Dict[str, Any]:
    # 按照最新的 /api/v3/images/generations 接口构建请求
    payload: Dict[str, Any] = {
        "model": IMAGE_MODEL_NAME,
        "prompt": prompt,
        "watermark": False
    }

    # 处理多图/单图生图的情况
    # 根据文档，支持 `image` 字段，格式为 string 或 array
    if input_images:
        processed_imgs = _process_input_images(input_images)
        if processed_imgs:
            if len(processed_imgs) == 1:
                payload["image"] = processed_imgs[0]
            else:
                payload["image"] = processed_imgs

    # 尺寸控制，支持 2K, 3K, 4K 等分辨率标签，或者明确的宽高像素（需符合一定总像素限制）
    # 由于原本传入的是 `aspect_ratio` (如 16:9)，我们可以将其转换为 API 支持的分辨率描述方式
    # 或者直接指定 size 并在 prompt 中说明
    if aspect_ratio:
        payload["size"] = "2K" # 指定基础分辨率
        payload["prompt"] = f"{prompt}\n(画面比例: {aspect_ratio})" # 附加比例要求给模型
    else:
        payload["size"] = "2K"

    # 使用新的 endpoints
    resp = _request_ark("images/generations", payload=payload, method="POST")
    
    # 解析同步返回的响应 (新的 images/generations 接口默认是同步返回结果的，除非用 tasks)
    urls = []
    if "data" in resp:
        for item in resp["data"]:
            if "url" in item:
                urls.append(item["url"])
            elif "b64_json" in item:
                urls.append(item["b64_json"])
                
    if urls:
        # 为了兼容既有的基于轮询 task_id 的架构，我们创建一个 mock task
        import uuid
        task_id = f"mock_img_task_{uuid.uuid4().hex}"
        # 需要在 provider 层面拦截这个 mock task，但由于这是底层 api 文件，
        # 我们只能把结果包装成类似 task 完成的状态返回，或者由外层统一处理。
        # 最简单的方法是修改返回结构，使其包含立刻可用的 urls。
        return {"task_id": task_id, "status": "completed", "urls": urls}
    
    # 如果没有立即返回 url，则可能还是返回了 task id（以防万一）
    task_id = resp.get("id") or resp.get("task_id") or resp.get("taskId")
    if not task_id:
        raise Exception(f"Volcengine ARK 返回格式异常或生成失败: {resp}")
    return {"task_id": task_id}


def local_generate_reference_image(
    prompt: str,
    entity_type: str,
    reference_variant: str = "pure_character",
    aspect_ratio: str = "",
    input_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    variant = (reference_variant or "pure_character").strip().lower()
    target_aspect_ratio = aspect_ratio
    if (entity_type or "").strip().lower() == "character" and not target_aspect_ratio:
        target_aspect_ratio = "9:16"
    full_prompt = (
        f"{prompt}\n"
        "Clean pure white background, studio lighting, one centered subject, high resolution, "
        "single-character reference portrait, full-body character concept art, one figure only, "
        "not a multi-view sheet, not a turnaround sheet, not a pose sheet, not an expression sheet, "
        "not a collage, not a lineup, no repeated character in different poses, no multiple panels, "
        "no split layout, no contact sheet, no text, no watermark."
    )
    if (entity_type or "").strip().lower() == "character":
        if variant in {"full", "full_character", "full_character_sheet", "complete", "complete_character"}:
            full_prompt += (
                " Full character reference mode: 9:16 vertical composition, single primary character only, clean white background, "
                "exactly one full-body standing figure in the frame, no duplicate versions of the same character, "
                "signature weapon or identity-defining handheld props allowed only when explicitly requested in the prompt, "
                "no mount, no companion, no extra character."
            )
        elif variant in {"mounted", "with_mount", "mount", "mounted_character"}:
            full_prompt += (
                " Mounted character reference mode: 9:16 vertical composition, keep one primary character as the visual focus, "
                "only one hero character pose in the frame, no duplicate versions of the same character, "
                "allow only the explicitly requested mount or companion and explicitly requested signature weapon, "
                "no extra characters, no crowd, no unrelated props."
            )
        else:
            full_prompt += (
                " Pure character reference mode: 9:16 vertical composition, single character only, exactly one full-body standing figure, "
                "no mount, no companion, no pet, no extra subject, no handheld prop, no weapon unless explicitly requested, "
                "keep only the character body, clothing, hairstyle, silhouette and essential wearable accessories."
            )
    return local_generate_image(
        prompt=full_prompt,
        aspect_ratio=target_aspect_ratio,
        input_images=input_images,
    )


def _normalize_storyboard_panel_count(panel_count: int) -> int:
    try:
        normalized = int(panel_count)
    except (TypeError, ValueError):
        normalized = 16
    return normalized if normalized in {4, 6, 8, 9, 12, 16, 25} else 16


def local_generate_prop_three_view_sheet(
    prompt: str,
    prop_name: str = "",
    input_images: Optional[List[str]] = None,
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    display_name = prop_name.strip() if prop_name else "该道具"
    full_prompt = (
        f"{prompt}\n"
        f"请生成 {display_name} 的工业设计三视图道具设定板。"
        "必须是单张图、单画布、横向排版，不得拆分成多张图片。"
        "严格采用正面视图、侧面视图、背面视图三等分均匀布局。"
        "纯白背景，无场景，无人物，无杂物，无阴影噪点，无文字，无标签，无水印，无 UI 元素。"
        "三视图中的道具必须保持完全一致的结构、材质、配色与比例。"
        "每个视图都必须完整展示道具主体，complete body, fully visible, no cropping, no missing parts."
        "强调 orthographic industrial design sheet、product concept board、clean studio lighting、even lighting、high readability、8K、ultra detailed."
    )
    return local_generate_image(
        prompt=full_prompt,
        aspect_ratio=aspect_ratio or "16:9",
        input_images=input_images,
    )


def local_generate_storyboard_grid_sheet(
    prompt: str,
    panel_count: int = 16,
    aspect_ratio: str = "1:1",
    input_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    normalized_count = _normalize_storyboard_panel_count(panel_count)
    grid_side = int(normalized_count ** 0.5)
    grid_label = f"{grid_side}x{grid_side}" if grid_side * grid_side == normalized_count else f"{normalized_count} panels"
    full_prompt = (
        f"{prompt}\n"
        f"请生成单张故事板拼图，严格为 {normalized_count} 宫格（{grid_label}）布局。"
        "所有内容必须整合在同一张画布内，禁止分图生成。"
        "每个宫格都必须是一张完整画面，所有宫格尺寸严格一致，边距与留白均匀。"
        "图片中不要出现文字、标签、分镜编号、水印、UI 元素。"
        "整张图需要读起来像完整故事板，镜头语言应包含远景、全景、中景、近景、特写等合理变化。"
        "所有格子中的角色身份、服装、发型、道具与环境连续性必须稳定。"
        "强调 storyboard contact sheet、single canvas、equal-sized panels、clean layout、strong continuity、high readability、high detail."
    )
    return local_generate_image(
        prompt=full_prompt,
        aspect_ratio=aspect_ratio or "1:1",
        input_images=input_images,
    )


def local_generate_video(
    prompt: str,
    input_images: Optional[List[str]] = None,
    duration: int = 12,
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
    audio_mode: str = "ambient_only",
) -> Dict[str, Any]:
    normalized_audio_mode = normalize_audio_mode(audio_mode)
    prompt_with_audio_instruction = f"{prompt.rstrip()}\n{build_audio_mode_instruction(generate_audio, normalized_audio_mode)}"
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt_with_audio_instruction}]
    
    if input_images and len(input_images) > 0:
        if len(input_images) == 1:
            img = _encode_image_to_data_uri(input_images[0])
            content.append({"type": "image_url", "image_url": {"url": img}})
        elif len(input_images) >= 2:
            img1 = _encode_image_to_data_uri(input_images[0])
            img2 = _encode_image_to_data_uri(input_images[1])
            content.append({"type": "image_url", "image_url": {"url": img1}, "role": "first_frame"})
            content.append({"type": "image_url", "image_url": {"url": img2}, "role": "last_frame"})

    payload: Dict[str, Any] = {
        "model": VIDEO_MODEL_NAME,
        "content": content,
        "ratio": aspect_ratio or "16:9",
        "resolution": "720p",
        "watermark": False,
        "generate_audio": generate_audio,
    }

    if duration:
        if duration < 4:
            payload["duration"] = 4
        elif duration > 12:
            payload["duration"] = 12
        else:
            payload["duration"] = duration
    else:
        payload["duration"] = -1

    resp = _request_ark("contents/generations/tasks", payload=payload, method="POST")
    task_id = resp.get("id") or resp.get("task_id") or resp.get("taskId")
    if not task_id:
        raise Exception(f"Volcengine ARK 返回缺少任务 id: {resp}")
    return {"task_id": task_id}


def _normalize_status(raw_status: str) -> str:
    s = (raw_status or "").lower()
    if s in {"succeeded", "success", "completed", "complete"}:
        return "completed"
    if s in {"failed", "error", "canceled", "cancelled"}:
        return "failed"
    if s in {"running", "queued", "processing"}:
        return "processing"
    return s or "processing"


def _extract_urls(resp: dict) -> List[str]:
    urls: List[str] = []

    for container_key in ["content", "result", "outputs", "output", "data"]:
        container = resp.get(container_key)
        if isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                url = (
                    item.get("url")
                    or (item.get("image_url") or {}).get("url")
                    or (item.get("video_url") or {}).get("url")
                    or item.get("video_url") # <--- 适配 Seedance
                    or (item.get("image") or {}).get("url")
                    or (item.get("video") or {}).get("url")
                )
                if url:
                    urls.append(url)
        if isinstance(container, dict):
            for nested_key in ["url", "urls", "video_url"]: # <--- 适配 Seedance
                v = container.get(nested_key)
                if isinstance(v, str):
                    urls.append(v)
                elif isinstance(v, list):
                    for u in v:
                        if isinstance(u, str):
                            urls.append(u)

    if "url" in resp and isinstance(resp["url"], str):
        urls.append(resp["url"])
    if "urls" in resp and isinstance(resp["urls"], list):
        for u in resp["urls"]:
            if isinstance(u, str):
                urls.append(u)

    seen = set()
    deduped: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def local_query_task_status(task_id: str) -> Dict[str, Any]:
    resp = _request_ark(f"contents/generations/tasks/{task_id}", method="GET")
    status = _normalize_status(resp.get("status") or resp.get("state") or resp.get("task_status") or "")
    urls = _extract_urls(resp)
    result: Dict[str, Any] = {}
    if urls:
        result["urls"] = urls
        result["url"] = urls[0]
    return {"task_id": task_id, "status": status, "result": result, "raw": resp}


def local_chat_completions(
    messages: List[Dict[str, Any]],
    model: str = "",
    response_format: Optional[Dict[str, Any]] = None,
    temperature: float = 0.7,
    is_vision: bool = False,
) -> Dict[str, Any]:
    if is_vision:
        vision_config = build_tool_vision_analyzer_model_config()
        # Vision requests use /api/v3/responses and have a different payload structure
        payload: Dict[str, Any] = {
            "model": model or vision_config["model_name"],
            "input": messages,
        }
        resp = _request_openai_compatible(
            api_base=vision_config["model_api_base"],
            api_key=vision_config.get("model_api_key", ""),
            endpoint="responses",
            payload=payload,
        )
        return resp
    else:
        text_config = build_tool_text_model_config()
        payload: Dict[str, Any] = {
            "model": model or text_config["model_name"],
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = _request_openai_compatible(
            api_base=text_config["model_api_base"],
            api_key=text_config.get("model_api_key", ""),
            endpoint="chat/completions",
            payload=payload,
        )
        return resp
