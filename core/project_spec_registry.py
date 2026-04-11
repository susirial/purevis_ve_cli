from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectSpecRegistry:
    def __init__(self, spec_path: Optional[str] = None):
        default_path = Path(__file__).resolve().parent.parent / ".trae" / "documents" / "project-configuration-spec.md"
        self.spec_path = Path(spec_path) if spec_path else default_path

    def get_registry_payload(self) -> Dict[str, Any]:
        return _load_registry(self.spec_path)

    def get_registry_version(self) -> str:
        payload = self.get_registry_payload()
        return str(payload["registry_version"])

    def list_style_families(self) -> List[Dict[str, Any]]:
        payload = self.get_registry_payload()
        return payload["style_families"]

    def list_media_families(self) -> List[Dict[str, Any]]:
        payload = self.get_registry_payload()
        return payload["media_families"]

    def list_style_subtypes(self, family_code: str) -> List[Dict[str, Any]]:
        family = self.get_style_family(family_code)
        return family.get("subtypes", [])

    def list_media_subtypes(self, family_code: str) -> List[Dict[str, Any]]:
        family = self.get_media_family(family_code)
        return family.get("subtypes", [])

    def get_style_family(self, family_code: str) -> Dict[str, Any]:
        payload = self.get_registry_payload()
        for family in payload["style_families"]:
            if family["code"] == family_code:
                return family
        raise ValueError(f"未知风格家族: {family_code}")

    def get_media_family(self, family_code: str) -> Dict[str, Any]:
        payload = self.get_registry_payload()
        for family in payload["media_families"]:
            if family["code"] == family_code:
                return family
        raise ValueError(f"未知媒介家族: {family_code}")

    def get_style_preset(self, family_code: str, subtype_code: str) -> Dict[str, Any]:
        family = self.get_style_family(family_code)
        for subtype in family.get("subtypes", []):
            if subtype["code"] == subtype_code:
                return {
                    "family_code": family["code"],
                    "family_label": family["label"],
                    "subtype_code": subtype["code"],
                    "subtype_summary": subtype.get("summary", ""),
                    "applicable_media": subtype.get("applicable_media", []),
                    "recommended_palette": subtype.get("recommended_palette", []),
                    "recommended_camera": subtype.get("recommended_camera", []),
                    "surface_treatment": subtype.get("surface_treatment", []),
                    "audience_tags": subtype.get("audience_tags", []),
                }
        raise ValueError(f"未知风格子类: {family_code}/{subtype_code}")

    def find_compatible_subtypes(self, family_code: str, media_subtype: str) -> List[Dict[str, Any]]:
        family = self.get_style_family(family_code)
        matches = []
        for subtype in family.get("subtypes", []):
            if media_subtype in subtype.get("applicable_media", []):
                matches.append(subtype)
        return matches

    def is_valid_media_subtype(self, media_subtype: str) -> bool:
        for family in self.list_media_families():
            for subtype in family.get("subtypes", []):
                if subtype["code"] == media_subtype:
                    return True
        return False


@lru_cache(maxsize=4)
def _load_registry(spec_path: Path) -> Dict[str, Any]:
    if not spec_path.exists():
        raise FileNotFoundError(f"未找到项目配置文档: {spec_path}")

    text = spec_path.read_text(encoding="utf-8")
    style_registry_block = _extract_section(
        text,
        "#### 3.1.2 一级风格家族 → 二级子类标准枚举表",
        "#### 3.1.3 二级子类推荐数据结构",
    )
    media_registry_block = _extract_section(
        text,
        "#### 3.2.1 媒介分类扩展清单",
        "### 3.3 内容基调与世界观 (Narrative & Worldbuilding)",
    )

    return {
        "registry_version": spec_path.stat().st_mtime_ns,
        "spec_path": str(spec_path),
        "style_families": _parse_style_registry(style_registry_block),
        "media_families": _parse_media_registry(media_registry_block),
    }


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        raise ValueError(f"项目配置文档缺少章节: {start_marker} -> {end_marker}")
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end].strip()


def _parse_style_registry(block: str) -> List[Dict[str, Any]]:
    families: List[Dict[str, Any]] = []
    current_family: Optional[Dict[str, Any]] = None
    family_pattern = re.compile(r"^- \*\*(?P<label_en>[^*]+?) / (?P<label_zh>[^*]+?)\*\*$")
    subtype_pattern = re.compile(
        r"^  - `(?P<code>[^`]+)`：适配 `(?P<media>[^`]+)`；色板 `(?P<palette>[^`]+)`；镜头 `(?P<camera>[^`]+)`；材质 `(?P<surface>[^`]+)`；受众 `(?P<audience>[^`]+)`$"
    )

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        family_match = family_pattern.match(line)
        if family_match:
            current_family = {
                "code": family_match.group("label_en").strip(),
                "label": family_match.group("label_zh").strip(),
                "subtypes": [],
            }
            families.append(current_family)
            continue
        subtype_match = subtype_pattern.match(line)
        if subtype_match and current_family is not None:
            current_family["subtypes"].append(
                {
                    "code": subtype_match.group("code").strip(),
                    "summary": line.split("：", 1)[1].strip(),
                    "applicable_media": _split_tokens(subtype_match.group("media")),
                    "recommended_palette": _split_tokens(subtype_match.group("palette")),
                    "recommended_camera": _split_tokens(subtype_match.group("camera")),
                    "surface_treatment": _split_tokens(subtype_match.group("surface")),
                    "audience_tags": _split_tokens(subtype_match.group("audience")),
                }
            )
    if not families:
        raise ValueError("未能从项目配置文档中解析任何风格家族")
    return families


def _parse_media_registry(block: str) -> List[Dict[str, Any]]:
    families: List[Dict[str, Any]] = []
    current_family: Optional[Dict[str, Any]] = None
    family_pattern = re.compile(r"^- \*\*(?P<label_zh>[^*]+?) / (?P<label_en>[^*]+?)\*\*$")
    subtype_pattern = re.compile(r"^  - `(?P<code>[^`]+)` (?P<label>[^：]+)：(?P<description>.+)$")

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        family_match = family_pattern.match(line)
        if family_match:
            current_family = {
                "code": family_match.group("label_en").strip(),
                "label": family_match.group("label_zh").strip(),
                "subtypes": [],
            }
            families.append(current_family)
            continue
        subtype_match = subtype_pattern.match(line)
        if subtype_match and current_family is not None:
            current_family["subtypes"].append(
                {
                    "code": subtype_match.group("code").strip(),
                    "label": subtype_match.group("label").strip(),
                    "description": subtype_match.group("description").strip(),
                }
            )
    if not families:
        raise ValueError("未能从项目配置文档中解析任何媒介家族")
    return families


def _split_tokens(raw: str) -> List[str]:
    tokens = []
    for chunk in re.split(r",| / ", raw):
        token = chunk.strip()
        if token:
            tokens.append(token)
    return tokens
