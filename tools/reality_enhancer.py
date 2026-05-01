from __future__ import annotations

from typing import Any, Dict, List, Optional


_ANIME_STYLE_HINTS = (
    "anime",
    "animation",
    "manga",
    "cartoon",
    "cel shading",
    "cel-shading",
    "toon",
    "q版",
    "二次元",
    "动漫",
    "卡通",
)

_PHOTOREAL_STYLE_HINTS = (
    "photo",
    "photoreal",
    "photographic",
    "live action",
    "live-action",
    "realistic",
    "hyperreal",
    "hyper-real",
    "写实",
    "摄影",
    "真人",
    "纪实",
)

_CINEMATIC_STYLE_HINTS = (
    "cinematic",
    "film",
    "movie",
    "screen",
    "trailer",
    "电影",
    "影视",
    "镜头",
    "预告片",
)

_CLOSE_UP_HINTS = (
    "medium close-up",
    "close-up",
    "extreme close-up",
    "特写",
    "近景",
    "大特写",
)

_MEDIUM_HINTS = (
    "medium",
    "medium wide",
    "中景",
)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _detect_style_family(style_hint: str) -> str:
    text = _normalize_text(style_hint)
    if any(token in text for token in _ANIME_STYLE_HINTS):
        return "anime"
    if any(token in text for token in _PHOTOREAL_STYLE_HINTS):
        return "photoreal"
    if any(token in text for token in _CINEMATIC_STYLE_HINTS):
        return "cinematic"
    return "stylized"


def _infer_shot_scale(shot_scale: str = "", segments: Optional[List[Any]] = None) -> str:
    direct_value = _normalize_text(shot_scale)
    if direct_value:
        if any(token in direct_value for token in _CLOSE_UP_HINTS):
            return "close_up"
        if any(token in direct_value for token in _MEDIUM_HINTS):
            return "medium"
        return "wide"

    shot_types = []
    for segment in segments or []:
        if isinstance(segment, dict):
            shot_types.append(_normalize_text(segment.get("shot_type")))

    if any(any(token in shot_type for token in _CLOSE_UP_HINTS) for shot_type in shot_types):
        return "close_up"
    if any(any(token in shot_type for token in _MEDIUM_HINTS) for shot_type in shot_types):
        return "medium"
    return "wide"


def resolve_reality_profile(
    *,
    target: str,
    entity_type: str,
    style_hint: str = "",
    shot_scale: str = "",
    segments: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    style_family = _detect_style_family(style_hint)
    inferred_shot_scale = _infer_shot_scale(shot_scale=shot_scale, segments=segments)
    normalized_target = _normalize_text(target)
    normalized_entity = _normalize_text(entity_type)

    profile_name = "subtle"
    if style_family in {"photoreal", "cinematic"}:
        profile_name = "cinematic_subtle"

    enable_closeup_skin_detail = normalized_entity == "character" and inferred_shot_scale == "close_up"
    if style_family == "anime":
        enable_closeup_skin_detail = False

    motion_safe = "video" in normalized_target

    return {
        "enabled": normalized_entity in {"character", "scene", "environment", "mixed"},
        "profile": profile_name,
        "style_family": style_family,
        "entity_type": normalized_entity or "mixed",
        "shot_scale": inferred_shot_scale,
        "motion_safe": motion_safe,
        "allow_visible_pores_in_closeup": enable_closeup_skin_detail and not motion_safe,
        "allow_faint_freckles": enable_closeup_skin_detail and style_family != "anime" and not motion_safe,
        "avoid_glamour_retouch": normalized_entity in {"character", "mixed"},
        "avoid_showroom_clean": normalized_entity in {"scene", "environment", "mixed"},
        "preserve_stylization": style_family in {"anime", "stylized"},
    }


def build_llm_reality_guidance(profile: Dict[str, Any]) -> str:
    if not profile.get("enabled"):
        return ""

    entity_type = profile["entity_type"]
    profile_name = profile["profile"]
    style_family = profile["style_family"]
    shot_scale = profile["shot_scale"]
    motion_safe = profile["motion_safe"]

    lines = [
        "真实度增强器：",
        f"- 档位：{profile_name}",
        f"- 风格保护：保持当前 {style_family} 审美方向，不得把风格化/动漫需求强行改写成纪实摄影。",
    ]

    if entity_type in {"character", "mixed"}:
        lines.extend(
            [
                "- 人物真实度：默认加入自然皮肤质感、轻微肤色起伏、轻微自然不对称、碎发与发际线细节，避免塑料皮肤、蜡像感、瓷皮、商业美容修图感。",
                "- 人物真实度：除非镜头是近景/特写且风格允许，不要夸张微观皮肤词汇。",
            ]
        )
        if profile.get("allow_visible_pores_in_closeup"):
            lines.append("- 近景人物：可适度加入细微毛孔、淡雀斑、轻微肤色不均、唇纹、眼下细节，但必须克制，不能脏乱或老化过度。")
        else:
            lines.append("- 当前镜头/风格：不要默认强调毛孔、雀斑等微观皮肤细节，只保留自然肤质即可。")

    if entity_type in {"scene", "environment", "mixed"}:
        lines.extend(
            [
                "- 场景真实度：强化真实材质差异、轻微风化/使用痕迹、自然积尘或湿度变化，但不要把环境做旧过头。",
                "- 场景真实度：强化前景/中景/背景分层，可加入轻微前景遮挡、空气透视、自然背景虚化；景深必须符合镜头尺度与镜头语言。",
                "- 光线真实度：优先真实光比与高光衰减，可使用头顶光、侧主光、轮廓/发丝光，但必须有合理动机来源和连续性。",
            ]
        )

    if shot_scale == "wide":
        lines.append("- 远景/大全景：不要写近距离毛孔类信息，重点放在整体材质、空间层次、光线逻辑和空气感。")
    elif shot_scale == "medium":
        lines.append("- 中景：以自然肤质、真实服装材质、合理景深为主，不要把特写级微观细节写得过满。")
    else:
        lines.append("- 近景/特写：可以加强面部与材质局部真实度，但要保持审美克制与主体美感。")

    if motion_safe:
        lines.append("- 视频约束：避免过强的微观皮肤描述导致时序闪烁，重点增强光线真实、材质真实、景深真实和物理连续性。")

    lines.append("- 负向约束：避免 plastic skin、waxy face、porcelain skin、over-smoothed beauty retouch、showroom-clean perfection、flat lighting。")
    return "\n".join(lines)


def build_direct_prompt_reality_fragment(profile: Dict[str, Any]) -> str:
    if not profile.get("enabled"):
        return ""

    positive_chunks: List[str] = []
    negative_chunks: List[str] = []

    if profile["entity_type"] in {"character", "mixed"}:
        positive_chunks.extend(
            [
                "natural skin texture",
                "slight tonal variation",
                "subtle natural asymmetry",
                "fine baby hairs and loose strands",
                "no beauty-retouch finish",
            ]
        )
        if profile.get("allow_visible_pores_in_closeup"):
            positive_chunks.extend(
                [
                    "subtle pores visible at close range",
                    "faint freckles if appropriate",
                    "natural lip texture",
                    "restrained under-eye detail",
                ]
            )
        negative_chunks.extend(
            [
                "plastic skin",
                "waxy face",
                "porcelain skin",
                "airbrushed glamour retouch",
                "over-smoothed facial texture",
            ]
        )

    if profile["entity_type"] in {"scene", "environment", "mixed"}:
        positive_chunks.extend(
            [
                "natural material irregularity",
                "subtle surface wear where appropriate",
                "realistic light falloff",
                "clear foreground middle-ground background separation",
                "natural background falloff",
            ]
        )
        negative_chunks.extend(
            [
                "showroom-clean perfection",
                "sterile surfaces",
                "flat lighting",
                "artificially creamy blur",
            ]
        )

    if profile.get("motion_safe"):
        positive_chunks.append("motion-safe realism with stable texture continuity")

    if profile.get("preserve_stylization"):
        positive_chunks.append("preserve stylized shape language while keeping realism restrained")

    if not positive_chunks and not negative_chunks:
        return ""

    positive_text = ", ".join(dict.fromkeys(positive_chunks))
    negative_text = ", ".join(dict.fromkeys(negative_chunks))
    if positive_text and negative_text:
        return f"Reality enhancer: {positive_text}. Avoid {negative_text}."
    if positive_text:
        return f"Reality enhancer: {positive_text}."
    return f"Avoid {negative_text}."
