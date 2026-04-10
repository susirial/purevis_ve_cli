import os
from dotenv import load_dotenv

# 1. 必须在导入 veadk 之前加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import asyncio
from veadk import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai.types import Content, Part
from agents.orchestrator import orchestrator_agent

# --- 引入 Rich 组件 ---
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from tools.chat_history import handle_cli_command, count_session_tokens, custom_compact_session_memory

# 初始化全局 Console
console = Console()

async def main():
    # 2. 使用编排好的总控智能体
    runner = Runner(agent=orchestrator_agent, app_name="purevis_app", user_id="user_01")
    
    welcome_msg = (
        "[bold white]Welcome to PureVis Studio Agent[/bold white] 🎬\n\n"
        "我是一个强大的 AI 短剧创作总控智能体，通过多智能体协作（视觉导演、多模态编导等）\n"
        "为你提供从[cyan]剧本拆解[/cyan]、[cyan]角色/场景设计[/cyan]到[cyan]多模态生成（图片/视频）[/cyan]的全链路创作服务。\n\n"
        "✨ [dim]输入 [bold red]'/help'[/bold red] 查看可用指令，或直接说出你的创作想法。[/dim]\n"
        "✨ [dim]输入 [bold red]'exit'[/bold red] 或 [bold red]'quit'[/bold red] 退出对话。[/dim]"
    )
    console.print(Panel.fit(
        welcome_msg, 
        title="[bold blue]PureVis Studio[/bold blue]", 
        border_style="blue",
        padding=(1, 2)
    ))
    
    # 为了支持 streaming 模式的 run_async，我们需要显式确保 session 已创建
    # 兼容各种可能存在的 session_service 和 session_manager API
    if hasattr(runner, 'session_manager') and hasattr(runner.session_manager, 'create_session'):
        try:
            await runner.session_manager.create_session("session_01", "user_01", "purevis_app")
        except TypeError:
            pass
    
    # 作为保底，调用一次 run 让引擎自动去初始化内部 session 状态，加上状态提示
    with console.status("[bold cyan]初始化引擎与会话状态中...[/bold cyan]"):
        await runner.run("hello", session_id="session_01", user_id="user_01")
    
    # 3. 开启循环对话
    while True:
        try:
            # 使用 console.input 渲染带有样式的提示符
            user_input = console.input("\n[bold blue]User:[/bold blue] ")
        except (EOFError, KeyboardInterrupt):
            break
            
        if user_input.lower() in ['exit', 'quit']:
            console.print("\n[bold green]Agent: 再见！[/bold green]")
            break
        if not user_input.strip():
            continue
        
        # 拦截以 / 开头的本地管理命令
        if user_input.strip().startswith("/"):
            await handle_cli_command(user_input, runner, console)
            continue

        try:
            # 在调用前检查 token 数量，若超过 250,000 (250k) 则自动压缩
            max_tokens_limit = 250000
            current_tokens = await count_session_tokens(runner)
            if current_tokens > max_tokens_limit:
                console.print(f"[bold yellow]⚠️ 当前会话 token 数量 ({current_tokens}) 超过 {max_tokens_limit}，触发自动压缩...[/bold yellow]")
                success = await custom_compact_session_memory(runner)
                if success:
                    new_tokens = await count_session_tokens(runner)
                    console.print(f"[bold green]✅ 自动压缩完成！Tokens: {current_tokens} -> {new_tokens}[/bold green]")
                else:
                    console.print("[bold red]❌ 自动压缩失败。[/bold red]")

            user_message = Content(
                role="user",
                parts=[Part(text=user_input)]
            )
            
            # 创建并启动 Status，不使用 with 语句以便在流式输出中动态控制启停
            status = console.status("[bold cyan]Agent 思考中...[/bold cyan]")
            status.start()
            
            # 用于记录流式输出是否留下了未换行的文本
            needs_newline = False 
            current_agent_author = None
            
            # Agent 内部在需要时会自动调用工具并总结返回，使用 run_async 实现流式输出
            # 开启 StreamingMode.SSE 才能获得实时的分块事件 (partial events)
            async for event in runner.run_async(
                user_id="user_01",
                session_id="session_01",
                new_message=user_message,
                run_config=RunConfig(max_llm_calls=30, streaming_mode=StreamingMode.SSE)
            ):
                # 检查并发言人切换
                author = getattr(event, "author", None)
                if author and author != current_agent_author:
                    if needs_newline:
                        console.print()
                        needs_newline = False
                    status.stop()
                    console.print(f"\n[bold cyan]💬 {author} 正在发言...[/bold cyan]")
                    current_agent_author = author
                    status.start()
                    
                # 1. 处理工具调用 (Input) 必须是非 partial，否则参数是不完整的片段
                if not event.partial and (calls := event.get_function_calls()):
                    if needs_newline:
                        console.print()  # 打印 Panel 前，确保之前的文本正常换行
                        needs_newline = False
                    
                    status.stop()  # 暂停动画
                    for call in calls:
                        # 检测是否为智能体转交 (Agent Transfer)
                        if "transfer" in call.name.lower():
                            agent_name = call.name.replace("transfer_to_", "")
                            panel = Panel(
                                Text(str(call.args)), 
                                title=f"[bold magenta]🔄 智能体转交: 呼叫 {agent_name} 团队[/bold magenta]", 
                                border_style="magenta"
                            )
                        else:
                            # 使用 Text() 包装 args 防止 JSON 中的中括号引发 MarkupError
                            panel = Panel(
                                Text(str(call.args)), 
                                title=f"[bold blue]🛠️ 工具调用: {call.name}[/bold blue]", 
                                border_style="blue"
                            )
                        console.print(panel)
                    
                    # 更新提示文案并恢复动画
                    status.update("[bold yellow]等待工具执行结果...[/bold yellow]")
                    status.start()
                        
                # 2. 处理工具返回 (Output) 同样必须是非 partial
                elif not event.partial and (responses := event.get_function_responses()):
                    if needs_newline:
                        console.print()
                        needs_newline = False
                    
                    status.stop()
                    for resp in responses:
                        raw_output = str(resp.response)
                        display_output = raw_output[:250] + "\n... (已截断)" if len(raw_output) > 250 else raw_output
                        
                        if "transfer" in resp.name.lower():
                            agent_name = resp.name.replace("transfer_to_", "")
                            panel = Panel(
                                Text(display_output), 
                                title=f"[bold magenta]✅ 转交返回: {agent_name} 团队处理完毕[/bold magenta]", 
                                border_style="magenta"
                            )
                        else:
                            panel = Panel(
                                Text(display_output), 
                                title=f"[bold green]✅ 工具返回: {resp.name}[/bold green]", 
                                border_style="green"
                            )
                        console.print(panel)
                        
                    status.update("[bold cyan]获取结果完毕，继续思考中...[/bold cyan]")
                    status.start()
                        
                # 3. 处理流式文本输出 (包含思考过程或最终回复)
                # 只有当 event 是 partial (片段) 时，我们才进行打字机输出，避免非 partial 的最终聚合文本导致重复输出
                elif event.partial and event.content and event.content.parts:
                    # 使用 _spinner 属性检查状态，如果不具有该属性或在某些 rich 版本中，
                    # 我们可以通过维护一个自定义布尔值来跟踪动画是否正在运行
                    status.stop()  # 开始流式输出文本，关闭动画
                        
                    for part in event.content.parts:
                        # 过滤掉 function_call 的中间构建片段
                        if getattr(part, "function_call", None):
                            continue
                            
                        if getattr(part, "thought", False) and part.text:
                            # 思考过程：使用 dim 样式，并且关闭 markup 解析
                            console.print(part.text, end="", style="dim", markup=False)
                            needs_newline = True
                        elif part.text:
                            # 正常文本：关闭 markup 解析，防止输出中的 [] 被吞掉
                            console.print(part.text, end="", markup=False)
                            needs_newline = True
                            
            # 单次对话结束清理
            status.stop()
            if needs_newline:
                console.print()  # 确保 Agent 回复完毕后完美换行
                
            # 在每轮对话结束后，打印当前上下文的总 Token 消耗比例和阈值
            try:
                final_tokens = await count_session_tokens(runner)
                max_tokens = 250000
                percent = (final_tokens / max_tokens) * 100
                console.print(f"\n[dim italic]📊 上下文 Token 使用率: {final_tokens} / {max_tokens} ({percent:.1f}%)[/dim italic]")
            except Exception:
                pass
                
        except Exception as e:
            if 'status' in locals():
                status.stop()
            console.print(f"\n[bold red][Error]: 调用发生错误: {e}[/bold red]\n")

if __name__ == "__main__":
    asyncio.run(main())
