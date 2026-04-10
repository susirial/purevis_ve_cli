import os
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
try:
    import tiktoken
except Exception:
    tiktoken = None
try:
    from rich.console import Console
    from rich.markdown import Markdown
except Exception:
    from contextlib import nullcontext

    class Console:
        def print(self, *args, **kwargs):
            builtins_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print
            builtins_print(*args)

        def status(self, *args, **kwargs):
            return nullcontext()

    class Markdown(str):
        pass
from tools.display_tools import format_clickable_link

logger = logging.getLogger(__name__)


def _get_session_service(runner):
    """统一获取 session_service 的入口，优先使用 ADK Runner 的标准属性。"""
    if hasattr(runner, 'session_service') and runner.session_service:
        return runner.session_service
    if hasattr(runner, 'short_term_memory') and hasattr(runner.short_term_memory, 'session_service'):
        return runner.short_term_memory.session_service
    return None

def _extract_event_text(event) -> str:
    content = getattr(event, "content", None)
    if not content:
        return ""
    role = getattr(content, "role", "unknown")
    parts = getattr(content, "parts", []) or []
    chunks = [f"role:{role}"]
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            chunks.append(str(text))
        function_call = getattr(part, "function_call", None)
        if function_call:
            chunks.append(f"function_call:{getattr(function_call, 'name', '')}")
            chunks.append(str(getattr(function_call, "args", "")))
        function_response = getattr(part, "function_response", None)
        if function_response:
            chunks.append(f"function_response:{getattr(function_response, 'name', '')}")
            chunks.append(str(getattr(function_response, "response", "")))
    return "\n".join(chunks)

def _count_text_tokens(text: str, encoding) -> int:
    if not text:
        return 0
    if encoding:
        try:
            return len(encoding.encode(text, disallowed_special=()))
        except Exception:
            return len(text) // 4
    return len(text) // 4

def _is_summary_event(event) -> bool:
    if not event:
        return False
    if getattr(event, "author", "") == "memory_summarizer":
        return True
    content = getattr(event, "content", None)
    if not content:
        return False
    for part in getattr(content, "parts", []) or []:
        text = getattr(part, "text", "")
        if text and "[History Summary of previous" in text:
            return True
    return False

async def count_session_tokens(runner, app_name="purevis_app", user_id="user_01", session_id="session_01") -> int:
    """
    计算当前 session 中 events 的总 token 数。
    使用 tiktoken 做近似计算。
    """
    events = await get_current_session_events(runner, app_name, user_id, session_id)
    if not events:
        return 0
        
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = None
        
    total_tokens = 0
    for event in events:
        total_tokens += _count_text_tokens(_extract_event_text(event), encoding)
            
    return total_tokens

async def custom_compact_session_memory(runner, app_name="purevis_app", user_id="user_01", session_id="session_01", limit=None):
    """
    压缩当前 session 的历史记录。
    如果未提供 limit，则压缩前一半的用户对话轮次。
    将前一半记录使用 veadk.Runner 总结后替换。
    """
    events = await get_current_session_events(runner, app_name, user_id, session_id)
    if not events:
        return False

    if limit is None:
        compact_event_num = len(events)
        limit_display = "all"
    else:
        compact_event_num = 0
        compact_counter = 0
        for event in events:
            if getattr(getattr(event, 'content', None), 'role', '') == 'user':
                compact_counter += 1
                if compact_counter > limit:
                    break
            compact_event_num += 1
        limit_display = str(limit)

    if compact_event_num == 0:
        return False

    events_need_compact = events[:compact_event_num]
    original_token_estimate = 0
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = None

    event_text = ""
    for event in events_need_compact:
        role = getattr(getattr(event, 'content', None), 'role', 'unknown')
        text_parts = []
        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_parts.append(part.text)
        content_text = " ".join(text_parts)
        original_token_estimate += _count_text_tokens(content_text, encoding)
        event_text += f"- Role: {role}\nContent: {content_text}\n"

    from veadk import Agent, Runner as VeadkRunner
    summarizer_agent = Agent(
        name="history_summarizer",
        description="Summarizes chat history",
        instruction="Summarize the following chat history events concisely. Focus on the main topics and decisions made.",
        model_name="deepseek-v3-2-251201"
    )
    summarizer_runner = VeadkRunner(agent=summarizer_agent)
    summary_response = await summarizer_runner.run(
        messages=(
            "请压缩以下历史为简洁备忘，保留目标、关键事实、关键决策、待办与约束。"
            "输出不超过 4000 中文字符。\n\nEvents are:\n" + event_text
        )
    )
    summary_text = str(summary_response).strip()
    if not summary_text:
        return False
    max_summary_chars = 4000
    max_summary_tokens_by_ratio = max(200, int(original_token_estimate * 0.35))
    max_summary_tokens = min(max_summary_tokens_by_ratio, max_summary_chars * 2)
    current_summary_tokens = _count_text_tokens(summary_text, encoding)
    if current_summary_tokens > max_summary_tokens:
        if encoding:
            token_ids = encoding.encode(summary_text, disallowed_special=())
            summary_text = encoding.decode(token_ids[:max_summary_tokens]).strip()
        else:
            summary_text = summary_text[:max(800, max_summary_tokens * 4)].strip()
    if len(summary_text) > max_summary_chars:
        summary_text = summary_text[:max_summary_chars].strip()

    from google.adk.events import Event
    from google.genai.types import Content, Part
    
    summary_event = Event(
        author="memory_summarizer",
        content=Content(
            role="model",
            parts=[Part(text=f"[History Summary of previous {limit_display} interactions]:\n{summary_text}")]
        )
    )

    session_service = _get_session_service(runner)
    if not session_service:
        logger.error("No session_service found on runner")
        return False

    remaining_events = list(events[compact_event_num:])
    new_events = [summary_event] + remaining_events

    try:
        await session_service.delete_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        new_session = await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        for evt in new_events:
            await session_service.append_event(new_session, evt)
    except Exception as e:
        logger.error(f"Failed to persist compacted session: {e}")
        return False

    verify_session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    verify_events = getattr(verify_session, "events", []) if verify_session else []
    return bool(verify_events) and _is_summary_event(verify_events[0])

async def get_current_session_events(runner, app_name="purevis_app", user_id="user_01", session_id="session_01"):
    """
    获取当前会话的 events 列表。
    通过 runner.session_service（ADK 标准属性）访问。
    """
    session_service = _get_session_service(runner)
    if not session_service:
        return []
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if session and hasattr(session, 'events'):
        return session.events
    return []

async def clear_current_session(runner, app_name="purevis_app", user_id="user_01", session_id="session_01"):
    """
    清理当前会话：删除后重建空 session，确保后续对话正常。
    """
    session_service = _get_session_service(runner)
    if not session_service:
        return False
    try:
        await session_service.delete_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        return True
    except Exception as e:
        logger.error(f"Failed to clear session: {e}")
        return False

async def import_session_memory(runner, filepath: str, app_name="purevis_app", user_id="user_01", session_id="session_01"):
    """
    从指定文件读取内容作为历史上下文，并将其作为总结事件插入到当前 session 的最前。
    """
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        return False, f"File not found: {filepath}"
        
    try:
        content_text = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Failed to read file: {e}"

    events = await get_current_session_events(runner, app_name, user_id, session_id)
    
    from google.adk.events import Event
    from google.genai.types import Content, Part
    
    import_event = Event(
        author="memory_summarizer",
        content=Content(
            role="model",
            parts=[Part(text=f"[History Summary of previous imported interactions]:\n{content_text}")]
        )
    )

    session_service = _get_session_service(runner)
    if not session_service:
        logger.error("No session_service found on runner")
        return False, "No session_service found on runner"

    new_events = [import_event] + list(events)

    try:
        await session_service.delete_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        new_session = await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        for evt in new_events:
            await session_service.append_event(new_session, evt)
    except Exception as e:
        logger.error(f"Failed to persist imported session: {e}")
        return False, f"Failed to persist session: {e}"

    verify_session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    verify_events = getattr(verify_session, "events", []) if verify_session else []
    if bool(verify_events) and _is_summary_event(verify_events[0]):
        return True, "Import successful"
    return False, "Import verification failed"

def get_output_dir() -> Path:
    """
    获取当前工作目录下的 output 目录绝对路径。
    该方法仅基于当前 cwd 解析，以便在测试中通过临时目录隔离真实资产。
    """
    return (Path.cwd().resolve() / "output").resolve()

def _validate_safe_output_dir(out_dir: Path) -> None:
    out_dir = out_dir.resolve()
    cwd = Path.cwd().resolve()

    if cwd == Path("/").resolve():
        raise ValueError("安全限制：禁止在根目录作为工作目录时执行 output 清理。")

    if out_dir.name != "output":
        raise ValueError("安全限制：仅允许操作名为 'output' 的目录。")

    if out_dir.parent != cwd:
        raise ValueError("安全限制：仅允许操作当前工作目录下的 output 目录。")

    if out_dir == cwd:
        raise ValueError("安全限制：禁止将工作目录本身作为 output 目录。")

    if out_dir.exists() and out_dir.is_symlink():
        raise ValueError("安全限制：output 目录为符号链接，禁止操作。")

    if out_dir.exists() and not out_dir.is_dir():
        raise ValueError("安全限制：output 不是目录，禁止操作。")

def _format_size(num_bytes: int) -> str:
    n = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024

def scan_output_dir(out_dir: Path | None = None) -> dict:
    """
    扫描 output 目录并返回统计信息。
    """
    out_dir = (out_dir or get_output_dir()).resolve()
    _validate_safe_output_dir(out_dir)

    if not out_dir.exists():
        return {
            "exists": False,
            "path": str(out_dir),
            "items": [],
            "file_count": 0,
            "dir_count": 0,
            "total_bytes": 0,
        }

    items = []
    file_count = 0
    dir_count = 0
    total_bytes = 0

    for child in out_dir.iterdir():
        child_type = "other"
        try:
            if child.is_symlink():
                child_type = "symlink"
            elif child.is_file():
                child_type = "file"
            elif child.is_dir():
                child_type = "dir"
        except Exception:
            child_type = "other"

        items.append({"name": child.name, "path": str(child), "type": child_type})

    for p in out_dir.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                file_count += 1
                total_bytes += p.stat().st_size
            elif p.is_dir() and not p.is_symlink():
                dir_count += 1
        except Exception:
            continue

    return {
        "exists": True,
        "path": str(out_dir),
        "items": items,
        "file_count": file_count,
        "dir_count": dir_count,
        "total_bytes": total_bytes,
        "total_human": _format_size(total_bytes),
    }

def delete_output_dir_contents(out_dir: Path | None = None) -> dict:
    """
    删除 output 目录下所有内容，但保留 output 目录本身。
    """
    out_dir = (out_dir or get_output_dir()).resolve()
    _validate_safe_output_dir(out_dir)

    if not out_dir.exists():
        return {"ok": True, "path": str(out_dir), "deleted": 0, "message": "output 目录不存在，无需删除。"}

    deleted = 0
    errors = []

    for child in list(out_dir.iterdir()):
        try:
            if child.is_symlink() or child.is_file():
                child.unlink(missing_ok=True)
                deleted += 1
            elif child.is_dir():
                shutil.rmtree(child)
                deleted += 1
            else:
                child.unlink(missing_ok=True)
                deleted += 1
        except Exception as e:
            errors.append({"path": str(child), "error": str(e)})

    return {"ok": len(errors) == 0, "path": str(out_dir), "deleted": deleted, "errors": errors}

def format_events_to_markdown(events) -> str:
    """将 events 转换为 Markdown 字符串"""
    if not events:
        return "*暂无会话历史。*"
        
    lines = ["# 会话历史记录\n"]
    
    for event in events:
        if getattr(event, "partial", False):
            continue
            
        content = getattr(event, "content", None)
        if not content:
            continue
            
        role = getattr(content, "role", "unknown")
        parts = getattr(content, "parts", [])
        
        if role == "user":
            lines.append("## 🗣️ User")
            for part in parts:
                if getattr(part, "text", None):
                    lines.append(part.text)
            lines.append("\n---\n")
            
        elif role == "model":
            has_text = False
            for part in parts:
                if getattr(part, "text", None):
                    if not has_text:
                        lines.append("## 🤖 Agent")
                        has_text = True
                    if getattr(part, "thought", False):
                        lines.append(f"> 💭 *{part.text.replace(chr(10), ' ')}*")
                    else:
                        lines.append(part.text)
                elif getattr(part, "function_call", None):
                    call = part.function_call
                    lines.append(f"**🛠️ 工具调用**: `{call.name}`")
                    lines.append(f"```json\n{call.args}\n```")
            
            if has_text or any(getattr(p, "function_call", None) for p in parts):
                lines.append("\n---\n")
                
        elif role == "tool":
            lines.append("## ⚙️ Tool Response")
            for part in parts:
                if getattr(part, "function_response", None):
                    resp = part.function_response
                    lines.append(f"**✅ 工具返回**: `{resp.name}`")
                    resp_str = str(getattr(resp, "response", ""))
                    if len(resp_str) > 800:
                        resp_str = resp_str[:800] + "\n... (已截断)"
                    lines.append(f"```json\n{resp_str}\n```")
            lines.append("\n---\n")
            
    return "\n".join(lines)

async def handle_cli_command(command: str, runner, console: Console) -> bool:
    """
    处理以 / 开头的 CLI 命令。
    返回 True 表示命令已处理，外部应跳过该轮对话。
    返回 False 表示这不是支持的内部命令。
    """
    cmd_raw = command.strip()
    cmd = cmd_raw.lower()
    cmd_parts = cmd.split()
    
    if cmd == "/help":
        help_text = (
            "[bold cyan]可用指令列表：[/bold cyan]\n"
            "  [bold green]/help[/bold green]    - 显示此帮助信息\n"
            "  [bold green]/history[/bold green] - 查看当前会话历史\n"
            "  [bold green]/clear[/bold green]   - 清空当前会话历史\n"
            "  [bold green]/compact[/bold green] - 压缩当前会话历史（减少 Token 占用）\n"
            "  [bold green]/export[/bold green]  - 导出当前会话历史到 Markdown 文件\n"
            "  [bold green]/import[/bold green]  - 从文件导入历史记录，用法: /import <filepath>\n"
            "  [bold green]/delete[/bold green]  - 清理 output 目录下的所有生成内容\n"
            "  [bold green]exit / quit[/bold green] - 退出程序"
        )
        console.print(help_text)
        return True
        
    elif cmd == "/history":
        events = await get_current_session_events(runner)
        md_text = format_events_to_markdown(events)
        console.print(Markdown(md_text))
        return True
        
    elif cmd == "/clear":
        success = await clear_current_session(runner)
        if success:
            console.print("[bold green]✅ 对话历史已清理！模型已忘记之前的上下文。[/bold green]")
        else:
            console.print("[bold red]❌ 清理失败：未能找到有效的 session 管理器。[/bold red]")
        return True
        
    elif cmd == "/compact":
        tokens_before = await count_session_tokens(runner)
        with console.status("[bold cyan]🔄 正在呼叫 summarizer 进行全量历史压缩，这可能需要几秒钟时间，请稍候...[/bold cyan]", spinner="dots"):
            success = await custom_compact_session_memory(runner)
            
        if success:
            tokens_after = await count_session_tokens(runner)
            console.print(f"[bold green]✅ 会话历史已压缩！Tokens: {tokens_before} -> {tokens_after}[/bold green]")
        else:
            console.print("[bold red]❌ 压缩失败：当前内存管理器不支持此功能或历史为空。[/bold red]")
        return True
        
    elif cmd == "/export_tk" or cmd == "/export":
        events = await get_current_session_events(runner)
        if not events:
            console.print("[bold yellow]⚠️ 当前没有对话历史可以导出。[/bold yellow]")
            return True
            
        md_text = format_events_to_markdown(events)
        
        out_dir = get_output_dir()
        try:
            _validate_safe_output_dir(out_dir)
        except Exception as e:
            console.print(f"[bold red]❌ 写入失败：output 目录不安全：{e}[/bold red]")
            return True
        out_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"chat_history_{timestamp}.md"
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_text)
            
        # 使用 rich 支持的 link 语法
        file_uri = out_path.absolute().as_uri()
        console.print(f"[bold green]✅ 导出成功！文件已保存至：[/bold green] [link={file_uri}]{out_path.absolute()}[/link]")
        return True

    elif cmd == "/delete":
        try:
            info = scan_output_dir()
        except Exception as e:
            console.print(f"[bold red]❌ 无法扫描 output 目录：{e}[/bold red]")
            return True

        if not info.get("exists"):
            console.print("[bold yellow]⚠️ 当前工作目录下不存在 output 目录。[/bold yellow]")
            return True

        items = info.get("items", []) or []
        if not items:
            console.print("[bold green]✅ output 目录为空，无需清理。[/bold green]")
            return True

        total_bytes = int(info.get("total_bytes", 0) or 0)
        total_human = info.get("total_human") or _format_size(total_bytes)
        file_count = int(info.get("file_count", 0) or 0)
        console.print(f"[bold yellow]⚠️ 将清空 output 目录下的所有内容（不删除 output 目录本身）。[/bold yellow]")
        console.print(f"- 路径: {info.get('path')}")
        console.print(f"- 文件数: {file_count}")
        console.print(f"- 估算体积: {total_human} ({total_bytes} bytes)")
        preview = "\n".join([f"  - {it.get('type')}: {it.get('name')}" for it in items[:20]])
        if preview:
            console.print("以下为前 20 个顶层条目预览：")
            console.print(preview)
        if len(items) > 20:
            console.print(f"... 还有 {len(items) - 20} 个顶层条目未展示")

        console.print("[bold cyan]如确认删除，请输入：/delete confirm[/bold cyan]")
        return True

    elif cmd_parts[:2] == ["/delete", "confirm"] and len(cmd_parts) == 2:
        try:
            before = scan_output_dir()
        except Exception:
            before = None
        try:
            result = delete_output_dir_contents()
        except Exception as e:
            console.print(f"[bold red]❌ 删除失败：{e}[/bold red]")
            return True

        try:
            after = scan_output_dir()
        except Exception:
            after = None

        if result.get("ok"):
            msg = f"[bold green]✅ 已清空 output 目录内容，共删除 {result.get('deleted', 0)} 个顶层条目。[/bold green]"
            console.print(msg)
        else:
            console.print(f"[bold red]❌ 清理过程中出现错误，已尝试删除 {result.get('deleted', 0)} 个顶层条目。[/bold red]")
            errors = result.get("errors", []) or []
            for err in errors[:10]:
                console.print(f"- {err.get('path')}: {err.get('error')}")
            if len(errors) > 10:
                console.print(f"... 还有 {len(errors) - 10} 个错误未展示")

        if before and after:
            console.print(f"[dim]删除前: {before.get('file_count', 0)} files, {before.get('total_human', _format_size(int(before.get('total_bytes', 0) or 0)))}[/dim]")
            console.print(f"[dim]删除后: {after.get('file_count', 0)} files, {after.get('total_human', _format_size(int(after.get('total_bytes', 0) or 0)))}[/dim]")
        return True

    elif cmd_parts[0] == "/import":
        if len(cmd_parts) < 2:
            console.print("[bold red]❌ 缺少文件路径参数。用法: /import <filepath>[/bold red]")
            return True
            
        filepath = cmd_raw[len("/import"):].strip()
        with console.status(f"[bold cyan]🔄 正在导入历史记录从 {filepath}...[/bold cyan]", spinner="dots"):
            success, msg = await import_session_memory(runner, filepath)
            
        if success:
            console.print(f"[bold green]✅ 历史记录导入成功！[/bold green]")
        else:
            console.print(f"[bold red]❌ 导入失败：{msg}[/bold red]")
        return True

    elif cmd.startswith("/"):
        console.print(f"[bold yellow]⚠️ 未知命令 '{cmd_raw}'。当前支持的命令：/help, /history, /clear, /compact, /export, /delete, /import[/bold yellow]")
        return True
        
    return False
