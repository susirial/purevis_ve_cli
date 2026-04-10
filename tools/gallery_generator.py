import os
import webbrowser
from pathlib import Path
from core.state_manager import StateManager

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f7;
            color: #333;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 40px;
            color: #1d1d1f;
        }}
        h2 {{
            border-bottom: 2px solid #ddd;
            padding-bottom: 10px;
            margin-top: 40px;
            color: #444;
        }}
        .section {{
            margin-bottom: 50px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }}
        .card img {{
            width: 100%;
            height: auto;
            display: block;
            border-bottom: 1px solid #eee;
        }}
        .card-content {{
            padding: 15px;
        }}
        .card-title {{
            font-size: 16px;
            font-weight: bold;
            margin: 0 0 10px 0;
            word-break: break-all;
        }}
        .card-desc {{
            font-size: 13px;
            color: #666;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="container">
        {sections_html}
    </div>
</body>
</html>
"""

SECTION_TEMPLATE = """
        <div class="section">
            <h2>{section_title}</h2>
            <div class="grid">
                {cards_html}
            </div>
        </div>
"""

CARD_TEMPLATE = """
                <div class="card">
                    <img src="{img_src}" alt="{img_title}" loading="lazy">
                    <div class="card-content">
                        <h3 class="card-title">{img_title}</h3>
                        <div class="card-desc">{img_desc}</div>
                    </div>
                </div>
"""

def generate_html_gallery(title: str, sections: list, output_path: str) -> str:
    """
    根据给定的 sections 生成 HTML 画廊。
    sections 格式: [{"title": "区段名", "cards": [{"title": "图名", "src": "相对或绝对路径", "desc": "描述"}]}]
    """
    sections_html = ""
    
    # 获取输出 HTML 文件所在的目录，为了后续计算图片的相对路径
    html_dir = Path(output_path).parent.absolute()
    
    for sec in sections:
        cards_html = ""
        for card in sec.get("cards", []):
            src_path = Path(card.get("src", ""))
            
            # 如果不是绝对路径，先基于当前工作目录将其转为绝对路径
            if not src_path.is_absolute():
                src_path = src_path.absolute()
            
            # 为了在 HTML 中正常显示，尽量转换为相对于 HTML 文件所在目录的相对路径
            img_src = str(src_path)
            try:
                # 转为基于 html_dir 的相对路径
                img_src = os.path.relpath(src_path, html_dir)
            except ValueError:
                # 无法计算相对路径时（比如不同盘符），使用 file:// 协议
                img_src = f"file://{src_path}"
                    
            cards_html += CARD_TEMPLATE.format(
                img_src=img_src,
                img_title=card.get("title", "未命名"),
                img_desc=card.get("desc", "").replace("\n", "<br>")
            )
            
        if cards_html:
            sections_html += SECTION_TEMPLATE.format(
                section_title=sec.get("title", "未命名分区"),
                cards_html=cards_html
            )
            
    final_html = HTML_TEMPLATE.format(
        title=title,
        sections_html=sections_html or "<p>暂无图片资产</p>"
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    return output_path

def generate_project_dashboard(project_name: str) -> str:
    """
    读取项目的 state.json，提取主体库数据，生成全量资产的 HTML 仪表盘，并自动在浏览器中打开。
    """
    sm = StateManager()
    try:
        state = sm.load_state(project_name)
    except FileNotFoundError:
        return f"错误：未找到项目 '{project_name}' 的状态数据。"
        
    sections = []
    
    # 处理主体库 (Subjects)
    subjects = state.get("subjects", [])
    if subjects:
        # 按照 subject type 进行聚合分类
        grouped_subjects = {}
        for sub in subjects:
            stype = sub.get("type", "other")
            grouped_subjects.setdefault(stype, []).append(sub)
            
        for stype, subs in grouped_subjects.items():
            cards = []
            for sub in subs:
                sub_name = sub.get("name", "未命名")
                for img in sub.get("images", []):
                    img_id = img.get("id", img.get("path", ""))
                    desc = img.get("description", "")
                    variant = img.get("variant", "")
                    
                    full_desc = f"<b>变体:</b> {variant}<br>" if variant else ""
                    if desc:
                        full_desc += f"<b>描述:</b> {desc}"
                        
                    cards.append({
                        "title": img_id,
                        "src": img.get("path", ""),
                        "desc": full_desc
                    })
                    
            if cards:
                # 简单翻译 type
                type_zh = {"character": "人物库", "scene": "场景库", "prop": "物品库", "animal": "动物库"}.get(stype, f"{stype.capitalize()}库")
                sections.append({
                    "title": f"🎭 主体资产 - {type_zh}",
                    "cards": cards
                })
                
    # todo: 未来可以在这里扩展处理 episodes (剧集/分镜关键帧) 的图片
    
    # 确定输出路径 (projects/<name>/dashboard.html)
    proj_dir = sm._get_project_dir(project_name)
    out_path = str(proj_dir / "dashboard.html")
    
    generate_html_gallery(f"🎬 短剧项目仪表盘 - {project_name}", sections, out_path)
    
    # 自动在默认浏览器中打开
    abs_path = Path(out_path).absolute()
    file_url = abs_path.as_uri()
    try:
        webbrowser.open(file_url)
    except Exception as e:
        print(f"[Warning] 无法自动打开浏览器: {e}")
        
    return f"成功生成并打开项目仪表盘：{out_path}"
