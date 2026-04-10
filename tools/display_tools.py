import os
import sys
import subprocess
from pathlib import Path

def format_clickable_link(text: str, path_or_url: str) -> str:
    """
    格式化绝对路径为终端原生的 OSC 8 可点击超链接。
    在支持的终端（如 iTerm2, VSCode）中，点击该链接可直接打开文件或网页。
    """
    # 确保如果是本地路径，转为 file:// 协议
    if not path_or_url.startswith("http://") and not path_or_url.startswith("https://") and not path_or_url.startswith("file://"):
        abs_path = Path(path_or_url).absolute()
        path_or_url = f"file://{abs_path}"
        
    return f"\033]8;;{path_or_url}\033\\{text}\033]8;;\033\\"

def open_file_natively(file_path: str) -> bool:
    """
    跨平台调用操作系统默认的查看器打开文件（如图片）。
    """
    try:
        abs_path = str(Path(file_path).absolute())
        if sys.platform == "win32":
            os.startfile(abs_path)
        elif sys.platform == "darwin":
            subprocess.call(["open", abs_path])
        else:
            subprocess.call(["xdg-open", abs_path])
        return True
    except Exception as e:
        print(f"[Warning] 无法原生打开文件 {file_path}: {e}")
        return False