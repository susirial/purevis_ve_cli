# PureVis Studio Agent

[English](README.md) | [简体中文](README_zh.md)

PureVis Studio Agent is a multimodal, multi-agent CLI for AI-native short drama and video production. It turns natural-language requests into a structured workflow that covers concept development, character and scene design, script writing, storyboard planning, keyframe generation, video synthesis, visual review, and local asset persistence.

The project is built on `VeADK` and is designed as an orchestration layer rather than a single-model wrapper. Text planning, image generation, video generation, and quality analysis are split into replaceable capability layers, so you can combine providers such as `PureVis`, `Volcengine Ark`, `LibTV`, and `Z.ai` without changing the top-level creation workflow.

## Highlights

- Natural-language driven creative pipeline from concept to final media.
- Specialized agents for orchestration, writing, storyboard design, image generation, video generation, and visual QA.
- Progressive-disclosure skill system that loads domain knowledge on demand instead of inflating the first prompt.
- Local project state, style configuration management, and reusable asset storage under `output/projects/`.
- Streaming CLI experience with tool-call panels, session history export/import, and automatic context compaction.
- Media-provider routing that separates planning models from image and video backends.

## Model And Provider Ecosystem

<p align="center">
  <img src="demo/volcengine-color.png" height="56" alt="Volcengine" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="demo/libtv-logo.svg" height="38" alt="LibTV" />
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="https://z-cdn.chatglm.cn/z-ai/static/logo.svg" height="42" alt="Z.ai" />
</p>

- `Volcengine Ark`: recommended production default for text, image, and video generation.
- `LibTV`: optional media backend for image and video generation with explicit model routing.
- `PureVis`: optional higher-level media workflow provider.
- `Z.ai`: optional OpenAI-compatible text-model source for agent or tool-side reasoning.

## Visual Showcase

The examples below demonstrate that PureVis produces reusable production assets rather than isolated generations. Character sheets, multi-view references, and key art can flow directly into storyboards, keyframes, and video synthesis.

### Key Art Exploration

<p align="center">
  <img src="demo/sky_verse_cover_epic.jpg" width="32%" alt="Key Art - Epic Confrontation" />
  <img src="demo/sky_verse_cover_duet.jpg" width="32%" alt="Key Art - Duet" />
  <img src="demo/sky_verse_cover_ruins.jpg" width="32%" alt="Key Art - Ruins Narrative" />
</p>

### Character References

<p align="center">
  <img src="demo/armed_diva_xingyao_ref.jpg" width="48%" alt="Character Reference - Xingyao" />
  <img src="demo/armed_diva_shuangren_ref.jpg" width="48%" alt="Character Reference - Shuangren" />
</p>

### Multi-View Sheets

<p align="center">
  <img src="demo/armed_diva_xingyao_multiview.jpg" width="48%" alt="Multi-view Sheet - Xingyao" />
  <img src="demo/armed_diva_shuangren_multiview.jpg" width="48%" alt="Multi-view Sheet - Shuangren" />
</p>

### Basic Image And Video Generation

**Text-to-image**

![Text-to-image demo](demo/山上有大象.jpg)

**Image-to-image**

![Image-to-image demo](demo/大象上的美女.jpg)

**Image-to-video**

<table>
  <tr>
    <td width="220" valign="top">
      <a href="https://github.com/susirial/purevis_ve_cli/blob/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">
        <img src="demo/大象上的美女.jpg" width="220" alt="Image-to-video cover" />
      </a>
    </td>
    <td valign="top">
      <strong>Content:</strong> elephant on a mountain transitioning into a rider scene<br/>
      <strong>Format:</strong> GitHub-friendly preview card<br/>
      <strong>Links:</strong>
      <a href="https://github.com/susirial/purevis_ve_cli/raw/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">direct MP4</a>
      ·
      <a href="https://github.com/susirial/purevis_ve_cli/blob/main/demo/%E5%B1%B1%E4%B8%8A%E5%A4%A7%E8%B1%A1%E8%BF%87%E6%B8%A1%E5%88%B0%E5%A4%A7%E8%B1%A1%E8%83%8C%E7%BE%8E%E5%A5%B3.mp4">GitHub page</a>
    </td>
  </tr>
</table>

## Architecture Overview

`purevis_agent.py` is the entry point. The runtime can be understood as six layers:

1. **CLI interaction layer**: renders the welcome panel, status animation, streaming text, tool-call panels, and errors with `rich`.
2. **Session execution layer**: creates a unified `Runner` with `orchestrator_agent` and initializes the session state.
3. **Command parsing layer**: routes `/...` commands to local management handlers and forwards normal prompts to the orchestrator.
4. **Multi-agent orchestration layer**: delegates work to `director`, `visual_director`, `image_gen`, `video_gen`, and `vision_analyzer`.
5. **Skill layer**: loads skill metadata, instructions, and references on demand, reducing first-turn context size significantly.
6. **Tools and state layer**: handles project state, style configuration, file persistence, media generation, and task polling.

## Agent Team

| Agent | Responsibility |
| --- | --- |
| `orchestrator` | Interprets user intent, decides the current production stage, and delegates work. |
| `director` | Handles planning, script writing, character/scene/prop design, and prompt pre-processing. |
| `visual_director` | Expands scripts or references into cinematic keyframe sequences and structured storyboard JSON. |
| `image_gen` | Generates reference images, keyframes, multi-view sheets, expression sheets, and pose sheets. |
| `video_gen` | Converts keyframes or reference images into short video clips. |
| `vision_analyzer` | Reviews visual assets for aesthetics, consistency, and rework suggestions. |

## End-To-End Workflow

The default production flow is organized into six stages:

1. **Project planning**: define genre, worldbuilding, and project settings.
2. **Character and scene design**: create textual design specs and generate reference assets.
3. **Script writing**: create episodes such as `ep01`, then generate scripts.
4. **Storyboard design**: convert scripts or references into cinematic keyframes and structured JSON.
5. **Keyframe production**: batch-generate image assets and review them visually.
6. **Video synthesis**: generate final motion clips from approved assets.

Example prompts:

```text
Create a new short-drama project called Cyberpunk 2077 and help me outline the story.
```

```text
Design the female lead: a 20-year-old cyber hacker. Generate a reference image and save it to the subject library.
```

```text
Create episode ep01 and write the script based on the outline.
```

```text
Ask the visual director to design 10 storyboard keyframes based on the script and the heroine reference image.
```

```text
Let the image-generation agent render a keyframe grid from the storyboard prompts, then ask the analyst to review the lighting.
```

```text
Let the video-generation agent turn all approved keyframes from episode one into 5-second motion clips.
```

## Installation

### Requirements

- `Python 3.10+`
- Access to at least one supported text model and one supported media provider
- A virtual environment is strongly recommended

### Create A Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### Install Dependencies

```bash
pip install veadk-python google-genai python-dotenv rich tiktoken pillow requests
```

### Configure Environment Variables

Copy the template and fill in your own credentials:

```bash
cp .example_env .env
```

Minimum recommended setup:

```bash
MODEL_AGENT_PROVIDER=openai
MODEL_AGENT_NAME=doubao-seed-2-0-pro-260215
MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
MODEL_AGENT_API_KEY=<your_text_model_key>

MODEL_TOOL_VISION_ANALYZER_PROVIDER=openai
MODEL_TOOL_VISION_ANALYZER_NAME=doubao-seed-2-0-pro-260215
MODEL_TOOL_VISION_ANALYZER_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
MODEL_TOOL_VISION_ANALYZER_API_KEY=<your_vision_model_key>

VOLCENGINE_ARK_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
VOLCENGINE_ARK_API_KEY=<your_media_key>

LOGGING_LEVEL=ERROR
LITELLM_LOG=CRITICAL
MEDIA_PROVIDER=volcengine_ark
```

Best practices:

- Never commit real API keys.
- Keep `MODEL_AGENT_*` for orchestration and writing, and manage media credentials separately.
- Use `MEDIA_IMAGE_PROVIDER` and `MEDIA_VIDEO_PROVIDER` if you want different backends for image and video generation.
- Use `MODEL_<AGENT_NAME>_*` overrides only when a specific agent truly needs a different model.

### Run The CLI

```bash
python purevis_agent.py
```

The CLI loads `.env` before importing `veadk`, initializes the runner, and starts a streaming chat loop with local command support.

## Core Capabilities

| Capability | What it does | Typical output |
| --- | --- | --- |
| Multi-agent orchestration | Routes tasks across specialized agents based on the current production stage | Delegated tool calls, intermediate results, final replies |
| Project state management | Creates project directories, tracks episodes, subjects, settings, and progress | `state.json`, directory structure, status summaries |
| Structured style governance | Manages style families, subtypes, target scopes, and version history | Style snapshots and reusable visual constraints |
| Character / scene / prop design | Produces reusable textual specs and generation prompts | Design docs, prompts, reference briefs |
| Storyboard preprocessing | Converts scripts into structured visual segments | Timeline segments and storyboard-ready data |
| Exhaustive JSON storyboard design | Builds structured keyframe plans from scripts or reference images | Frame-by-frame JSON and storyboard summaries |
| Image generation | Supports text-to-image, image-to-image, keyframes, and reference sheets | Task IDs, image URLs, saved files |
| Multi-view consistency assets | Produces multi-view, expression, and pose sheets | Reusable consistency materials |
| Image-to-video | Generates motion clips from one or two still images | Task IDs, video URLs, saved videos |
| Visual QA | Reviews aesthetics, lighting, consistency, and rework opportunities | Analysis reports and pass/fail guidance |
| Session history management | Exports, imports, clears, and compacts long-running conversations | Markdown history and summary state |
| Provider routing | Switches media backends via configuration without changing user workflow | Unified tool behavior across providers |

## CLI Commands

The CLI supports two entry modes:

- Local management commands that start with `/`
- Natural-language production requests routed through the orchestrator

Common commands:

| Command | Description |
| --- | --- |
| `/help` | Show local CLI help |
| `/history` | Print current session history as Markdown |
| `/clear` | Reset the current session |
| `/compact` | Compress long chat history |
| `/export` | Export the current session into `output/chat_history_<timestamp>.md` |
| `/import <filepath>` | Import a saved history summary |
| `/delete` | Preview removable contents under `output/` |
| `/delete confirm` | Delete top-level contents under `output/` after confirmation |
| `/style families` | List available style families |
| `/style subtypes <family>` | List subtypes for a family |
| `/style show <family> <subtype>` | Show a style preset |
| `/style current <project>` | Show current style config for a project |
| `/style versions <project>` | Show style change history |
| `/style apply <project> <target> <family> <subtype>` | Apply a style to `image`, `video`, or `keyframe` |
| `/style delete <project> [target]` | Remove style configuration |
| `exit` / `quit` | Exit safely |

## Repository Layout

```text
agents/                  # Agent definitions
core/                    # Model config, state, and style managers
docs/                    # Skill architecture and troubleshooting docs
skills/                  # Progressive-disclosure skills and references
tools/                   # CLI, state, media, file, and routing tools
demo/                    # Example images and videos used in the README
output/                  # Generated at runtime for projects, assets, and history
purevis_agent.py         # CLI entry point
.example_env             # Environment template
```

Typical project output:

```text
output/projects/<project_name>/
├── state.json
├── subjects/
│   ├── <subject_name>/
│   └── <scene_name>/
└── episodes/<episode_id>/
    ├── scripts/
    ├── storyboard/
    ├── keyframes/
    └── videos/
```

## Media Routing

Provider selection follows this logic:

1. Use `MEDIA_IMAGE_PROVIDER` or `MEDIA_VIDEO_PROVIDER` if explicitly set.
2. Otherwise fall back to `MEDIA_PROVIDER`.
3. If `MEDIA_PROVIDER=auto`, prefer `PUREVIS_API_KEY`, then `LIBTV_ACCESS_KEY`, then `VOLCENGINE_ARK_API_KEY`.
4. If a call explicitly passes a `model`, that model takes priority over defaults.
5. If a default model is incompatible with the chosen provider, the system raises a configuration error instead of silently switching.

Useful LibTV models:

- Image: `lib_nano_2`, `lib_nano_pro`
- Video: `seedance_2_0`, `seedance_2_0_fast`, `kling_o3`

## Session Safety And Recovery

- The CLI creates or recovers the session on startup and falls back to a lightweight `hello` run if the lower-level API behaves differently.
- Session history is compacted automatically when token usage exceeds `250000`.
- Tool output is truncated in the terminal to reduce noise while preserving key information.
- `/delete` is intentionally two-step and only operates on a safe `output/` directory inside the workspace.
- Import and export commands validate file access before mutating session state.

## Case Study

The assets under `demo/完整演示/` show a complete example that starts from a natural-language request for a 15-second promotional video and ends with:

1. script planning,
2. multiple directorial style options,
3. character design,
4. reference-image generation,
5. video-prompt generation, and
6. final video synthesis.

This is the core value of PureVis: it productizes the creative workflow, not just a single image or video API call.

## Related Docs

- `docs/skills-architecture.md`: progressive-disclosure skill design
- `docs/skills-changelog.md`: skill-system change log
- `docs/skills-troubleshooting.md`: troubleshooting guide
- `VEADK_DEV_GUIDE.md`: VeADK integration notes

## FAQ

### Why can a plain-language prompt trigger so many tools?

Because requests go through the `orchestrator`, which interprets the production stage and delegates tasks to specialized agents and tools.

### Why does `/delete` not remove files immediately?

This is a safety feature. The CLI previews what can be deleted first, and only deletes after `/delete confirm`.

### Why does the system sometimes compact history automatically?

Long creative sessions are expensive. Once the estimated session context exceeds `250000` tokens, the system summarizes older history to keep the workflow stable.

### Can media generation still work without `PUREVIS_API_KEY`?

Yes. The router can fall back to `LibTV` or `Volcengine Ark` based on the available credentials and configuration.

### What are the current limitations?

- The entry program uses a fixed `user_id` and `session_id`, which is best suited for local single-user workflows.
- `video_gen` currently supports up to two input images.
- Episode IDs are expected to use formats such as `ep01`, `ep02`, and so on.
- Structured storyboard and prompt-generation tools need meaningful input and may reject empty or under-specified requests.
