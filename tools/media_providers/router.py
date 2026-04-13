from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from tools.media_providers.catalog import get_media_provider_catalog


_IMAGE_CAPABILITIES = {
    "generate_image",
    "generate_reference_image",
    "generate_multi_view",
    "generate_expression_sheet",
    "generate_pose_sheet",
    "generate_prop_three_view_sheet",
    "generate_storyboard_grid_sheet",
}

_VIDEO_CAPABILITIES = {"generate_video"}


def _capability_domain(capability: str) -> str:
    normalized = (capability or "").strip()
    if normalized in _IMAGE_CAPABILITIES:
        return "image"
    if normalized in _VIDEO_CAPABILITIES:
        return "video"
    return "other"


def _build_error(
    code: str,
    capability: str,
    message: str,
    requested_model: str = "",
    provider: str = "",
    requires_env: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "capability": capability,
            "requested_model": requested_model,
            "provider": provider,
            "requires_env": requires_env or [],
            "message": message,
        },
    }


def _choose_provider_from_list(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: int(item.get("priority", 0)), reverse=True)[0]


def _configured_default_model(catalog_selected: Dict[str, Any], domain: str) -> str:
    if domain == "image":
        return (catalog_selected.get("image_default_model") or "").strip().lower()
    if domain == "video":
        return (catalog_selected.get("video_default_model") or "").strip().lower()
    return ""


def _supports_model(capability_manifest: Dict[str, Any], model_name: str) -> bool:
    if not model_name:
        return False
    models = [m.lower() for m in capability_manifest.get("models", [])]
    fixed_model = (capability_manifest.get("fixed_model") or "").strip().lower()
    return model_name in models or model_name == fixed_model


def resolve_media_provider(
    capability: str,
    requested_model: str = "",
    intent_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    normalized_capability = (capability or "").strip()
    normalized_model = (requested_model or "").strip().lower()
    tags = [tag.strip().lower() for tag in (intent_tags or []) if tag and tag.strip()]
    catalog = get_media_provider_catalog()
    providers = catalog.get("providers", [])
    providers_by_name = {item["name"]: item for item in providers}
    domain = _capability_domain(normalized_capability)

    if not normalized_capability:
        return _build_error("INVALID_CAPABILITY", normalized_capability, "capability 不能为空。")

    if normalized_model:
        matching = []
        unavailable_match = None
        for provider in providers:
            cap = provider.get("capabilities", {}).get(normalized_capability, {})
            if not cap.get("enabled"):
                continue
            models = [m.lower() for m in cap.get("models", [])]
            fixed_model = (cap.get("fixed_model") or "").lower()
            if normalized_model in models or normalized_model == fixed_model:
                if provider.get("available"):
                    matching.append(provider)
                elif unavailable_match is None:
                    unavailable_match = provider
        chosen = _choose_provider_from_list(matching)
        if chosen:
            return {
                "ok": True,
                "provider": chosen["name"],
                "model": normalized_model,
                "capability": normalized_capability,
                "reason": "requested_model_supported",
                "selected_by": "requested_model",
                "requires_config": [],
                "catalog": catalog.get("selected", {}),
            }
        if unavailable_match:
            return _build_error(
                "PROVIDER_NOT_CONFIGURED",
                capability=normalized_capability,
                requested_model=normalized_model,
                provider=unavailable_match["name"],
                requires_env=unavailable_match.get("requires_env", []),
                message="支持该模型的 provider 当前未完成配置，需先补齐环境变量。",
            )
        return _build_error(
            "MODEL_NOT_SUPPORTED",
            capability=normalized_capability,
            requested_model=normalized_model,
            message="当前系统中没有可用 provider 支持该能力与模型组合。",
        )

    env_provider_name = None
    env_source = None
    if domain == "image":
        env_provider_name = catalog.get("selected", {}).get("image_provider")
        env_source = "MEDIA_IMAGE_PROVIDER" if env_provider_name else None
    elif domain == "video":
        env_provider_name = catalog.get("selected", {}).get("video_provider")
        env_source = "MEDIA_VIDEO_PROVIDER" if env_provider_name else None

    if not env_provider_name:
        env_provider_name = catalog.get("selected", {}).get("resolved_default_provider")
        env_source = "MEDIA_PROVIDER"

    if env_provider_name:
        chosen_provider = providers_by_name.get(env_provider_name)
        if chosen_provider:
            cap = chosen_provider.get("capabilities", {}).get(normalized_capability, {})
            if cap.get("enabled") and chosen_provider.get("available"):
                configured_model = _configured_default_model(catalog.get("selected", {}), domain)
                if configured_model:
                    if chosen_provider.get("supports_explicit_model_selection") and _supports_model(cap, configured_model):
                        default_model = configured_model
                        reason = "configured_provider_and_default_model_selected"
                    else:
                        return _build_error(
                            "INVALID_MEDIA_CONFIGURATION",
                            capability=normalized_capability,
                            requested_model=configured_model,
                            provider=chosen_provider["name"],
                            message="当前能力级默认模型与所选 provider 不兼容，请调整默认模型或 provider 配置。",
                        )
                else:
                    default_model = cap.get("default_model") or cap.get("fixed_model") or ""
                    reason = "configured_provider_selected"
                return {
                    "ok": True,
                    "provider": chosen_provider["name"],
                    "model": default_model,
                    "capability": normalized_capability,
                    "reason": reason,
                    "selected_by": env_source,
                    "requires_config": [],
                    "catalog": catalog.get("selected", {}),
                }
            if cap.get("enabled") and not chosen_provider.get("available"):
                return _build_error(
                    "PROVIDER_NOT_CONFIGURED",
                    capability=normalized_capability,
                    provider=chosen_provider["name"],
                    requires_env=chosen_provider.get("requires_env", []),
                    message="当前配置指定了该 provider，但其所需环境变量未满足。",
                )

    candidates = []
    for provider in providers:
        cap = provider.get("capabilities", {}).get(normalized_capability, {})
        if cap.get("enabled") and provider.get("available"):
            candidates.append(provider)

    chosen = _choose_provider_from_list(candidates)
    if chosen:
        cap = chosen.get("capabilities", {}).get(normalized_capability, {})
        configured_model = _configured_default_model(catalog.get("selected", {}), domain)
        if configured_model:
            if chosen.get("supports_explicit_model_selection") and _supports_model(cap, configured_model):
                default_model = configured_model
                reason = "configured_default_model_selected"
            else:
                return _build_error(
                    "INVALID_MEDIA_CONFIGURATION",
                    capability=normalized_capability,
                    requested_model=configured_model,
                    provider=chosen["name"],
                    message="当前能力级默认模型与自动选择出的 provider 不兼容，请调整默认模型或 provider 配置。",
                )
        else:
            default_model = cap.get("default_model") or cap.get("fixed_model") or ""
            reason = "auto_priority_selected"
        if not configured_model and "high_level_workflow" in tags:
            reason = "workflow_capability_selected"
        elif not configured_model and "explicit_model_control" in tags:
            reason = "explicit_model_capable_provider_selected"
        return {
            "ok": True,
            "provider": chosen["name"],
            "model": default_model,
            "capability": normalized_capability,
            "reason": reason,
            "selected_by": "catalog_priority",
            "requires_config": [],
            "catalog": catalog.get("selected", {}),
        }

    return _build_error(
        "CAPABILITY_NOT_SUPPORTED",
        capability=normalized_capability,
        message="当前系统中没有可用 provider 支持该能力。",
    )


def resolve_provider_for_task(task_id: str) -> Dict[str, Any]:
    normalized_task_id = (task_id or "").strip()
    if not normalized_task_id:
        return _build_error("INVALID_TASK_ID", "", "task_id 不能为空。")

    if normalized_task_id.startswith("libtv:"):
        return {
            "ok": True,
            "provider": "libtv",
            "reason": "task_prefix_detected",
            "selected_by": "task_id",
        }

    catalog = get_media_provider_catalog()
    selected_provider = catalog.get("selected", {}).get("resolved_default_provider")
    if selected_provider:
        return {
            "ok": True,
            "provider": selected_provider,
            "reason": "fallback_to_current_default_provider",
            "selected_by": "current_config",
        }

    return _build_error(
        "PROVIDER_NOT_CONFIGURED",
        capability="query_task_status",
        message="当前没有可用的默认媒体 provider，无法查询该任务状态。",
    )
