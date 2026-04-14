# Skills 系统变更日志

## v1.0.0 — 2026-04-14 · 渐进式披露技能系统初始版本

### 新增

#### 技能加载器
- `tools/skill_loader.py`：三层渐进式披露技能加载系统
  - `list_available_skills()` — L1 元数据层，列出所有 skill 的 name + description
  - `load_skill(skill_name)` — L2 指令层，加载 SKILL.md 正文
  - `load_skill_reference(skill_name, ref_file)` — L3 资源层，加载参考文档

#### 9 个 Skill（含 12 个参考文档）
- `skills/project-management/` — 项目生命周期管理（六阶段工作流）
- `skills/style-configuration/` — 结构化风格配置管理
- `skills/character-design/` — 角色设计工作流
- `skills/scene-prop-design/` — 场景/道具设计工作流
- `skills/storyboard-direction/` — 分镜/视觉导演工作流（含构图技法、用光术语、JSON 规范）
- `skills/image-generation/` — 图片生成工作流
- `skills/video-generation/` — 视频生成工作流（含预检规则、音频指南）
- `skills/vision-analysis/` — 视觉审美分析
- `skills/media-routing/` — 媒体 Provider 路由决策

#### 验证
- `tests/test_skill_system.py` — 端到端验证测试 + 上下文 benchmark

### 变更

#### orchestrator.py
- instruction 从 ~97 行缩减至 ~35 行
- 新增 `list_available_skills`, `load_skill`, `load_skill_reference` 三个工具
- 领域知识（风格治理、媒体路由、视频预检等）移出 instruction → 对应 skill
- 新增技能触发条件映射表
- 保留核心职责边界规则（不可用工具列表）

#### director.py
- instruction 从 ~30 行缩减至 ~20 行（保留核心规则摘要）
- 新增 `load_skill`, `load_skill_reference` 工具
- 角色/场景设计详细规则移至 `character-design` / `scene-prop-design` skill

#### visual_director.py
- instruction 从 ~145 行缩减至 ~18 行
- 构图技法、用光术语、Exhausted JSON 规范移至 `storyboard-direction` skill 的 references/
- 工具白名单规则保留在 instruction 中
- 新增 `load_skill`, `load_skill_reference` 工具

#### image_gen.py
- instruction 从 ~14 条详细规则缩减至 ~5 条核心概要
- 完整工作流规则（闭环流程、版式规则等）移至 `image-generation` skill
- 新增 `load_skill`, `load_skill_reference` 工具

#### video_gen.py
- instruction 从 ~12 条详细规则缩减至 ~6 条核心概要 + 硬规则
- 预检流程、确认卡流程、音频模式详情移至 `video-generation` skill
- 新增 `load_skill`, `load_skill_reference` 工具

#### vision_analyzer.py
- instruction 从 ~7 条规则缩减至 ~5 条核心概要
- 审核标准详情移至 `vision-analysis` skill
- 新增 `load_skill`, `load_skill_reference` 工具

### 效果
- 首轮上下文从 ~17500 tokens 降至 ~4400 tokens（-75%）
- 消除了角色变体规则在 3 个智能体中的重复注入
- 领域知识文件化，支持独立版本管理和热更新
