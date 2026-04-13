# orchestrator 媒体 Provider 三层改造方案

## 1. 目标

基于以下三条设计原则，给出一套可落地的修改方案：

- 在 `prompt` 中放稳定决策规则
- 在 `catalog` 中放当前支持事实
- 在 `router` 中放最终选择逻辑

本方案的目标是让 `orchestrator` 在面对“切换媒体后端”“指定生图模型”“指定生视频模型”“选择更快/更强/更完整工作流”这类需求时，既能稳定判断，也不会把易变的 provider / model 事实硬编码进系统提示词。

## 2. 设计总览

建议改造为三层结构：

### 第一层：Prompt 层

承载内容：

- 稳定的决策原则
- 用户意图识别规则
- 禁止行为
- 配置引导规则

不承载内容：

- 完整 provider 列表
- 完整模型清单
- 当前可用性状态
- 详细路由分支

### 第二层：Catalog 层

承载内容：

- 当前注册了哪些 provider
- 当前 provider 是否可用
- 每个 provider 支持哪些 capability
- 每个 capability 支持哪些模型
- 是否支持显式模型切换
- 各 provider 的推荐场景与所需环境变量

### 第三层：Router 层

承载内容：

- 按 capability 选 provider
- 按模型选 provider
- 按配置与环境变量选 provider
- 输出结构化路由结果或结构化错误

## 3. 推荐修改范围

建议修改或新增以下模块：

- `agents/orchestrator.py`
- `tools/media_providers/catalog.py`
- `tools/media_providers/router.py`
- `tools/media_providers/registry.py`
- `tools/media_providers/base.py`

如需要给 `orchestrator` 暴露可读目录，还建议新增一个工具层入口，例如：

- `tools/media_provider_tools.py`

## 4. 第一层改造：Prompt

### 4.1 修改目标

在 `orchestrator` 的系统提示词中新增一个独立规则块：

- 媒体 Provider 感知规则
- 媒体路由意图识别规则
- 配置引导规则
- 禁止行为

### 4.2 推荐新增的提示词块

建议把下面这段加入 `agents/orchestrator.py` 的 `instruction` 中，放在“调度规则与要求”区域，作为一个独立小节。

```text
【媒体 Provider 感知与配置引导规则】
- 当前系统底层存在多个媒体 provider，不同 provider 的能力范围、模型透明度与配置方式不同。
- 当任务涉及媒体能力选择、模型选择、默认后端切换时，不要凭记忆硬编码判断，优先依据系统提供的 provider catalog、配置状态和路由结果进行决策。
- 当用户明确指定模型时，必须优先尊重模型约束，不得静默替换成其他模型；如果当前 provider 或当前配置不支持该模型，必须明确说明原因，并给出可执行的配置建议。
- 当用户没有指定模型，但表达了“更快 / 更强质量 / 更低成本 / 更稳定 / 更适合完整工作流”等目标时，应先识别为媒体路由意图，再结合 provider catalog 做推荐。
- 当用户需要高阶工作流能力（如角色设计、场景设计、分镜拆解、提示词生成、图像分析）时，优先考虑工作流能力更完整的 provider；当用户需要显式指定生图或生视频模型时，优先考虑支持显式模型选择的 provider。
- 当用户只是想切换默认媒体后端时，可引导其配置 `MEDIA_PROVIDER`；如果系统支持能力级配置，则优先引导 `MEDIA_IMAGE_PROVIDER` 与 `MEDIA_VIDEO_PROVIDER`。
- 不得把未接入、未配置或仅占位的 provider 说成“当前可直接使用”；只有在 catalog 显示可用，且所需环境变量满足时，才可以向用户承诺该能力当前可用。
- 当媒体能力选择存在不确定性时，先解释当前可选路线，再询问用户是要“切默认后端”还是“本次任务显式指定模型”。
```

### 4.3 Prompt 层不建议加入的内容

以下内容不建议直接写死在系统提示词：

- `lib_nano_2`
- `lib_nano_pro`
- `seedance_2_0`
- `seedance_2_0_fast`
- `kling_o3`
- provider 的完整能力矩阵

原因是这些内容变化频率高，后续极易与代码实现漂移。

## 5. 第二层改造：Catalog

### 5.1 修改目标

新增一个统一的 provider 目录模块，例如：

- `tools/media_providers/catalog.py`

用于给 `orchestrator` 和未来的工具层返回“当前系统真实支持的媒体能力地图”。

### 5.2 Catalog 推荐接口

建议至少提供这两个接口：

```python
def get_media_provider_catalog() -> dict:
    ...

def get_media_provider_manifest(name: str) -> dict:
    ...
```

### 5.3 Catalog 推荐数据结构

建议输出结构如下：

```python
{
    "providers": [
        {
            "name": "libtv",
            "display_name": "LibTV",
            "available": True,
            "availability": "ga",
            "requires_env": ["LIBTV_ACCESS_KEY"],
            "supports_explicit_model_selection": True,
            "capabilities": {
                "generate_image": {
                    "enabled": True,
                    "models": ["lib_nano_2", "lib_nano_pro"],
                    "default_model": "lib_nano_2",
                },
                "generate_video": {
                    "enabled": True,
                    "models": ["seedance_2_0", "seedance_2_0_fast", "kling_o3"],
                    "default_model": "seedance_2_0_fast",
                },
                "generate_multi_view": {
                    "enabled": True,
                    "fixed_model": "lib_nano_2",
                },
            },
            "recommended_for": ["explicit_model_control", "fast_image", "fast_video"],
            "notes": "适合显式指定模型的原子媒体生成。",
        }
    ]
}
```

### 5.4 Catalog 的实现来源

建议按以下顺序构建 catalog：

- 从 `registry` 获取已注册 provider
- provider 实例自身暴露：
  - `capabilities()`
  - `supported_models()`
- 再由 `catalog.py` 补充：
  - `display_name`
  - `availability`
  - `requires_env`
  - `supports_explicit_model_selection`
  - `recommended_for`

### 5.5 当前系统建议的事实表达

过渡期建议 catalog 明确返回这些事实：

- `libtv`
  - 支持显式模型切换
  - 生图模型：`lib_nano_2`、`lib_nano_pro`
  - 生视频模型：`seedance_2_0`、`seedance_2_0_fast`、`kling_o3`
- `purevis`
  - 高阶工作流能力完整
  - 当前不支持通过 `model` 参数显式切换底层模型
- `volcengine_ark`
  - 当前支持基础生图/生视频/参考图/多视图/表情/姿势
  - 当前不支持通过 `model` 参数显式切换底层模型
- `vidu` / `kling`
  - 当前标记为 `planned`
  - 不应作为默认推荐

## 6. 第三层改造：Router

### 6.1 修改目标

新增统一路由器模块，例如：

- `tools/media_providers/router.py`

把“最终该选哪个 provider、该不该报错、该怎么提示用户配置”从 prompt 中剥离出来。

### 6.2 Router 推荐接口

建议至少提供：

```python
def resolve_media_provider(
    capability: str,
    requested_model: str = "",
    intent_tags: list[str] | None = None,
) -> dict:
    ...
```

### 6.3 Router 返回结构

建议返回结构如下：

```python
{
    "provider": "libtv",
    "model": "kling_o3",
    "capability": "generate_video",
    "reason": "requested_model_supported",
    "requires_config": [],
}
```

失败时建议返回结构化错误：

```python
{
    "error": {
        "code": "MODEL_NOT_SUPPORTED",
        "capability": "generate_video",
        "requested_model": "kling_o3",
        "message": "当前默认 provider 不支持该模型，请切换到支持显式模型的 provider。"
    }
}
```

### 6.4 Router 决策优先级

建议优先级如下：

1. 用户显式指定模型
2. capability 级配置
3. 全局 `MEDIA_PROVIDER`
4. `auto` 下按 catalog 推荐顺序选择

### 6.5 Router 的核心规则

- 用户明确指定模型时，不允许静默换模型
- provider 不可用时，不得返回“假可用”结果
- 高阶工作流能力优先选工作流型 provider
- 原子生图/生视频且用户指定模型时，优先选模型透明 provider

## 7. 第四层补充：给 orchestrator 暴露只读工具

### 7.1 建议新增工具

建议新增一个只读工具供 `orchestrator` 调用，例如：

```python
def describe_media_capabilities() -> dict:
    return get_media_provider_catalog()
```

或者：

```python
def suggest_media_route(capability: str, requested_model: str = "", intent: str = "") -> dict:
    return resolve_media_provider(...)
```

### 7.2 为什么需要工具而不是只靠 prompt

因为 `orchestrator` 自身没有办法直接读取当前 provider 真实可用性。

如果没有工具：

- 它只能靠系统提示词和记忆
- 一旦环境变量缺失，它仍可能给出错误承诺

如果有工具：

- 它可以基于当前运行时事实说话
- 也更容易在回复里生成正确的配置引导

## 8. 对现有代码的具体修改建议

### 8.1 `agents/orchestrator.py`

建议做的事：

- 增加“媒体 Provider 感知与配置引导规则”提示词块
- 不在 prompt 中写死完整模型清单

### 8.2 `tools/media_providers/base.py`

建议做的事：

- 保留现有 `capabilities()`
- 保留现有 `supported_models()`
- 如有必要，未来再补：
  - `display_name()`
  - `required_env()`
  - `supports_explicit_model_selection()`

### 8.3 `tools/media_providers/catalog.py`

建议做的事：

- 聚合 provider manifest
- 判断 provider 当前是否已配置
- 输出统一 catalog

### 8.4 `tools/media_providers/router.py`

建议做的事：

- 实现 capability/model/config 三维路由
- 提供结构化成功结果
- 提供结构化错误结果

### 8.5 `tools/media_providers/registry.py`

建议做的事：

- 保留现有 `get_media_provider()`
- 后续内部可复用 catalog / router 逻辑
- 不建议让 registry 同时承担“注册 + 描述 + 路由”三种职责

## 9. 分阶段落地建议

### 阶段一：最小可用改造

先做：

- 修改 `orchestrator` prompt
- 新增 `catalog.py`
- 新增只读工具 `describe_media_capabilities()`

这样 `orchestrator` 就已经能：

- 知道需要读目录
- 基于真实能力解释给用户

### 阶段二：标准路由落地

再做：

- 新增 `router.py`
- 新增 `suggest_media_route()` 或直接暴露 `resolve_media_provider()`

这样 `orchestrator` 就能从“解释能力”升级到“做稳定推荐”。

### 阶段三：配置分层

最后再做：

- `MEDIA_IMAGE_PROVIDER`
- `MEDIA_VIDEO_PROVIDER`
- `MEDIA_IMAGE_DEFAULT_MODEL`
- `MEDIA_VIDEO_DEFAULT_MODEL`

这样用户体验会更完整。

## 10. 最终推荐方案

我建议按下面这个顺序实施：

1. 在 `prompt` 中加入稳定决策规则
2. 新增 `catalog.py` 暴露当前支持事实
3. 新增 `router.py` 承担最终选择逻辑
4. 给 `orchestrator` 暴露只读能力目录工具
5. 后续再补能力级配置

## 11. 一句话总结

这次改造不应该是“把 provider / model 信息写进 `orchestrator` prompt”这么简单，而应该是：

- 让 `prompt` 负责判断原则
- 让 `catalog` 负责当前事实
- 让 `router` 负责最终选择

这样改完后，`orchestrator` 才能真正稳定地引导用户通过不同配置使用不同 provider 和不同模型，而且不会随着模型迭代迅速失控。
