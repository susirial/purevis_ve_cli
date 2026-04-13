# orchestrator 媒体 Provider 提示词设计说明

## 1. 结论

是的，`orchestrator` 的系统提示词里需要加入“媒体 provider 能力认知”。

但按照业界最佳实践，不应该把完整的 provider 能力矩阵、所有模型名、所有路由细节都硬编码进系统提示词。

正确做法是三层结合：

- 系统提示词只放稳定的决策原则
- 动态能力目录负责提供当前系统真实支持的 provider / capability / model
- 运行时路由器负责最终选择 provider，并返回结构化错误

一句话说：

- `prompt` 负责“怎么判断”
- `catalog` 负责“现在支持什么”
- `router` 负责“最后选谁”

## 2. 为什么不能把完整矩阵全塞进系统提示词

如果把以下内容全部硬编码进 `orchestrator` 系统提示词：

- 当前有哪些 provider
- 每个 provider 支持哪些能力
- 每个能力支持哪些模型
- 哪些模型更快、哪些更强
- 哪些 provider 需要哪些环境变量

短期看似方便，长期会有几个明显问题：

- 每次新增模型都要改系统提示词
- 文档与代码容易漂移
- prompt 长度持续膨胀
- `orchestrator` 会把过期知识当真
- 灰度能力、禁用能力、占位 provider 很难准确表达

这类信息属于“变化快的运行时目录”，不应该由系统提示词长期硬编码承担。

## 3. 系统提示词里应该放什么

建议系统提示词只放以下四类稳定规则。

### 3.1 Provider 感知规则

让 `orchestrator` 知道：

- 当前系统底层存在多个媒体 provider
- 不同 provider 的能力边界不同
- 有的 provider 偏高阶工作流
- 有的 provider 偏原子生图/生视频能力
- 有的 provider 支持显式模型选择，有的不支持

这里强调“有差异”这个事实，不强调完整列表。

### 3.2 决策优先级规则

让 `orchestrator` 知道如何判断：

- 用户显式指定模型时，优先按模型路由
- 用户只表达目标时，按能力和推荐策略路由
- 用户要求高阶工作流时，优先考虑工作流型 provider
- 用户要求显式模型控制时，优先考虑模型透明 provider

### 3.3 配置引导规则

让 `orchestrator` 知道应该如何引导用户：

- 如果用户要切换默认后端，可以引导配置 `MEDIA_PROVIDER`
- 如果用户未来要分开配置图片与视频后端，优先引导能力级配置
- 如果用户当前 provider 不支持显式模型切换，要明确解释限制

### 3.4 禁止行为规则

这是最重要的一层：

- 不要臆测某个 provider 一定支持某个模型
- 不要在用户明确指定模型时静默替换为别的模型
- 不要把“planned” 或未配置的 provider 当成当前可用能力承诺给用户
- 不要绕过能力目录和路由器直接拍脑袋做推荐

## 4. 系统提示词里不应该放什么

以下内容不建议长期硬编码进 `orchestrator` 系统提示词：

- 所有 provider 的完整模型清单
- 所有 provider 的完整能力矩阵
- 每个 provider 所需环境变量的完整表
- 所有模型的默认时长、默认画幅、价格、质量说明
- 详细回退顺序的所有分支

这些信息建议从动态目录读取。

## 5. 最佳实践的三层架构

### 5.1 第一层：系统提示词

只定义稳定策略：

- 什么时候需要询问用户是否指定模型
- 什么时候应该读 provider catalog
- 什么时候应该提示用户改配置
- 什么时候应该明确报“不支持”

### 5.2 第二层：Provider Catalog

建议由代码提供一个统一目录，例如：

```python
get_media_provider_catalog()
```

返回：

- 当前有哪些 provider
- 每个 provider 当前是否可用
- 支持哪些 capability
- 每个 capability 支持哪些 models
- 是否支持显式模型选择
- 推荐场景

### 5.3 第三层：Capability Router

建议由代码统一做选择，例如：

```python
resolve_media_provider(
    capability="generate_video",
    requested_model="kling_o3",
    user_intent_tags=["explicit_model"]
)
```

返回：

- 选中的 provider
- 选中的模型
- 选择原因
- 不可用时的结构化错误

## 6. 对当前系统最合适的提示词设计

基于你们现有架构，我建议 `orchestrator` 的系统提示词新增一个独立段落：

## 媒体 Provider 感知与配置引导规则

建议内容如下。

```text
【媒体 Provider 感知与配置引导规则】
- 当前系统底层存在多个媒体 provider，不同 provider 的能力范围、模型透明度与配置方式不同。
- 你不应假设某个 provider 一定支持某个模型；当任务涉及媒体能力选择、模型选择、默认后端切换时，优先依据系统提供的 provider catalog、配置状态和路由结果进行判断。
- 当用户明确指定模型时，必须优先尊重模型约束，不得静默替换成其他模型；如果当前 provider 或当前配置不支持该模型，必须明确说明原因，并给出可执行的配置建议。
- 当用户没有指定模型，但表达了“更快 / 更强质量 / 更低成本 / 更稳定 / 更适合完整工作流”等目标时，你应先将其识别为媒体路由意图，再结合 provider catalog 给出推荐。
- 当用户需要高阶工作流能力（如角色设计、场景设计、分镜拆解、提示词生成、图像分析）时，优先考虑工作流能力更完整的 provider；当用户需要显式指定生图或生视频模型时，优先考虑支持显式模型选择的 provider。
- 当用户只是想切换默认媒体后端时，可引导其配置 `MEDIA_PROVIDER`；如果系统后续支持能力级配置，则优先引导 `MEDIA_IMAGE_PROVIDER` 与 `MEDIA_VIDEO_PROVIDER` 这类更细粒度配置。
- 你不得把未接入、未配置或仅占位的 provider 说成“当前可直接使用”；只有在 provider catalog 显示可用，且所需环境变量已满足时，才可以向用户承诺该能力现在可用。
- 当媒体能力选择存在不确定性时，先解释当前可选路线，再询问用户是要“默认后端切换”还是“本次任务显式指定模型”。
```

这段 prompt 的特点是：

- 不硬编码完整矩阵
- 但明确规定了 `orchestrator` 的判断方式
- 适合作为长期稳定规则

## 7. 什么内容适合做“运行时注入”

建议把下面这类信息，以“动态上下文”或“工具返回结果”的形式提供给 `orchestrator`：

- 当前 provider 列表
- 当前可用 provider 列表
- 当前哪些 provider 已配置
- 每个 provider 当前支持哪些生图模型
- 每个 provider 当前支持哪些生视频模型
- 每个 provider 当前支持哪些高阶能力
- 推荐默认模型

例如：

```json
{
  "providers": [
    {
      "name": "libtv",
      "available": true,
      "supports_explicit_model_selection": true,
      "image_models": ["lib_nano_2", "lib_nano_pro"],
      "video_models": ["seedance_2_0", "seedance_2_0_fast", "kling_o3"],
      "capabilities": {
        "generate_image": true,
        "generate_video": true,
        "generate_multi_view": true,
        "generate_storyboard_grid_sheet": true,
        "design_character": false
      }
    }
  ]
}
```

这种信息是运行时真实状态，最适合注入，不适合写死在 prompt。

## 8. 给当前系统的推荐知识分层

我建议 `orchestrator` 对媒体能力的认知分三层。

### 第一层：系统提示词中的稳定认知

- 有多个 provider
- provider 能力不同
- 有的支持显式模型，有的不支持
- 选择时要尊重用户显式模型要求
- 不能承诺未配置或未接入能力

### 第二层：Catalog 中的当前事实

- 当前支持 `purevis`、`libtv`、`volcengine_ark`、`vidu`、`kling`
- `libtv` 当前显式支持哪些 image/video models
- `purevis` 当前适合哪些高阶工作流
- `vidu` / `kling` 当前是不是仅占位

### 第三层：Router 的最终决策

- 当前任务应该走哪个 provider
- 默认模型应该是什么
- 如果失败，应该提示用户改哪个配置

## 9. 对当前项目的具体建议

结合你们当前实现，建议：

- 在 `orchestrator` 系统提示词中加入“媒体 Provider 感知与配置引导规则”
- 但不要把所有 provider 的全部模型清单硬编码进去
- 同时新增一个给 `orchestrator` 使用的 catalog 接口
- 后续再新增 router 接口

也就是说：

- **要加**
- 但要加的是“规则层”
- 不是“全量事实表”

## 10. 如果一定要在 prompt 里加入部分事实，应该加哪些

如果你希望 `orchestrator` 在没有 catalog 的过渡阶段也能做基本判断，那么可以只加极少量、最稳定的事实：

- 系统当前存在多个媒体 provider
- `libtv` 适合显式模型选择
- `purevis` 更适合完整工作流能力
- `volcengine_ark` 可作为通用默认媒体后端
- `vidu` / `kling` 当前不应默认承诺为可直接使用

这个粒度是可以接受的。

但不建议在 prompt 里长期硬编码：

- `lib_nano_2`
- `lib_nano_pro`
- `seedance_2_0`
- `seedance_2_0_fast`
- `kling_o3`

因为这类模型名未来最容易变化。

## 11. 推荐的过渡方案

如果你们现在还没有 `catalog.py` 和 `router.py`，最佳过渡方案是：

### 阶段一

先给 `orchestrator` 系统提示词增加“媒体 Provider 感知与配置引导规则”。

### 阶段二

新增：

- `get_media_provider_catalog()`

让 `orchestrator` 在涉及媒体路由意图时先读目录。

### 阶段三

新增：

- `resolve_media_provider()`

把最终选择彻底从 prompt 记忆迁移到代码逻辑。

## 12. 一句话结论

你的理解是对的：

- `orchestrator` 的系统提示词里确实应该增加“当前系统存在不同媒体 provider，能力不同，配置切换方式不同”的认知规则

但最佳实践不是把完整 provider 和模型清单全部塞进系统提示词，而是：

- 在 prompt 中放稳定决策规则
- 在 catalog 中放当前支持事实
- 在 router 中放最终选择逻辑

这才是可持续、可维护、符合业界最佳实践的设计。
