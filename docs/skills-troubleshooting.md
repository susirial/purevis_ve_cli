# Skills 系统问题排查指南

## 常见问题

### 1. LLM 忘记加载 Skill

**现象**：智能体在执行任务时没有遵循预期的工作流规则。

**排查**：
- 检查 orchestrator instruction 中的技能触发条件映射表是否覆盖了该任务类型
- 检查用户输入是否命中了触发条件的关键词

**解决**：
- 在 instruction 中增加更明确的触发关键词
- 对高频 skill 考虑在 instruction 中直接内联关键规则摘要
- 未来可探索 before_agent callback 自动注入

### 2. Skill 加载返回错误

**现象**：`load_skill("xxx")` 返回 `error` 字段。

**排查**：
```bash
# 检查 skill 目录是否存在
ls skills/xxx/SKILL.md

# 检查 frontmatter 格式
head -5 skills/xxx/SKILL.md
```

**解决**：
- 确保目录名与 SKILL.md 中的 `name` 字段一致
- 确保 frontmatter 格式正确（`---` 开头和结尾）
- 运行 `python3 tests/test_skill_system.py` 验证

### 3. Reference 文件加载失败

**现象**：`load_skill_reference("xxx", "yyy.md")` 返回错误。

**排查**：检查文件是否存在于 `skills/xxx/references/yyy.md`。

**解决**：错误信息中包含 `available_references` 列表，根据实际文件名调整。

### 4. 子智能体无法加载 Skill

**现象**：子智能体报告 `load_skill` 工具不存在。

**排查**：检查对应智能体的 `tools=[]` 列表是否包含 `load_skill` 和 `load_skill_reference`。

**解决**：
```python
from tools.skill_loader import load_skill, load_skill_reference

Agent(tools=[..., load_skill, load_skill_reference])
```

### 5. Skill 更新后行为未变化

**现象**：修改了 SKILL.md 但智能体行为没有变化。

**说明**：技能加载器每次 `load_skill` 调用都会重新读取文件，支持热更新。但如果是在同一个对话会话中，LLM 可能已经在上下文中缓存了旧版本的 skill 内容。

**解决**：开始新的对话会话即可生效。

### 6. SKILL.md 遗漏工具名（LLM 不知道自己有哪些工具）

**现象**：LLM 在执行任务时只使用了部分工具，忽略了同一智能体注册的其他可用工具。

**根因**：SKILL.md 正文中只用自然语言描述了工作流方向（"转交 director""交给 image_gen"），但没有写出具体的工具函数名。LLM 不主动 `load_skill_reference` 时，就不知道还有这些工具可用。

**排查**：
```bash
# 运行工具覆盖审计脚本（对比 SKILL.md 内容 vs 智能体实际注册的 tools 列表）
python3 -c "
from pathlib import Path
skills_dir = Path('skills')
for skill_dir in sorted(skills_dir.iterdir()):
    skill_md = skill_dir / 'SKILL.md'
    if not skill_md.exists(): continue
    content = skill_md.read_text()
    print(f'{skill_dir.name}: {len(content)} chars')
    # 检查工具名是否出现在正文中
"
```

**预防**：
- 每个 SKILL.md 正文中必须包含一个"可用工具清单"表，显式列出该 Skill 涉及的所有工具函数名
- 工作流步骤中标注每步调用的具体工具名（如 `→ 调用 design_character`）
- 新增或修改 Skill 后，运行审计脚本确认工具覆盖率为 100%

**已修复历史**：v1.0.1 通过审计脚本发现并修复了 character-design、scene-prop-design、image-generation、video-generation 4 个 Skill 的工具遗漏。

### 7. 上下文窗口溢出

**现象**：LLM 输出截断或质量明显下降。

**排查**：
```bash
python3 tests/test_skill_system.py  # 查看 Benchmark 部分
```

**解决**：
- 检查是否同时加载了过多 skill（正常情况下每轮只应加载 1-2 个）
- 将过长的 SKILL.md 内容进一步拆分到 references/
- 保持每个 SKILL.md 正文 < 5000 tokens

## 验证命令

```bash
# 完整验证（含 benchmark）
python3 tests/test_skill_system.py

# 检查 skill 文件结构
find skills -type f | sort

# 检查智能体代码行数
wc -l agents/*.py tools/skill_loader.py
```

## 监控要点

| 指标 | 健康范围 | 告警条件 |
|------|---------|---------|
| 单个 SKILL.md 正文 | < 2500 字符 | > 5000 字符 |
| 单次会话加载的 skill 数 | 1-3 个 | > 5 个 |
| 单次会话加载的 reference 数 | 0-3 个 | > 6 个 |
| skill 总数 | 9 个（当前） | 新增后需更新测试 |
