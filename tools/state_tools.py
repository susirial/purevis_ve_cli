from core.state_manager import StateManager
from typing import Dict, Any
from tools.gallery_generator import generate_project_dashboard


def open_project_dashboard_state(project_name: str) -> Dict[str, Any]:
    """
    打开并渲染当前项目的全量图片资产画廊（Project Asset Dashboard）。
    当用户想要直观地查看当前项目生成了哪些角色图片、场景图片等资产时，调用此工具。
    系统会生成一个 HTML 页面并在浏览器中自动打开。
    """
    try:
        msg = generate_project_dashboard(project_name)
        return {"message": msg}
    except Exception as e:
        return {"error": f"生成或打开项目仪表盘失败: {e}"}

def list_all_projects_state() -> Dict[str, Any]:
    """
    当用户没有指定项目名，或者你想知道目前有哪些项目可以查询时，调用此工具。
    """
    sm = StateManager()
    try:
        projects = sm.list_all_projects()
        recoverable_projects = []
        warnings = []
        for project_name in projects:
            state_file = sm.base_dir / project_name / "state.json"
            if not state_file.exists():
                recoverable_projects.append(project_name)
                warnings.append(f"项目 '{project_name}' 缺少 state.json，可通过 get_project_state 自动修复。")
        return {
            "projects": projects,
            "count": len(projects),
            "recoverable_projects": recoverable_projects,
            "warnings": warnings
        }
    except Exception as e:
        return {"error": f"列出项目失败: {e}"}

def create_project_state(project_name: str) -> Dict[str, Any]:
    """
    创建一个新的短剧项目状态管理目录。
    如果项目已存在，则会报错。
    """
    sm = StateManager()
    try:
        return sm.create_project(project_name)
    except FileExistsError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"创建项目失败: {e}"}

def get_project_state(project_name: str = None) -> Dict[str, Any]:
    """
    获取当前短剧项目的整体状态和资产列表（包括配置、已创建的剧集、已生成的角色/场景/物品图片等）。
    当你需要知道项目有哪些角色图片、场景图片，或者项目进行到什么阶段时，调用此工具。
    如果 project_name 为空，将会尝试列出当前所有项目提示用户。
    """
    if not project_name:
        return list_all_projects_state()
        
    sm = StateManager()
    try:
        return sm.load_state(project_name)
    except FileNotFoundError:
        return {"error": f"项目 '{project_name}' 不存在或尚未初始化状态。"}
    except Exception as e:
        return {"error": f"读取项目状态失败: {e}"}

def add_subject_image_state(project_name: str, subject_name: str, subject_type: str, image_path: str, description: str = "", variant_desc: str = "参考图") -> Dict[str, Any]:
    """
    向项目的主体库（Subject Library）中添加一张主体图片（角色、场景、物品等）。
    当图片生成完毕并保存到本地后，必须调用此工具将图片路径记录到项目的状态管理中。
    subject_type 必须是 'character', 'scene' 或 'prop' 之一。
    variant_desc: 对图片的变体描述（如 '人物参考图', '多视图', '穿短裙'），将用于生成结构化名称。
    """
    sm = StateManager()
    try:
        type_map = {
            "character": "人物", 
            "scene": "场景", 
            "prop": "物品",
            "animal": "动物",
            "vehicle": "车辆"
        }
        # 通用 fallback 逻辑：如果在字典中找不到，就尝试将其首字母大写（如 mecha -> Mecha）
        zh_type = type_map.get(subject_type, str(subject_type).capitalize())
        
        structured_name = f"主体_{zh_type}_{subject_name}_{variant_desc}"
        
        return sm.add_subject_image(
            project_name=project_name, 
            subject_name=subject_name, 
            subject_type=subject_type, 
            image_path=image_path, 
            description=description,
            structured_name=structured_name,
            variant_desc=variant_desc
        )
    except Exception as e:
        return {"error": f"添加主体图片失败: {e}"}

def update_project_settings_state(project_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新项目的全局配置项（如视觉风格 art_style、目标媒介 aspect_ratio 等）。
    可以增量更新。传入一个字典，字典中包含要更新的配置项和值。
    """
    sm = StateManager()
    try:
        return sm.update_project_settings(project_name, settings)
    except Exception as e:
        return {"error": f"更新项目配置失败: {e}"}

def add_episode_state(project_name: str, episode_id: str) -> Dict[str, Any]:
    """
    向项目中添加一个新的剧集（例如 'ep01'），并为其建立专属的输出目录结构。
    """
    sm = StateManager()
    try:
        return sm.add_episode(project_name, episode_id)
    except Exception as e:
        return {"error": f"添加剧集失败: {e}"}
