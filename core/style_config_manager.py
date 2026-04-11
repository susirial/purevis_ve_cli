from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.project_spec_registry import ProjectSpecRegistry
from core.state_manager import StateManager


STYLE_TARGETS = ("video", "image", "keyframe")
STYLE_CONFIG_SCHEMA_VERSION = "1.0"


class StyleConfigManager:
    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        registry: Optional[ProjectSpecRegistry] = None,
    ):
        self.state_manager = state_manager or StateManager()
        self.registry = registry or ProjectSpecRegistry()

    def list_style_families(self) -> List[Dict[str, Any]]:
        return self.registry.list_style_families()

    def list_style_subtypes(self, family_code: str) -> List[Dict[str, Any]]:
        return self.registry.list_style_subtypes(family_code)

    def list_media_families(self) -> List[Dict[str, Any]]:
        return self.registry.list_media_families()

    def get_style_preset(self, family_code: str, subtype_code: str) -> Dict[str, Any]:
        return self.registry.get_style_preset(family_code, subtype_code)

    def get_project_style_config(self, project_name: str) -> Dict[str, Any]:
        state = self.state_manager.load_state(project_name)
        settings = state.setdefault("settings", {})
        style_config = settings.get("style_config")
        if style_config:
            normalized = self._normalize_existing_style_config(style_config)
            if normalized != style_config:
                settings["style_config"] = normalized
                self.state_manager.save_state(project_name, state)
                self._write_current_snapshot(project_name, normalized)
            return normalized

        legacy_style = self._build_legacy_style_fallback(settings)
        if legacy_style:
            settings["style_config"] = legacy_style
            self.state_manager.save_state(project_name, state)
            self._write_current_snapshot(project_name, legacy_style)
            return legacy_style

        return self._empty_style_config()

    def update_project_style_config(
        self,
        project_name: str,
        target_styles: Dict[str, Dict[str, Any]],
        actor: str = "system",
        change_reason: str = "manual update",
        auto_correct: bool = True,
    ) -> Dict[str, Any]:
        state = self.state_manager.load_state(project_name)
        settings = state.setdefault("settings", {})
        current = self._normalize_existing_style_config(settings.get("style_config") or self._empty_style_config())
        next_targets = deepcopy(current["targets"])
        warnings: List[str] = []

        for target, payload in target_styles.items():
            normalized_target = self._normalize_target_payload(
                state=state,
                target=target,
                payload=payload,
                auto_correct=auto_correct,
                warnings=warnings,
            )
            next_targets[target] = normalized_target

        next_config = {
            "schema_version": STYLE_CONFIG_SCHEMA_VERSION,
            "registry_version": self.registry.get_registry_version(),
            "version": int(current.get("version", 0)) + 1,
            "updated_at": _now_iso(),
            "targets": next_targets,
        }

        settings["style_config"] = next_config
        self._sync_legacy_visual_settings(settings, next_config)
        self.state_manager.save_state(project_name, state)
        self._write_current_snapshot(project_name, next_config)
        self._append_version_snapshot(project_name, next_config, actor, change_reason)
        self._append_audit_log(
            project_name=project_name,
            actor=actor,
            action="update",
            change_reason=change_reason,
            payload={"targets": list(target_styles.keys()), "warnings": warnings},
            resulting_version=next_config["version"],
        )
        return {
            "project_name": project_name,
            "style_config": next_config,
            "warnings": warnings,
        }

    def delete_project_style_config(
        self,
        project_name: str,
        target: Optional[str] = None,
        actor: str = "system",
        change_reason: str = "manual delete",
    ) -> Dict[str, Any]:
        state = self.state_manager.load_state(project_name)
        settings = state.setdefault("settings", {})
        current = self._normalize_existing_style_config(settings.get("style_config") or self._empty_style_config())
        next_config = deepcopy(current)

        if target:
            if target not in STYLE_TARGETS:
                raise ValueError(f"未知风格目标: {target}")
            next_config["targets"].pop(target, None)
        else:
            next_config["targets"] = {}

        next_config["version"] = int(current.get("version", 0)) + 1
        next_config["updated_at"] = _now_iso()
        next_config["registry_version"] = self.registry.get_registry_version()
        settings["style_config"] = next_config
        self._sync_legacy_visual_settings(settings, next_config)
        self.state_manager.save_state(project_name, state)
        self._write_current_snapshot(project_name, next_config)
        self._append_version_snapshot(project_name, next_config, actor, change_reason)
        self._append_audit_log(
            project_name=project_name,
            actor=actor,
            action="delete",
            change_reason=change_reason,
            payload={"target": target or "all"},
            resulting_version=next_config["version"],
        )
        return {
            "project_name": project_name,
            "style_config": next_config,
        }

    def list_project_style_versions(self, project_name: str) -> Dict[str, Any]:
        versions_path = self._versions_path(project_name)
        if not versions_path.exists():
            return {"project_name": project_name, "snapshots": []}
        return json.loads(versions_path.read_text(encoding="utf-8"))

    def build_prompt_style_context(self, project_name: str, target: str) -> Dict[str, Any]:
        if target not in STYLE_TARGETS:
            raise ValueError(f"未知风格注入目标: {target}")
        style_config = self.get_project_style_config(project_name)
        state = self.state_manager.load_state(project_name)
        settings = state.get("settings", {})
        resolved_target = self._resolve_target_config(style_config, target)
        delivery_context = self._extract_delivery_context(settings)

        if not resolved_target:
            return {
                "project_name": project_name,
                "target": target,
                "style_prompt_block": "【项目风格注入】当前项目尚未配置结构化风格，请先选择风格家族与二级子类。",
                "resolved_style": None,
                "delivery_context": delivery_context,
                "style_version": style_config.get("version", 0),
            }

        prompt_lines = [
            f"【项目风格注入 / {target.upper()}】",
            f"- 一级风格家族: {resolved_target['family_code']} / {resolved_target['family_label']}",
            f"- 二级风格子类: {resolved_target['subtype_code']}",
        ]
        if delivery_context:
            prompt_lines.append(
                "- 目标媒介: "
                + " / ".join(
                    str(delivery_context[key])
                    for key in ("media_family", "media_subtype", "aspect_ratio")
                    if delivery_context.get(key)
                )
            )
        if resolved_target.get("recommended_palette"):
            prompt_lines.append("- 推荐色板: " + ", ".join(resolved_target["recommended_palette"]))
        if resolved_target.get("recommended_camera"):
            prompt_lines.append("- 推荐镜头: " + ", ".join(resolved_target["recommended_camera"]))
        if resolved_target.get("surface_treatment"):
            prompt_lines.append("- 推荐材质: " + ", ".join(resolved_target["surface_treatment"]))
        if resolved_target.get("audience_tags"):
            prompt_lines.append("- 目标受众标签: " + ", ".join(resolved_target["audience_tags"]))
        negative_constraints = resolved_target.get("negative_style_constraints") or []
        if negative_constraints:
            prompt_lines.append("- 负向约束: " + ", ".join(negative_constraints))
        prompt_lines.append("- 执行要求: 在当前任务的提示词、分镜描述与结构化 JSON 中显式继承上述风格要素，除非用户明确覆盖。")

        return {
            "project_name": project_name,
            "target": target,
            "style_prompt_block": "\n".join(prompt_lines),
            "resolved_style": resolved_target,
            "delivery_context": delivery_context,
            "style_version": style_config.get("version", 0),
        }

    def _normalize_existing_style_config(self, style_config: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {
            "schema_version": style_config.get("schema_version", STYLE_CONFIG_SCHEMA_VERSION),
            "registry_version": style_config.get("registry_version", self.registry.get_registry_version()),
            "version": int(style_config.get("version", 0) or 0),
            "updated_at": style_config.get("updated_at"),
            "targets": {},
        }
        for target, payload in (style_config.get("targets") or {}).items():
            if target not in STYLE_TARGETS or not isinstance(payload, dict):
                continue
            normalized["targets"][target] = {
                "family_code": payload.get("family_code"),
                "family_label": payload.get("family_label"),
                "subtype_code": payload.get("subtype_code"),
                "subtype_summary": payload.get("subtype_summary", ""),
                "applicable_media": list(payload.get("applicable_media") or []),
                "recommended_palette": list(payload.get("recommended_palette") or []),
                "recommended_camera": list(payload.get("recommended_camera") or []),
                "surface_treatment": list(payload.get("surface_treatment") or []),
                "audience_tags": list(payload.get("audience_tags") or []),
                "negative_style_constraints": list(payload.get("negative_style_constraints") or []),
                "source": payload.get("source", "structured"),
            }
        return normalized

    def _build_legacy_style_fallback(self, settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        visual = settings.get("visual") or {}
        family_code = visual.get("art_style_family")
        subtype_code = visual.get("art_style_subtype")
        if not family_code or not subtype_code:
            return None
        preset = self.registry.get_style_preset(family_code, subtype_code)
        target_config = {
            **preset,
            "negative_style_constraints": [],
            "source": "legacy_visual_settings",
        }
        return {
            "schema_version": STYLE_CONFIG_SCHEMA_VERSION,
            "registry_version": self.registry.get_registry_version(),
            "version": 1,
            "updated_at": _now_iso(),
            "targets": {
                "video": deepcopy(target_config),
                "image": deepcopy(target_config),
                "keyframe": deepcopy(target_config),
            },
        }

    def _normalize_target_payload(
        self,
        state: Dict[str, Any],
        target: str,
        payload: Dict[str, Any],
        auto_correct: bool,
        warnings: List[str],
    ) -> Dict[str, Any]:
        if target not in STYLE_TARGETS:
            raise ValueError(f"未知风格目标: {target}")
        family_code = payload.get("family_code") or payload.get("art_style_family") or payload.get("family")
        subtype_code = payload.get("subtype_code") or payload.get("art_style_subtype") or payload.get("subtype")
        if not family_code or not subtype_code:
            raise ValueError(f"{target} 风格配置缺少 family_code 或 subtype_code")

        preset = self.registry.get_style_preset(family_code, subtype_code)
        delivery_context = self._extract_delivery_context(state.get("settings", {}))
        media_subtype = delivery_context.get("media_subtype")
        applied_preset = preset

        if media_subtype and media_subtype not in preset.get("applicable_media", []):
            compatible_subtypes = self.registry.find_compatible_subtypes(family_code, media_subtype)
            if auto_correct and compatible_subtypes:
                fallback_subtype = compatible_subtypes[0]["code"]
                applied_preset = self.registry.get_style_preset(family_code, fallback_subtype)
                warnings.append(
                    f"{target} 风格 {subtype_code} 与当前媒介 {media_subtype} 不匹配，已自动回退为 {fallback_subtype}"
                )
            else:
                warnings.append(
                    f"{target} 风格 {subtype_code} 与当前媒介 {media_subtype} 不完全匹配，已保留原选择"
                )

        negative_constraints = payload.get("negative_style_constraints") or payload.get("negative_constraints") or []
        return {
            **applied_preset,
            "negative_style_constraints": list(negative_constraints),
            "source": "structured",
        }

    def _resolve_target_config(self, style_config: Dict[str, Any], target: str) -> Optional[Dict[str, Any]]:
        targets = style_config.get("targets") or {}
        if target in targets:
            return targets[target]
        if target == "keyframe" and "image" in targets:
            return targets["image"]
        if target == "video" and "keyframe" in targets:
            return targets["keyframe"]
        if targets:
            first_target = next(iter(targets.values()))
            return first_target
        return None

    def _extract_delivery_context(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        delivery = settings.get("delivery") or settings.get("format") or {}
        return {
            "media_family": delivery.get("media_family"),
            "media_subtype": delivery.get("media_subtype"),
            "aspect_ratio": delivery.get("aspect_ratio"),
            "frame_rate": delivery.get("frame_rate"),
        }

    def _sync_legacy_visual_settings(self, settings: Dict[str, Any], style_config: Dict[str, Any]) -> None:
        resolved = self._resolve_target_config(style_config, "keyframe") or self._resolve_target_config(style_config, "image")
        if not resolved:
            return
        visual = settings.setdefault("visual", {})
        visual["art_style_family"] = resolved["family_code"]
        visual["art_style_subtype"] = resolved["subtype_code"]

    def _empty_style_config(self) -> Dict[str, Any]:
        return {
            "schema_version": STYLE_CONFIG_SCHEMA_VERSION,
            "registry_version": self.registry.get_registry_version(),
            "version": 0,
            "updated_at": None,
            "targets": {},
        }

    def _project_root(self, project_name: str) -> Path:
        return (self.state_manager.base_dir / project_name).resolve()

    def _current_snapshot_path(self, project_name: str) -> Path:
        return self._project_root(project_name) / "style_config.current.json"

    def _versions_path(self, project_name: str) -> Path:
        return self._project_root(project_name) / "style_config_versions.json"

    def _audit_log_path(self, project_name: str) -> Path:
        return self._project_root(project_name) / "style_config_audit.jsonl"

    def _write_current_snapshot(self, project_name: str, style_config: Dict[str, Any]) -> None:
        snapshot_path = self._current_snapshot_path(project_name)
        snapshot_path.write_text(
            json.dumps(style_config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _append_version_snapshot(
        self,
        project_name: str,
        style_config: Dict[str, Any],
        actor: str,
        change_reason: str,
    ) -> None:
        versions_path = self._versions_path(project_name)
        if versions_path.exists():
            versions_payload = json.loads(versions_path.read_text(encoding="utf-8"))
        else:
            versions_payload = {
                "schema_version": STYLE_CONFIG_SCHEMA_VERSION,
                "project_name": project_name,
                "snapshots": [],
            }
        versions_payload["snapshots"].append(
            {
                "version": style_config["version"],
                "timestamp": style_config["updated_at"],
                "actor": actor,
                "change_reason": change_reason,
                "config": style_config,
            }
        )
        versions_path.write_text(
            json.dumps(versions_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _append_audit_log(
        self,
        project_name: str,
        actor: str,
        action: str,
        change_reason: str,
        payload: Dict[str, Any],
        resulting_version: int,
    ) -> None:
        audit_path = self._audit_log_path(project_name)
        record = {
            "timestamp": _now_iso(),
            "actor": actor,
            "action": action,
            "change_reason": change_reason,
            "payload": payload,
            "resulting_version": resulting_version,
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
