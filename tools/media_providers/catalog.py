from __future__ import annotations

import os
from typing import Any, Dict, List

from core.model_config import build_volcengine_ark_api_config
from tools.media_providers.registry import (
    get_media_provider_by_name,
    list_registered_provider_names,
    resolve_auto_provider_name,
)


_PROVIDER_METADATA: Dict[str, Dict[str, Any]] = {
    "purevis": {
        "display_name": "PureVis",
        "availability": "ga",
        "requires_env": ["PUREVIS_API_KEY"],
        "supports_explicit_model_selection": False,
        "recommended_for": ["high_level_workflow", "design_pipeline", "analysis_pipeline"],
        "notes": "适合完整高阶工作流，不适合显式指定底层模型。",
        "priority": 100,
        "defaults": {},
    },
    "libtv": {
        "display_name": "LibTV",
        "availability": "ga",
        "requires_env": ["LIBTV_ACCESS_KEY"],
        "supports_explicit_model_selection": True,
        "recommended_for": ["explicit_model_control", "fast_image", "fast_video"],
        "notes": "适合显式指定模型的原子生图、生视频与标准化设定板能力。",
        "priority": 90,
        "defaults": {
            "generate_image": "lib_nano_2",
            "generate_video": "seedance_2_0_fast",
            "generate_reference_image": "lib_nano_2",
            "generate_multi_view": "lib_nano_2",
            "generate_prop_three_view_sheet": "lib_nano_2",
            "generate_storyboard_grid_sheet": "lib_nano_2",
        },
    },
    "volcengine_ark": {
        "display_name": "Volcengine Ark",
        "availability": "ga",
        "requires_env": ["VOLCENGINE_ARK_API_KEY"],
        "supports_explicit_model_selection": False,
        "recommended_for": ["default_media_backend", "general_generation"],
        "notes": "适合作为通用默认媒体后端，当前不暴露显式模型切换。",
        "priority": 80,
        "defaults": {},
    },
    "vidu": {
        "display_name": "Vidu",
        "availability": "planned",
        "requires_env": [],
        "supports_explicit_model_selection": False,
        "recommended_for": [],
        "notes": "当前为占位 provider，尚未接入可用能力。",
        "priority": 10,
        "defaults": {},
    },
    "kling": {
        "display_name": "Kling",
        "availability": "planned",
        "requires_env": [],
        "supports_explicit_model_selection": False,
        "recommended_for": [],
        "notes": "当前为占位 provider，尚未接入可用能力。",
        "priority": 10,
        "defaults": {},
    },
}

_CAPABILITY_ALIASES: Dict[str, str] = {
    "image_generation": "generate_image",
    "video_generation": "generate_video",
    "reference_image": "generate_reference_image",
    "multi_view": "generate_multi_view",
    "expression_sheet": "generate_expression_sheet",
    "pose_sheet": "generate_pose_sheet",
    "prop_three_view_sheet": "generate_prop_three_view_sheet",
    "storyboard_grid_sheet": "generate_storyboard_grid_sheet",
    "character_design": "design_character",
    "scene_design": "design_scene",
    "prop_design": "design_prop",
    "storyboard_breakdown": "breakdown_storyboard",
    "keyframe_prompting": "generate_keyframe_prompts",
    "video_prompting": "generate_video_prompts",
    "image_analysis": "analyze_image",
}


def _is_provider_configured(name: str, requires_env: List[str]) -> bool:
    if name == "volcengine_ark":
        return bool(build_volcengine_ark_api_config().get("api_key"))
    if not requires_env:
        return True
    return all(bool(os.environ.get(key, "").strip()) for key in requires_env)


def _build_capabilities_manifest(provider_name: str, provider: Any, defaults: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    raw_caps = provider.capabilities()
    raw_models = provider.supported_models()
    image_models = raw_models.get("image", []) or []
    video_models = raw_models.get("video", []) or []
    capabilities: Dict[str, Dict[str, Any]] = {}

    for raw_key, public_key in _CAPABILITY_ALIASES.items():
        enabled = bool(raw_caps.get(raw_key, False))
        entry: Dict[str, Any] = {"enabled": enabled}
        if public_key == "generate_image":
            entry["models"] = image_models
        elif public_key == "generate_video":
            entry["models"] = video_models
        if public_key in defaults:
            if public_key in {"generate_image", "generate_video"}:
                entry["default_model"] = defaults[public_key]
            else:
                entry["fixed_model"] = defaults[public_key]
        capabilities[public_key] = entry

    if provider_name == "libtv":
        capabilities["generate_image"]["aspect_ratios"] = sorted(provider.IMAGE_ASPECT_RATIOS)
        capabilities["generate_video"]["aspect_ratios"] = sorted(provider.VIDEO_ASPECT_RATIOS)
        capabilities["generate_video"]["duration_range"] = {"min": 4, "max": 15}

    return capabilities


def get_media_provider_manifest(name: str) -> Dict[str, Any]:
    provider_name = (name or "").strip().lower()
    provider = get_media_provider_by_name(provider_name)
    metadata = _PROVIDER_METADATA.get(provider_name, {})
    requires_env = list(metadata.get("requires_env", []))
    configured = _is_provider_configured(provider_name, requires_env)
    availability = metadata.get("availability", "ga")
    capabilities = _build_capabilities_manifest(
        provider_name=provider_name,
        provider=provider,
        defaults=dict(metadata.get("defaults", {})),
    )
    if availability == "planned":
        for value in capabilities.values():
            value["enabled"] = False
    return {
        "name": provider_name,
        "display_name": metadata.get("display_name", provider_name),
        "registered": True,
        "availability": availability,
        "configured": configured,
        "available": configured and availability != "planned",
        "requires_env": requires_env,
        "supports_explicit_model_selection": bool(metadata.get("supports_explicit_model_selection", False)),
        "recommended_for": list(metadata.get("recommended_for", [])),
        "priority": int(metadata.get("priority", 0)),
        "notes": metadata.get("notes", ""),
        "capabilities": capabilities,
    }


def get_media_provider_catalog() -> Dict[str, Any]:
    raw_media_provider = os.environ.get("MEDIA_PROVIDER", "auto").strip().lower() or "auto"
    image_provider = os.environ.get("MEDIA_IMAGE_PROVIDER", "").strip().lower() or None
    video_provider = os.environ.get("MEDIA_VIDEO_PROVIDER", "").strip().lower() or None
    image_default_model = os.environ.get("MEDIA_IMAGE_DEFAULT_MODEL", "").strip().lower() or None
    video_default_model = os.environ.get("MEDIA_VIDEO_DEFAULT_MODEL", "").strip().lower() or None
    manifests = [get_media_provider_manifest(name) for name in list_registered_provider_names()]

    try:
        auto_resolved_provider = resolve_auto_provider_name()
    except Exception:
        auto_resolved_provider = None

    selected_provider = raw_media_provider if raw_media_provider != "auto" else auto_resolved_provider
    resolved_image_provider = image_provider or selected_provider
    resolved_video_provider = video_provider or selected_provider
    return {
        "selected": {
            "media_provider": raw_media_provider,
            "image_provider": image_provider,
            "video_provider": video_provider,
            "image_default_model": image_default_model,
            "video_default_model": video_default_model,
            "resolved_default_provider": selected_provider,
            "resolved_auto_provider": auto_resolved_provider,
            "resolved_image_provider": resolved_image_provider,
            "resolved_video_provider": resolved_video_provider,
        },
        "providers": manifests,
    }
