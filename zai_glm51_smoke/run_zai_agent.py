import asyncio
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from veadk import Agent, Runner
except Exception:
    Agent = None
    Runner = None


BASE_DIR = Path(__file__).resolve().parents[1]


def _safe_rel_path(relative_path: str) -> Path:
    if not relative_path:
        raise ValueError("path 不能为空")
    p = Path(relative_path)
    if p.is_absolute():
        raise ValueError("path 必须为相对路径")
    resolved = (BASE_DIR / p).resolve()
    try:
        resolved.relative_to(BASE_DIR)
    except ValueError as exc:
        raise ValueError("path 不允许越界到项目目录之外") from exc
    return resolved


def create_smoke_assets(dir_path: str = "output/zai_smoke", script_name: str = "smoke_generated.py") -> dict:
    target_dir = _safe_rel_path(dir_path)
    target_dir.mkdir(parents=True, exist_ok=True)

    script_path = (target_dir / script_name).resolve()
    try:
        script_path.relative_to(BASE_DIR)
    except ValueError as exc:
        raise ValueError("script_name 不允许越界到项目目录之外") from exc

    script_content = "\n".join(
        [
            "import os",
            "from pathlib import Path",
            "",
            "try:",
            "    from dotenv import load_dotenv",
            "except Exception:",
            "    load_dotenv = None",
            "",
            "if load_dotenv:",
            "    load_dotenv(Path(__file__).resolve().parents[2] / '.env')",
            "",
            "print('provider=', os.environ.get('MODEL_AGENT_PROVIDER'))",
            "print('model=', os.environ.get('MODEL_AGENT_NAME'))",
            "print('api_base=', os.environ.get('MODEL_AGENT_API_BASE'))",
            "print('ok')",
            "",
        ]
    )

    script_path.write_text(script_content, encoding="utf-8")

    return {
        "dir": str(target_dir.relative_to(BASE_DIR)),
        "script": str(script_path.relative_to(BASE_DIR)),
    }


def _configure_zai_env() -> None:
    zai_api_key = os.environ.get("ZAI_API_KEY")
    if not zai_api_key:
        raise RuntimeError("请先设置环境变量 ZAI_API_KEY")

    zai_model = os.environ.get("ZAI_MODEL") or "glm-5.1"
    zai_base_url = os.environ.get("ZAI_BASE_URL") or "https://api.z.ai/api/paas/v4/"

    os.environ["MODEL_AGENT_PROVIDER"] = os.environ.get("MODEL_AGENT_PROVIDER") or "openai"
    os.environ["MODEL_AGENT_NAME"] = zai_model
    os.environ["MODEL_AGENT_API_BASE"] = zai_base_url
    os.environ["MODEL_AGENT_API_KEY"] = zai_api_key


async def _run() -> int:
    if load_dotenv:
        load_dotenv(BASE_DIR / ".env")

    try:
        _configure_zai_env()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if Agent is None or Runner is None:
        print("veadk 未安装。请先安装: python3 -m pip install veadk-python", file=sys.stderr)
        return 2

    agent = Agent(
        name="zai_smoke_agent",
        description="Smoke test agent for Z.AI GLM-5.1 via OpenAI-compatible API.",
        instruction="Call create_smoke_assets exactly once, then reply with the returned JSON.",
        tools=[create_smoke_assets],
        **{
            "model_provider": os.environ.get("MODEL_AGENT_PROVIDER", ""),
            "model_name": os.environ.get("MODEL_AGENT_NAME", ""),
            "model_api_base": os.environ.get("MODEL_AGENT_API_BASE", ""),
            "model_api_key": os.environ.get("MODEL_AGENT_API_KEY", ""),
        },
    )

    runner = Runner(agent=agent, app_name="zai_smoke_app", user_id="zai_user")
    await runner.run(
        "Create a directory and a python script for smoke testing by calling create_smoke_assets. Return the JSON.",
        session_id="zai_smoke_session",
        user_id="zai_user",
    )

    script_path = _safe_rel_path("output/zai_smoke/smoke_generated.py")
    if not script_path.exists():
        print("未检测到 smoke_generated.py，说明模型可能未触发函数调用。", file=sys.stderr)
        return 3

    proc = subprocess.run([sys.executable, str(script_path)], cwd=str(BASE_DIR), check=False, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
