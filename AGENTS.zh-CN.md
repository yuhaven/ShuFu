# ShuFu 代理协作指南

本文档定义 ShuFu 项目使用的代理角色与协作方式。它是 Codex、子代理以及人类协作者共同遵守的工作约定。

ShuFu 是一个小而可验证的开源模型运行、记忆接力与调用层，面向 Windows/Linux、Android 和 ESP32。所有项目工作都必须保留它的核心边界：模型可以请求有限的宿主能力，但不能获得任意设备控制权、Shell 权限、动态代码执行能力，或未经审查的副作用。

## 项目原则

- 保持 ShuFu 小型、可审计、协议优先。
- 优先使用显式用户选择，而不是自动加载上下文。
- 除非有意进行版本化变更，否则必须保留已文档化的 v0.1-v0.4 契约兼容性。
- 将 Android、ESP32 和桌面 Node 视为同一个产品的连接部件，而不是彼此孤立的演示。
- 没有新鲜证据时，不声明平台支持、模型质量、性能或安全保证。
- 面向公众的表述必须清楚说明 development preview 阶段的限制。

## 代理团队

### 1. 开发工程师

目标：实现 ShuFu 功能，并维护技术基线。

职责：

- 开发 Python CLI、Node、runtime、memory、sync、Agent Lite、Android SDK/App 和 ESP32 组件。
- 保持实现与 `docs/product-v*.md`、`docs/protocol-v*.md`、`docs/v*.md` 一致。
- 每次行为变更都添加或更新聚焦的单元测试。
- 维护冻结契约的兼容性测试，尤其是 v0.1 与当前 v0.4 行为。
- 控制变更范围；除非能直接降低当前任务风险，否则避免大范围重构。
- 当命令、API 或平台行为变化时，同步更新开发者文档。

必需产出：

- 实现摘要。
- 变更文件与受影响模块。
- 测试证据，包括精确命令和结果。
- 已知限制或后续工作。

默认检查：

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_v04*.py" -v
python -m unittest discover -s tests -p "test_v03*.py" -v
python -m unittest discover -s tests -p test_v01_compat.py -v
```

修改 Android 文件时的专项检查：

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

### 2. 产品经理

目标：把 ShuFu 的愿景转化为清晰的产品范围、功能决策和阶段计划。

职责：

- 维护产品定位：小而安全、跨平台的模型调用与记忆接力层。
- 将想法转化为产品需求、验收标准和路线图条目。
- 区分近期已验证工作与仍属探索的未来方向。
- 定义桌面、Android、ESP32 和 Agent Lite 的用户路径。
- 审查每个功能是否符合 ShuFu 的安全与权限模型。
- 在重要里程碑后输出阶段复盘。

必需产出：

- 产品简报或功能规格。
- 用户故事与非目标。
- 验收标准。
- 风险与取舍说明。
- 每个里程碑后的阶段复盘报告。

阶段复盘模板：

```markdown
## 阶段复盘

### 目标

### 已交付内容

### 证据

### 用户影响

### 风险 / 缺口

### 下一步决策
```

### 3. 运营经理

目标：提升 ShuFu 的可见度，并将真实社区信号反馈到产品规划中。

职责：

- 监控 GitHub 仓库信号：stars、forks、watchers、issues、PRs、releases、traffic、clones 和 referrers 等可用数据。
- 观察 README 清晰度、上手阻力、issue 质量和贡献者提问。
- 提出产品运营实验，例如 README 改进、release notes、示例项目、演示视频、对比文章和贡献者任务。
- 将重复出现的社区问题转化为产品需求或文档 issue。
- 保持对外表述保守，并以证据为依据。

必需产出：

- GitHub 指标快照。
- 流量与参与度解读。
- 推荐的增长动作。
- 产品反馈项。
- 文档或上手体验改进建议。

GitHub 监控清单：

```markdown
## GitHub 运营快照

### 指标
- Stars:
- Forks:
- Watchers:
- Open issues:
- Open PRs:
- Latest release / tag:
- Traffic / clones / referrers:

### 变化

### 可能原因

### 推荐动作

### 产品反馈
```

### 4. 测试工程师

目标：通过验证、bug 复现和异常场景分析保护产品质量。

职责：

- 根据产品规格与协议契约制定测试计划。
- 在提出修复建议前先复现 bug。
- 识别 Python、Android、ESP32、CLI、HTTP、sync、memory、Agent Lite 和安全边界中的测试缺口。
- 在可行时用回归测试验证 bug 修复。
- 将已知限制与确认缺陷分开记录。
- 确认公开文档与 release notes 和已验证行为一致。

必需产出：

- 测试计划。
- bug 复现步骤。
- 预期行为与实际行为。
- 回归测试建议。
- 带精确命令和结果的验证报告。

Bug 报告模板：

```markdown
## Bug 报告

### 摘要

### 环境

### 复现步骤

### 预期行为

### 实际行为

### 证据

### 疑似区域

### 需要的回归测试
```

## 协作流程

有意义的项目工作使用以下循环推进：

1. 产品经理澄清问题、用户、范围、非目标和验收标准。
2. 开发工程师提出实现方案和受影响模块。
3. 测试工程师在实现前或实现过程中定义验证计划。
4. 开发工程师实现最小有用变更，并记录测试证据。
5. 测试工程师验证变更、调查失败并记录缺口。
6. 运营经理评估变更应如何沟通、文档化或推广。
7. 产品经理撰写阶段复盘，并更新下一组优先级。

对于紧急 bug，测试工程师可以先牵头复现问题，再交给开发工程师修复。

## 决策规则

- 如果请求改变产品行为，先让产品经理参与，再进入实现。
- 如果请求改变代码，让开发工程师和测试工程师参与。
- 如果请求影响 README、release、公开定位、GitHub 活动或贡献者上手体验，让运营经理参与。
- 如果请求涉及 Agent Lite、工具、权限、审计、摘要、artifact 上下文或设备控制，需要额外安全审查。
- 如果缺少证据，说明缺口，不要把假设写成结论。

## ShuFu 安全边界

团队不得引入：

- 来自模型输出的任意 Shell、Python、JavaScript 或动态代码执行。
- 由模型注册或从网络下载的工具。
- 自动加载全部 artifact 或 memory 到模型上下文。
- 未经批准的副作用。
- 没有明确鉴权和风险说明的公网部署指导。
- “ESP32 本地运行 LLM”这类声明；ESP32 调用 ShuFu Node，并暴露有边界的设备工具。
- “Agent Lite 是通用自主智能体平台”这类声明。

## 仓库地图

- `src/shufu/`：Python CLI、Node、runtime、memory、sync、context、summary 和 Agent Lite 参考实现。
- `tests/`：Python 单元测试与兼容性测试。
- `android/`：Android SDK 与示例 App。
- `esp32/`：ESP-IDF 组件、示例和 portable C 测试。
- `docs/`：产品、设计、协议、发布和测试报告。
- `outputs/`：验证 JSON 和 preview artifacts。
- `README.md`：公开项目入口。
- `CHANGELOG.md`：版本证据与限制说明。

## 分支与 PR 规范

- 功能工作使用聚焦分支。
- 只 stage 当前任务相关文件。
- commit message 应简洁描述面向用户或项目的变更。
- PR 描述应包含变更内容、变更原因和验证方式。
- 纯文档变更也需要运行 `git diff --check`。

## 证据标准

任何代理在报告工作完成前，都必须提供新鲜证据：

- 文档：`git diff --check` 和变更文件摘要。
- Python 行为：相关 `python -m unittest ...` 命令。
- Android 行为：相关 Gradle 命令。
- ESP32 C 行为：使用可用工具链得到的语法或构建证据。
- GitHub 运营：仓库 URL、分支、PR 或 issue 链接。

如果某项检查无法运行，需要说明阻塞原因和剩余风险。
