import os
import shutil
import urllib.request
from pathlib import Path

def save_text_file(content: str, filepath: str) -> None:
    """
    SubTask 2.1: 保存文本文件。如果目录不存在则自动创建。
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def read_text_file(filepath: str) -> str:
    """
    SubTask 2.1: 读取文本文件。
    如果传入的是目录，将返回错误提示，引导大模型使用 list_directory 工具。
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    if path.is_dir():
        return f"[错误] '{filepath}' 是一个目录。请使用 list_directory 工具查看目录内容，或提供具体的文件路径进行读取。"
        
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def list_directory(dir_path: str, max_depth: int = 2) -> str:
    """
    列出指定目录下的所有文件和子目录结构 (Tree format)。
    当你想知道某个目录中有哪些文件时调用此工具。
    为了防止输出过长导致上下文超限，默认最大递归深度为 2。
    """
    path = Path(dir_path)
    if not path.exists():
        return f"[错误] 路径不存在: {dir_path}"
    if not path.is_dir():
        return f"[错误] 路径不是一个目录: {dir_path}"
        
    def generate_tree(current_path, prefix="", depth=1):
        if depth > max_depth:
            return prefix + "└── ... (已达到最大深度限制)\n"
            
        tree_str = ""
        try:
            items = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for i, item in enumerate(items):
                is_last = (i == len(items) - 1)
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    tree_str += f"{prefix}{connector}{item.name}/\n"
                    extension = "    " if is_last else "│   "
                    tree_str += generate_tree(item, prefix + extension, depth + 1)
                else:
                    size_kb = item.stat().st_size / 1024
                    tree_str += f"{prefix}{connector}{item.name} ({size_kb:.1f} KB)\n"
        except PermissionError:
            tree_str += prefix + "└── [权限被拒绝]\n"
            
        return tree_str

    header = f"📁 {path.absolute()}\n"
    body = generate_tree(path, depth=1)
    if not body:
        return header + "(空目录)"
    return header + body

def download_and_save_media(url: str, filepath: str) -> None:
    """
    SubTask 2.2: 下载并保存媒体文件 (图片、视频等)。
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        with open(path, "wb") as f:
            f.write(response.read())

def delete_file(filepath: str) -> str:
    """
    删除仓库内的文件或目录。
    仅允许删除当前项目仓库中的路径，防止越界删除。
    """
    path = Path(filepath).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()

    repo_root = Path(__file__).resolve().parent.parent
    try:
        path.relative_to(repo_root)
    except ValueError:
        raise ValueError(f"不允许删除仓库外的路径: {filepath}")

    if not path.exists():
        raise FileNotFoundError(f"路径不存在: {filepath}")

    if path.is_dir():
        shutil.rmtree(path)
        return f"已删除目录: {path}"

    path.unlink()
    return f"已删除文件: {path}"
