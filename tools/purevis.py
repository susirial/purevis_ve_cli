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
    provider = get_media_provider()
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
    provider = get_media_provider()
    return provider.generate_image(prompt=prompt, aspect_ratio=aspect_ratio, input_images=input_images, model=model)

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
    provider = get_media_provider()
    normalized_variant = _normalize_reference_variant(reference_variant)
    target_aspect_ratio = aspect_ratio
    if (entity_type or "").strip().lower() == "character" and not target_aspect_ratio:
        target_aspect_ratio = "9:16"
    if getattr(provider, "supports_reference", False):
        return provider.generate_reference_image(
            prompt=prompt,
            entity_type=entity_type,
            reference_variant=normalized_variant,
            aspect_ratio=target_aspect_ratio,
            input_images=input_images,
        )
    suffix = f"\n\n请生成{entity_type}参考图：主体居中，干净背景，留白充足，便于后续图生图与一致性控制。"
    if (entity_type or "").strip().lower() == "character":
        suffix += "\n" + _character_reference_variant_instruction(normalized_variant)
    return generate_image(prompt + suffix, aspect_ratio=target_aspect_ratio, input_images=input_images)

def generate_multi_view(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character multi-view turnaround sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_multi_view", False):
        return provider.generate_multi_view(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = (
        f"\n\n根据输入图1中 {character_name} 的角色参考图，生成角色多视图拼图（单张图，16:9）。"
        "左侧1/3是一张角色的大脸特写照，右侧2/3依次是角色的正面全身照、3/4侧面全身照、背面的全身照。"
        "无任何分割线，无文字，无水印。"
        "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。"
        "左1/3：角色大脸特写照（正面视角，脸部占大比例，务必包含完整头部轮廓，头发不得被裁切出画框，清晰展示五官与发型细节）。"
        "右第1列：角色正面全身照（从头到脚完整展示，包含完整的发型和鞋子）。"
        "右第2列：角色3/4侧面全身照（从头到脚完整展示，包含完整的发型和鞋子）。"
        "右第3列：角色背面全身照（从头到脚完整展示，包含完整的发型和鞋子）。"
        "四个视图必须是同一角色、同一服饰与配色、同一画风。"
        "造型、画风、着装等所有设计都严格参考图1，不要改变角色身份，不要新增道具、武器、挂件、额外人物或环境叙事元素。"
    )
    return generate_image(prompt + suffix, input_images=[ref_image])

def generate_expression_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character expression sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_expression", False):
        return provider.generate_expression_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = (
        f"\n\n根据输入图1中 {character_name} 的角色参考图，生成角色表情设定拼图（单张图，3x3）。"
        "单张图共九格，顺序固定为：第一行 neutral / happy / laughing；第二行 sad / angry / surprised；第三行 fearful / disgusted / determined。"
        "无任何分割线，无文字，无标签，无水印，无 UI 元素。"
        "每一格都必须是角色头部到上肩的近景特写，务必包含完整头部轮廓，头发不得裁切出画框。"
        "九格必须保持同一角色身份、同一发型、同一发色、同一服装领口与可见配饰、同一画风与配色。"
        "五官结构、发际线、眉形、眼型、鼻子、嘴型、下颌线都要严格参考输入图1，不得改变角色身份。"
        "每个表情必须通过清晰的微表情差异体现：眉毛位置、眼睑开合、嘴角弧度、鼻翼、脸颊紧张度。"
        "不得新增道具、武器、挂件、额外角色或环境叙事元素。"
        "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。"
    )
    return generate_image(prompt + suffix, input_images=[ref_image])

def generate_pose_sheet(prompt: str, character_name: str, ref_image: str) -> dict:
    """
    Submit a character pose sheet generation task.
    """
    provider = get_media_provider()
    if getattr(provider, "supports_pose", False):
        return provider.generate_pose_sheet(prompt=prompt, character_name=character_name, ref_image=ref_image)
    suffix = (
        f"\n\n根据输入图1中 {character_name} 的角色参考图，生成角色姿势设定拼图（单张图，16:9）。"
        "采用 3x2 或 3x3 的多格布局，至少包含六个姿势，顺序优先为：idle standing、walking mid-stride、running/sprinting、signature action pose、seated/resting pose、iconic power pose。"
        "无任何分割线，无文字，无标签，无水印，无 UI 元素。"
        "每一格都必须完整展示角色从头到脚的全身，包含完整发型、双手、双脚和鞋子，不得裁切肢体，不得遗漏鞋面或鞋底。"
        "所有格子必须是同一角色、同一服饰与配色、同一发型、同一体型比例、同一画风。"
        "造型、画风、着装、发型、配饰都严格参考输入图1，不得改变角色身份。"
        "不得新增道具、武器、挂件、额外角色或环境叙事元素；除非该元素已经属于输入图1中的基础角色设计。"
        "动作可以变化，但角色设定不能漂移；动态姿势必须具备清晰的动作线、自然重心、合理的布料与头发运动反馈。"
        "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。"
    )
    return generate_image(prompt + suffix, input_images=[ref_image])


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
    provider = get_media_provider()
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
    provider = get_media_provider()
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
    model: str = "",
) -> dict:
    """
    Submit a video generation task.
    
    Args:
        prompt: 提示词描述。
        input_images: 【重要】最多包含2个本地图片路径的列表。第1张作为首帧，如果有第2张则作为尾帧。工具会自动读取并转为 Base64。
        duration: 视频时长（秒），支持 4-12 秒或 -1（自动），默认 12。
        aspect_ratio: 画幅比，支持 '16:9', '9:16', '1:1' 等，默认 '16:9'。
        generate_audio: 是否生成音频，默认 True。
        model: 可选，显式指定底层视频模型。不同 provider 仅接受自身支持的模型名。
    """
    provider = get_media_provider()
    return provider.generate_video(
        prompt=prompt,
        input_images=input_images,
        duration=duration,
        aspect_ratio=aspect_ratio,
        generate_audio=generate_audio,
        model=model,
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
    generate_prop_three_view_sheet,
    generate_storyboard_grid_sheet,
    generate_video,
    query_task_status,
    wait_for_task,
    sleep_seconds
]
