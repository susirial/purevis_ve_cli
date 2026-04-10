import os
import time
import base64
import requests
from typing import Optional, List, Dict, Any

try:
    from tools.image_utils import resize_and_compress_image
except ImportError:
    def resize_and_compress_image(p, **kwargs): return p

from tools.media_providers.base import FeatureUnavailableError
from tools.media_providers.registry import get_media_provider as _get_media_provider

PUREVIS_BASE_URL = "https://www.purevis.cn/api/v1"


def get_media_provider():
    return _get_media_provider()


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

def design_character(character_name: str, character_brief: str, style: str, story_context: str = "") -> dict:
    """
    Generate a character t2i prompt and Chinese description.
    
    Args:
        character_name: Name of the character.
        character_brief: Brief description of the character.
        style: Visual style (e.g., "Japanese anime", "realistic").
        story_context: Optional context of the story.
    """
    provider = get_media_provider()
    return provider.design_character(
        character_name=character_name,
        character_brief=character_brief,
        style=style,
        story_context=story_context
    )

def design_scene(scene_name: str, scene_brief: str, style: str, story_context: str = "") -> dict:
    """
    Generate a scene t2i prompt and Chinese description.
    """
    provider = get_media_provider()
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
    provider = get_media_provider()
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
    provider = get_media_provider()
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
    provider = get_media_provider()
    return provider.generate_keyframe_prompts(
        segments=segments,
        entity_names=entity_names,
        aspect_ratio=aspect_ratio,
        style=style
    )

def generate_video_prompts(segments: list, entity_names: list, aspect_ratio: str, style: str) -> dict:
    """
    Generate per-segment video timeline prompts.
    
    Args:
        segments: 必须是一个包含具体剧本情节或画面分镜描述的列表（例如从 `breakdown_storyboard` 返回的结果）。严禁传入空列表或无实质剧情内容的参数，否则接口会报错 INTENT_REJECTED。
        entity_names: List of entity names to be included.
        aspect_ratio: 16:9 | 9:16 | 1:1
        style: Visual style.
    """
    provider = get_media_provider()
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
    provider = get_media_provider()
    return provider.analyze_image(
        image_url_or_path=image_url_or_path,
        analyze_type=analyze_type
    )

# ==========================================
# Task 4: Tool APIs (Asynchronous)
# ==========================================

def generate_image(prompt: str, aspect_ratio: str = "", input_images: list = None) -> dict:
    """
    Submit a general-purpose image generation task (Text-to-Image or Image-to-Image).
    Returns task_id to poll later.
    
    Args:
        prompt: 提示词描述。
        aspect_ratio: 画幅比，例如 "16:9"、"9:16"、"1:1" 等。
        input_images: 【重要】如果要进行图生图（如参考已有的角色/场景图片），请将该图片的本地路径（如 "output/projects/.../xxx.jpg"）作为一个字符串放入此列表中传入（例如：["output/.../img.jpg"]）。工具会自动读取并转为 Base64。如果不使用图生图，留空即可。
    """
    provider = get_media_provider()
    return provider.generate_image(prompt=prompt, aspect_ratio=aspect_ratio, input_images=input_images)

def generate_reference_image(prompt: str, entity_type: str, aspect_ratio: str = "", input_images: list = None) -> dict:
    """
    Submit a reference sheet generation task with composition constraints.
    
    Args:
        prompt: 提示词描述。
        entity_type: character | scene | prop
        aspect_ratio: 画幅比
        input_images: 如果需要基于已有图片生成参考图，可传入本地路径列表（同 generate_image）。
    """
    provider = get_media_provider()
    if getattr(provider, "supports_reference", False):
        return provider.generate_reference_image(
            prompt=prompt,
            entity_type=entity_type,
            aspect_ratio=aspect_ratio,
            input_images=input_images,
        )
    suffix = f"\n\n请生成{entity_type}参考图：主体居中，干净背景，留白充足，便于后续图生图与一致性控制。"
    return generate_image(prompt + suffix, aspect_ratio=aspect_ratio, input_images=input_images)

def generate_multi_view(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character multi-view turnaround sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_multi_view", False):
        return provider.generate_multi_view(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = f"\n\n请生成角色多视图转身表：角色名={character_name}，包含正面/左侧/右侧/背面，多格排版，风格一致。"
    return generate_image(prompt + suffix, input_images=[ref_image])

def generate_expression_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character expression sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_expression", False):
        return provider.generate_expression_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = f"\n\n请生成角色表情表：角色名={character_name}，至少8种表情，多格排版，面部特征与服装保持一致。"
    return generate_image(prompt + suffix, input_images=[ref_image])

def generate_pose_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character pose sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_pose", False):
        return provider.generate_pose_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = f"\n\n请生成角色姿势表：角色名={character_name}，包含站姿/走路/跑步/坐姿/动作姿势等，多格排版，比例一致。"
    return generate_image(prompt + suffix, input_images=[ref_image])

def generate_video(prompt: str, input_images: list = None, duration: int = 12, aspect_ratio: str = "16:9", generate_audio: bool = True) -> dict:
    """
    Submit a video generation task.
    
    Args:
        prompt: 提示词描述。
        input_images: 【重要】最多包含2个本地图片路径的列表。第1张作为首帧，如果有第2张则作为尾帧。工具会自动读取并转为 Base64。
        duration: 视频时长（秒），支持 4-12 秒或 -1（自动），默认 12。
        aspect_ratio: 画幅比，支持 '16:9', '9:16', '1:1' 等，默认 '16:9'。
        generate_audio: 是否生成音频，默认 True。
    """
    provider = get_media_provider()
    return provider.generate_video(
        prompt=prompt,
        input_images=input_images,
        duration=duration,
        aspect_ratio=aspect_ratio,
        generate_audio=generate_audio,
    )

def query_task_status(task_id: str) -> dict:
    """
    Query task status and result by task_id.
    """
    provider = get_media_provider()
    return provider.query_task_status(task_id)

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
    while True:
        # 1. 查询状态
        result = query_task_status(task_id)
        status = result.get("status", "")
        
        # 2. 判断是否结束
        if status in ["completed", "failed"]:
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
    generate_video,
    query_task_status,
    wait_for_task,
    sleep_seconds
]
