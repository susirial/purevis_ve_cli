import os
import base64
from pathlib import Path

def display_image_in_terminal(image_path: str) -> None:
    """
    SubTask 2.3: 在终端使用 iTerm2 协议渲染图片 (内联显示)。
    注意：此协议主要在 iTerm2, WezTerm 等支持图片内联显示的终端中有效。
    如果在不支持的终端中运行，通常会被忽略或输出乱码。
    """
    path = Path(image_path)
    if not path.exists():
        print(f"[错误] 无法显示图片: 文件不存在 {image_path}")
        return

    try:
        with open(path, "rb") as img_file:
            img_data = img_file.read()
            b64_data = base64.b64encode(img_data).decode("utf-8")
            b64_name = base64.b64encode(path.name.encode("utf-8")).decode("utf-8")
            
            # 使用 iTerm2 的图片显示控制序列
            # OSC 1337 ; File=[args]:[base64] BEL
            print(f"\033]1337;File=name={b64_name};inline=1:{b64_data}\a")
    except Exception as e:
        print(f"[错误] 渲染图片失败 {image_path}: {str(e)}")
