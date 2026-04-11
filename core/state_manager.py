import json
import shutil
from pathlib import Path
from typing import Dict, Any, List

class StateManager:
    """
    状态管理与多项目/多集/主体库目录结构
    """
    def __init__(self, base_dir: str = "output/projects"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, name: str) -> Path:
        return self.base_dir / name

    def _get_state_file(self, name: str) -> Path:
        return self._get_project_dir(name) / "state.json"

    def list_all_projects(self) -> List[str]:
        """列出所有已创建的项目名称"""
        if not self.base_dir.exists():
            return []
        projects = []
        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue
            if (item / "state.json").exists():
                projects.append(item.name)
                continue
            if (item / "episodes").is_dir() or (item / "subjects").is_dir():
                projects.append(item.name)
        return sorted(projects)

    def repair_state_if_missing(self, project_name: str) -> Dict[str, Any]:
        project_dir = self._get_project_dir(project_name)
        if not project_dir.exists():
            raise FileNotFoundError(f"未找到项目 '{project_name}' 的目录。")

        state_file = self._get_state_file(project_name)
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)

        (project_dir / "subjects").mkdir(parents=True, exist_ok=True)
        (project_dir / "episodes").mkdir(parents=True, exist_ok=True)

        episodes: Dict[str, Any] = {}
        episodes_dir = project_dir / "episodes"
        if episodes_dir.is_dir():
            for ep_dir in sorted(episodes_dir.iterdir(), key=lambda p: p.name):
                if not ep_dir.is_dir():
                    continue
                episode_id = ep_dir.name
                episodes[episode_id] = {
                    "id": episode_id,
                    "status": "recovered",
                    "progress": {}
                }

        state = {
            "name": project_name,
            "settings": {},
            "subjects": [],
            "episodes": episodes
        }
        self.save_state(project_name, state)
        return state

    def create_project(self, name: str) -> Dict[str, Any]:
        """SubTask 1.1: 创建项目"""
        project_dir = self._get_project_dir(name)
        if project_dir.exists():
            raise FileExistsError(f"项目 '{name}' 已存在。")
        
        # 创建目录结构
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "subjects").mkdir(exist_ok=True)
        (project_dir / "episodes").mkdir(exist_ok=True)
        
        # 初始化状态并序列化 (SubTask 1.5)
        state = {
            "name": name,
            "settings": {},
            "subjects": [],
            "episodes": {}
        }
        self.save_state(name, state)
        return state

    def delete_project(self, name: str) -> None:
        """SubTask 1.1: 删除项目"""
        project_dir = self._get_project_dir(name)
        if project_dir.exists():
            shutil.rmtree(project_dir)

    def load_state(self, name: str) -> Dict[str, Any]:
        """SubTask 1.5: 读取项目状态 JSON"""
        state_file = self._get_state_file(name)
        if not state_file.exists():
            project_dir = self._get_project_dir(name)
            if project_dir.exists() and ((project_dir / "episodes").is_dir() or (project_dir / "subjects").is_dir()):
                return self.repair_state_if_missing(name)
            raise FileNotFoundError(f"未找到项目 '{name}' 的状态文件。")
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def discover_subject_assets(self, project_name: str) -> Dict[str, Any]:
        project_dir = self._get_project_dir(project_name)
        if not project_dir.exists():
            raise FileNotFoundError(f"未找到项目 '{project_name}' 的目录。")

        subjects_dir = project_dir / "subjects"
        registered_subject_names = self._get_registered_subject_names(project_name)
        if not subjects_dir.exists():
            return {
                "project_name": project_name,
                "subject_root": str(subjects_dir),
                "registered_subject_names": registered_subject_names,
                "discovered_subjects": [],
                "discovered_count": 0,
            }

        discovered: Dict[str, Dict[str, Any]] = {}
        for item in sorted(subjects_dir.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower())):
            if item.is_dir():
                subject_name = item.name.strip()
                record = discovered.setdefault(subject_name, _build_discovered_subject_record(subject_name))
                _append_unique(record["source_paths"], str(item))
                for child in sorted(item.rglob("*"), key=lambda path: str(path).lower()):
                    if not child.is_file():
                        continue
                    _append_discovered_asset(record, child)
                continue

            if not item.is_file():
                continue

            if _is_text_asset(item) and not _is_subject_design_doc(item):
                continue

            subject_name = _infer_subject_name(item)
            record = discovered.setdefault(subject_name, _build_discovered_subject_record(subject_name))
            _append_unique(record["source_paths"], str(item))
            _append_discovered_asset(record, item)

        discovered_subjects = []
        for subject_name, record in discovered.items():
            if subject_name in registered_subject_names:
                continue
            if not record["design_docs"] and not record["images"] and not record["source_paths"]:
                continue
            discovered_subjects.append(record)

        discovered_subjects.sort(key=lambda item: item["name"])
        return {
            "project_name": project_name,
            "subject_root": str(subjects_dir),
            "registered_subject_names": registered_subject_names,
            "discovered_subjects": discovered_subjects,
            "discovered_count": len(discovered_subjects),
        }

    def save_state(self, name: str, state: Dict[str, Any]) -> None:
        """SubTask 1.5: 序列化项目状态到 JSON 文件"""
        state_file = self._get_state_file(name)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)

    def update_project_settings(self, project_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新项目全局配置 (支持增量更新)
        """
        state = self.load_state(project_name)
        if "settings" not in state:
            state["settings"] = {}

        state["settings"] = _deep_merge_dicts(state["settings"], settings)
        self.save_state(project_name, state)
        return state["settings"]

    def get_project_settings(self, project_name: str) -> Dict[str, Any]:
        """
        获取项目全局配置
        """
        state = self.load_state(project_name)
        return state.get("settings", {})

    def add_episode(self, project_name: str, episode_id: str) -> Dict[str, Any]:
        """
        SubTask 1.2 & 1.4: 允许在项目中添加剧集，并建立专属输出目录结构。
        """
        state = self.load_state(project_name)
        if episode_id in state.get("episodes", {}):
            raise ValueError(f"剧集 '{episode_id}' 已存在于项目 '{project_name}' 中。")
        
        episode_dir = self._get_project_dir(project_name) / "episodes" / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        # SubTask 1.4: 建立剧集专属的输出目录结构
        (episode_dir / "scripts").mkdir(exist_ok=True)       # 剧本
        (episode_dir / "storyboard").mkdir(exist_ok=True)    # 图片分镜
        (episode_dir / "keyframes").mkdir(exist_ok=True)     # 关键帧
        (episode_dir / "video").mkdir(exist_ok=True)         # 分镜视频
        
        episode_state = {
            "id": episode_id,
            "status": "created",
            "progress": {}
        }
        state["episodes"][episode_id] = episode_state
        self.save_state(project_name, state)
        return episode_state

    def add_subject_image(self, project_name: str, subject_name: str, subject_type: str, image_path: str, description: str = "", structured_name: str = "", variant_desc: str = "") -> Dict[str, Any]:
        """
        SubTask 1.3: 主体库（Subject Library）管理，支持为主体添加多张图片。
        subject_type: 角色 (character) / 场景 (scene) / 物品 (prop) 等
        """
        state = self.load_state(project_name)
        
        # 查找或创建主体
        subject = None
        for sub in state.get("subjects", []):
            if sub["name"] == subject_name:
                subject = sub
                break
                
        if not subject:
            subject = {
                "name": subject_name,
                "type": subject_type,
                "images": []
            }
            state.setdefault("subjects", []).append(subject)
            
        # 建立主体库专属目录 projects/<project_name>/subjects/<subject_name>/
        subject_dir = self._get_project_dir(project_name) / "subjects" / subject_name
        subject_dir.mkdir(parents=True, exist_ok=True)
        
        src_path = Path(image_path)
        if not src_path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
            
        # 复制图片到主体库中，使用结构化名称重命名文件
        ext = src_path.suffix
        file_name = f"{structured_name}{ext}" if structured_name else src_path.name
        dest_path = subject_dir / file_name
        
        # 防止覆盖
        counter = 1
        while dest_path.exists() and str(src_path.absolute()) != str(dest_path.absolute()):
            dest_path = subject_dir / f"{structured_name}_{counter}{ext}"
            counter += 1

        if str(src_path.absolute()) != str(dest_path.absolute()):
            shutil.copy2(src_path, dest_path)
            
        image_record = {
            "id": structured_name or file_name,
            "path": str(dest_path),
            "description": description,
            "variant": variant_desc
        }
        subject["images"].append(image_record)
        
        self.save_state(project_name, state)
        return state

    def get_episode_dir(self, project_name: str, episode_id: str) -> Path:
        """获取某集的主目录"""
        return self._get_project_dir(project_name) / "episodes" / episode_id

    def _get_registered_subject_names(self, project_name: str) -> List[str]:
        state_file = self._get_state_file(project_name)
        if not state_file.exists():
            return []
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return []
        subjects = state.get("subjects", []) or []
        names = []
        for subject in subjects:
            if isinstance(subject, dict) and subject.get("name"):
                names.append(str(subject["name"]))
        return names


def _deep_merge_dicts(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in incoming.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(existing, value)
            continue
        result[key] = value
    return result


def _build_discovered_subject_record(subject_name: str) -> Dict[str, Any]:
    return {
        "name": subject_name,
        "status": "discovered",
        "design_docs": [],
        "images": [],
        "source_paths": [],
    }


def _append_discovered_asset(record: Dict[str, Any], asset_path: Path) -> None:
    asset_record = {"path": str(asset_path)}
    if _is_text_asset(asset_path):
        _append_unique(record["design_docs"], asset_record)
    elif _is_image_asset(asset_path):
        _append_unique(record["images"], asset_record)


def _append_unique(items: List[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _is_text_asset(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown", ".txt"}


def _is_subject_design_doc(path: Path) -> bool:
    stem = path.stem.strip()
    return any(
        stem.endswith(suffix)
        for suffix in ["_角色设定", "_场景设定", "_物品设定", "_设定", "-设定", " 设定"]
    )


def _is_image_asset(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _infer_subject_name(path: Path) -> str:
    stem = path.stem.strip()
    for suffix in ["_角色设定", "_场景设定", "_物品设定", "_设定", "-设定", " 设定"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)].strip()
            break
    return stem or path.stem
