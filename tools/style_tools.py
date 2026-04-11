from typing import Any, Dict, Optional

from core.style_config_manager import StyleConfigManager


def list_style_families_state() -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return {
            "style_families": manager.list_style_families(),
            "registry_version": manager.registry.get_registry_version(),
        }
    except Exception as e:
        return {"error": f"读取风格家族失败: {e}"}


def list_style_subtypes_state(style_family: str) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return {
            "style_family": style_family,
            "subtypes": manager.list_style_subtypes(style_family),
            "registry_version": manager.registry.get_registry_version(),
        }
    except Exception as e:
        return {"error": f"读取风格子类失败: {e}"}


def preview_style_preset_state(style_family: str, style_subtype: str) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return {
            "preset": manager.get_style_preset(style_family, style_subtype),
            "registry_version": manager.registry.get_registry_version(),
        }
    except Exception as e:
        return {"error": f"读取风格预设失败: {e}"}


def get_project_style_config_state(project_name: str) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return manager.get_project_style_config(project_name)
    except Exception as e:
        return {"error": f"读取项目风格配置失败: {e}"}


def update_project_style_config_state(
    project_name: str,
    target_styles: Dict[str, Dict[str, Any]],
    actor: str = "agent",
    change_reason: str = "agent update",
    auto_correct: bool = True,
) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return manager.update_project_style_config(
            project_name=project_name,
            target_styles=target_styles,
            actor=actor,
            change_reason=change_reason,
            auto_correct=auto_correct,
        )
    except Exception as e:
        return {"error": f"更新项目风格配置失败: {e}"}


def delete_project_style_config_state(
    project_name: str,
    target: Optional[str] = None,
    actor: str = "agent",
    change_reason: str = "agent delete",
) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return manager.delete_project_style_config(
            project_name=project_name,
            target=target,
            actor=actor,
            change_reason=change_reason,
        )
    except Exception as e:
        return {"error": f"删除项目风格配置失败: {e}"}


def list_project_style_versions_state(project_name: str) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return manager.list_project_style_versions(project_name)
    except Exception as e:
        return {"error": f"读取项目风格版本失败: {e}"}


def get_prompt_style_context_state(project_name: str, target: str) -> Dict[str, Any]:
    manager = StyleConfigManager()
    try:
        return manager.build_prompt_style_context(project_name, target)
    except Exception as e:
        return {"error": f"构建风格注入上下文失败: {e}"}
