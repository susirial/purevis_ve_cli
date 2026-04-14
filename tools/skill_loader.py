"""
Skill Loader - 渐进式披露技能加载系统

基于 Anthropic Agent Skills 规范，提供三层上下文加载：
  L1: 元数据（name + description）始终可见
  L2: SKILL.md 正文按需加载
  L3: references/ 内文档按需读取
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)


def _parse_frontmatter(skill_md: Path) -> Tuple[str, str]:
    """从 SKILL.md 解析 YAML frontmatter，返回 (name, description)。"""
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return (skill_md.parent.name, "")

    block = match.group(1)
    name = ""
    desc = ""
    for line in block.splitlines():
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
    return (name or skill_md.parent.name, desc)


def _list_references(skill_dir: Path) -> List[str]:
    """列出 skill 目录下 references/ 中的文件名。"""
    ref_dir = skill_dir / "references"
    if not ref_dir.is_dir():
        return []
    return sorted(f.name for f in ref_dir.iterdir() if f.is_file())


def _get_body(skill_md: Path) -> str:
    """提取 SKILL.md 中 frontmatter 之后的正文部分。"""
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if match:
        return text[match.end():].strip()
    return text.strip()


def list_available_skills() -> Dict[str, Any]:
    """
    列出所有可用的技能及其简要描述（L1 元数据层）。
    当你需要了解系统具备哪些专业能力，或者不确定应该加载哪个技能时调用。
    返回值中每个技能包含 name 和 description。
    """
    if not SKILLS_DIR.is_dir():
        return {"skills": [], "count": 0, "error": "skills/ 目录不存在。"}

    skills: List[Dict[str, str]] = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        name, desc = _parse_frontmatter(skill_md)
        skills.append({"name": name, "description": desc})

    return {"skills": skills, "count": len(skills)}


def load_skill(skill_name: str) -> Dict[str, Any]:
    """
    加载指定技能的完整工作流指令（L2 指令层）。
    当你判断当前任务需要某个专业技能的工作流规则和操作指南时调用。
    返回技能正文指令以及可用的参考文档列表。

    Args:
        skill_name: 技能名称，如 "style-configuration"、"project-management" 等。
    """
    skill_dir = SKILLS_DIR / skill_name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        available = list_available_skills()
        names = [s["name"] for s in available.get("skills", [])]
        return {
            "error": f"技能 '{skill_name}' 不存在。",
            "available_skills": names,
        }

    name, description = _parse_frontmatter(skill_md)
    body = _get_body(skill_md)
    references = _list_references(skill_dir)

    return {
        "skill_name": name,
        "description": description,
        "instructions": body,
        "available_references": references,
    }


def load_skill_reference(skill_name: str, reference_file: str) -> Dict[str, Any]:
    """
    加载技能的参考文档（L3 资源层），如详细规范、术语表、对比表等。
    仅在执行技能工作流过程中需要查阅细节时调用。

    Args:
        skill_name: 技能名称。
        reference_file: references/ 目录下的文件名，如 "composition-techniques.md"。
    """
    ref_path = SKILLS_DIR / skill_name / "references" / reference_file
    if not ref_path.exists():
        available = _list_references(SKILLS_DIR / skill_name)
        return {
            "error": f"参考文档 '{reference_file}' 不存在于技能 '{skill_name}' 中。",
            "available_references": available,
        }

    content = ref_path.read_text(encoding="utf-8")
    return {
        "skill_name": skill_name,
        "reference_file": reference_file,
        "content": content,
    }
