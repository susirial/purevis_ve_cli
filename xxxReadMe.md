# xxxReadMe

## 目录索引

- [01. 一级风格家族 `art_style_family`](#row-01)
- [02. 二级风格子类 `art_style_subtype`](#row-02)
- [03. 媒介家族 `media_family`](#row-03)
- [04. 媒介子类 `media_subtype`](#row-04)
- [05. 推荐色板、镜头、材质、受众标签](#row-05)
- [06. 风格 × 媒介的设计文案矩阵](#row-06)

## 说明范围

本文仅针对 [style-configuration-management-system-design.md:L45-L52](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/.trae/documents/style-configuration-management-system-design.md#L45-L52) 中列出的六项内容做逐段拆解，重点说明它们在风格配置管理系统中的职责、设计意图以及与实现模块的关系。

## 逐段拆解表

| 序号 | 原文片段（或标题） | 功能说明 | 类型 | 默认值 | 必填 | 使用示例 | 备注 / 依赖项 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <a id="row-01"></a> 1 | 一级风格家族 `art_style_family` | 这是风格体系的顶层分类，用来决定项目属于哪种大类审美路线，例如国漫、日漫、3D CG、电影化风格化。设计思路是先用“粗粒度分类”完成路由，再在此基础上细分具体子类，避免系统只依赖自由文本风格描述。 | 配置字段 / 枚举型字符串 | 当前实现无硬编码默认值；未配置时为空 | 是，若要启用结构化风格配置则必须提供 | `Guoman`、`Japanese_Anime`、`3D_CG` | 由 [project_spec_registry.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/project_spec_registry.py#L9-L195) 从规范文档解析；在 [style_config_manager.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py#L261-L299) 中校验；会同步到 legacy `settings.visual.art_style_family` |
| <a id="row-02"></a> 2 | 二级风格子类 `art_style_subtype` | 这是一级家族下的具体执行风格，用来把抽象风格落到可操作的视觉预设，例如 `Xianxia`、`Romance_Webtoon`、`Epic_Fantasy_Cinema`。设计上它负责承接实际的推荐色板、镜头、材质和适配媒介，是 Prompt 注入的核心来源。 | 配置字段 / 枚举型字符串 | 当前实现无硬编码默认值；旧项目可从 legacy 配置回填 | 是，需与 `art_style_family` 成对出现 | `Xianxia`、`Romance_Webtoon`、`Hyper_Real_CG` | 通过 [style_config_manager.py:L156-L209](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py#L156-L209) 生成风格注入块；与 `family_code` 共同决定 `video/image/keyframe` 三类目标的最终风格 |
| <a id="row-03"></a> 3 | 媒介家族 `media_family` | 这是内容交付形态的顶层分类，用来区分短剧、电影、MV、广告片、企业宣传片等不同业务场景。设计思路是把“视觉风格”与“内容承载媒介”拆开，避免把短剧、电影等媒介逻辑错误地写进风格本身。 | 配置字段 / 枚举型字符串 | 当前实现无默认值；取自项目 `settings.delivery` | 建议必填 | `Short_Drama`、`Film`、`MV` | 主要来自 [project-configuration-spec.md:L255-L266](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/.trae/documents/project-configuration-spec.md#L255-L266)；在 [style_config_manager.py:L314-L320](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py#L314-L320) 中被读取，并参与风格注入上下文构建 |
| <a id="row-04"></a> 4 | 媒介子类 `media_subtype` | 这是媒介家族下的细分类，用来决定更具体的交付约束，例如 `Vertical_Short_Drama`、`Documentary_Film`、`Lyric_MV`。设计上它不仅影响内容形态，也作为风格合法性校验条件：某些风格子类只适合特定媒介子类。 | 配置字段 / 枚举型字符串 | 当前实现无默认值；由项目交付设置决定 | 建议必填 | `Vertical_Short_Drama`、`Animated_MV`、`Corporate_Profile_Film` | 在 [style_config_manager.py:L281-L292](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py#L281-L292) 中用于兼容性检查和自动回退；如果风格不匹配，会给出 warning 或切换同家族兼容子类 |
| <a id="row-05"></a> 5 | 推荐色板、镜头、材质、受众标签 | 这一项不是单个字段，而是一组附属元数据。它们的作用是把“风格名称”转译为模型可消费的执行参数，例如颜色倾向、镜头语言、材质处理方向和受众定位。设计思路是让风格从“命名标签”升级成“结构化风格预设”。 | 结构化预设元数据 / 数组字段 | 默认值为空数组 | 否，但强烈建议补全 | `recommended_palette: ["jade_white", "ice_blue", "rune_gold"]` | 来源于 [project-configuration-spec.md:L91-L250](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/.trae/documents/project-configuration-spec.md#L91-L250)；在 [style_config_manager.py:L189-L200](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py#L189-L200) 被拼成风格注入块；对子模块 `visual_director`、`image_gen`、`video_gen` 生效 |
| <a id="row-06"></a> 6 | 风格 × 媒介的设计文案矩阵 | 这是规范文档中的高层知识层，用来给每个典型“风格 × 媒介”组合提供设计解释、应用场景和创作方向。设计思路不是直接拿来做字段存储，而是为后续推荐系统、风格解释、Prompt 模板和用户界面文案提供语义依据。 | 说明性规范内容 / 文档矩阵 | 无默认值 | 否 | 如 `[仙侠风格]×[竖屏短剧]`、`[商业广告风格]×[广告片]` | 当前代码不会直接逐条解析整段矩阵，但它为 [style-configuration-management-system-design.md:L42-L53](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/.trae/documents/style-configuration-management-system-design.md#L42-L53) 中“规范源”概念提供语义支撑；后续如果做推荐 UI，可将其转化为预览文案 |

## 补充说明

- `art_style_family` 与 `art_style_subtype` 共同定义“风格是什么”。
- `media_family` 与 `media_subtype` 共同定义“内容将交付到哪里、以什么形态呈现”。
- 推荐色板、镜头、材质、受众标签负责把风格转成可执行参数。
- 风格 × 媒介矩阵负责把结构化配置补足为可解释的设计语言。

## 关联模块速查

- 规范来源： [project-configuration-spec.md](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/.trae/documents/project-configuration-spec.md)
- 注册表解析： [project_spec_registry.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/project_spec_registry.py)
- 风格配置管理： [style_config_manager.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/core/style_config_manager.py)
- Agent 工具接口： [style_tools.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/tools/style_tools.py)
- 总控注入点： [orchestrator.py](file:///Users/susirial/work_station/SOLO_MTC_SHOW/public_purevis_cli_project/agents/orchestrator.py)

## 预览与提交说明

- 本文档已按标准 Markdown 表格格式编写。
- 本地已通过文本级结构检查与 Markdown 转 HTML 方式验证表格语法可解析。
- 当前环境可以完成文件创建、版本跟踪准备和本地校验。
- 若需要真正发起远程合并请求并指派评审，还需要本地 Git 远程仓库权限与代码托管平台访问能力。
