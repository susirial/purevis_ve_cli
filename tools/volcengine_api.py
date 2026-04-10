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

from tools.media_providers.base import FeatureUnavailableError


DEFAULT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
IMAGE_MODEL_NAME = "doubao-seedream-4-5-251128"
VIDEO_MODEL_NAME = "doubao-seedance-1-5-pro-251215"
TEXT_MODEL_NAME = os.environ.get("VOLCENGINE_TEXT_MODEL", "doubao-seed-2-0-pro-260215")
VISION_MODEL_NAME = os.environ.get("VOLCENGINE_VISION_MODEL", "doubao-seed-2-0-pro-260215")


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
    return os.environ.get("MODEL_AGENT_API_KEY")


def _get_api_base() -> str:
    return os.environ.get("ARK_API_BASE", DEFAULT_API_BASE).rstrip("/")


def _request_ark(endpoint: str, method: str = "POST", payload: Optional[dict] = None, max_retries: int = 2) -> dict:
    api_key = _get_ark_api_key()
    if not api_key:
        raise FeatureUnavailableError("MODEL_AGENT_API_KEY 未设置，无法使用 Volcengine ARK 媒体服务。")

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


def local_generate_video(
    prompt: str,
    input_images: Optional[List[str]] = None,
    duration: int = 12,
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    
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
        # Vision requests use /api/v3/responses and have a different payload structure
        payload: Dict[str, Any] = {
            "model": model or VISION_MODEL_NAME,
            "input": messages,
        }
        resp = _request_ark("responses", payload=payload, method="POST")
        return resp
    else:
        payload: Dict[str, Any] = {
            "model": model or TEXT_MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = _request_ark("chat/completions", payload=payload, method="POST")
        return resp
