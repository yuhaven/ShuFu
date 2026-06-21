# ShuFu 发布流程

本流程适用于开源技术预览、候选版本和稳定版本。核心原则是：版本能力由可复现
证据证明，平台构建、协议兼容与真实设备验证分别判定，不能互相替代。

## 1. 版本与兼容策略

- v0.1 是冻结兼容基线：`/shufu/v1/*` 和 Bundle Schema 1 不做破坏性修改。
- v0.2 引入能力协商、Schema 2、Android 和增量同步；新增能力通过 capabilities 暴露。
- v0.3 目标是 ESP-IDF、流式调用和预注册设备工具，并改善弱网/大产物同步。
- v0.4 目标是受限 Agent Lite、显式产物注入和摘要记忆。
- 客户端必须按能力协商降级。协议、Schema 或工具权限发生破坏性变化时，必须升级主版本或新增端点，而不是静默改变旧端点。

## 2. 发布等级

| 等级 | 允许的未覆盖项 | 命名与说明 |
| --- | --- | --- |
| 开发快照 | 可以缺少真机/性能证据，但测试失败必须公开 | 不创建稳定标签；明确 commit SHA |
| 技术预览 | 核心自动化必须通过；真机/模型缺口必须列在 Release Notes | `vX.Y.0-preview.N` |
| 候选版本 | 目标平台、真实设备和真实模型主路径必须通过 | `vX.Y.0-rc.N` |
| 稳定版本 | 所有阻断门槛关闭，使用正式签名并具备回滚信息 | `vX.Y.Z` |

## 3. 每个版本的必需产物

- `docs/product-vX.Y.md`：目标、非目标、用户场景和验收标准；
- `docs/vX.Y-design.md`：架构、数据、权限和失败模式；
- `docs/protocol-vX.Y.md`：端点、能力、Schema 和兼容规则；
- `docs/test-report-vX.Y.md`：环境、命令、结果、跳过项和风险；
- `outputs/vX.Y-verification.json`：机器可读测试与发布门槛；
- 二进制发布物、许可证信息和 `SHA256SUMS-vX.Y.txt`（如该版本产生二进制）；
- `CHANGELOG.md`、开发日志和 GitHub Release Notes。

若某版本没有对应产物，必须在测试报告中写明“无此产物”，不能用空文件或上一版本文件代替。

## 4. 计划中的 CI 门槛

当前仓库尚未初始化 Git/GitHub，因此以下是待落地 CI 规划，不是已运行状态。

### 4.1 通用文档与供应链

- 检查 Markdown 相对链接、JSON 语法和版本号一致性；
- 验证 SHA-256 清单；
- 禁止密钥、Token、签名库和本机绝对路径进入提交；
- 生成依赖/第三方许可证清单；
- PR 中标出协议、Schema、权限和发布物变化。

### 4.2 Python / Windows / Linux

- Windows 与 Linux 矩阵，Python 3.10–3.12；
- `python -m compileall -q src tests`；
- `python -m unittest discover -s tests -v`；
- `python -m unittest discover -s tests -p test_v01_compat.py -v`；
- CLI run/serve/memory 冒烟；关键兼容测试不允许跳过。

### 4.3 Android

- 固定 JDK、Gradle、Android SDK/Build Tools/NDK 版本；
- Kotlin/JVM 测试和真实 Python Node 互操作测试，互操作不得静默跳过；
- `:shufu-sdk:assembleDebug`、`:app:assembleDebug`、Release Lint；
- 检查 AAR/APK ABI、JNI 导出和 SHA-256；
- 候选/稳定版增加物理 ARM64 设备安装、调用、同步和真实 GGUF 测试；
- 稳定版使用受控 Release Key，CI 只通过秘密存储注入。

### 4.4 ESP32 / v0.3

- 固定 ESP-IDF 版本和至少一个代表性目标芯片；
- SDK 示例 `idf.py build`；
- 协议解析、断流重连、分块、超时和内存上限测试；
- 与真实 ShuFu Node 的流式/非流式互操作；
- 预注册 GPIO/传感器工具的白名单、参数和拒绝路径测试；
- 候选/稳定版必须在明确型号的物理板卡执行，并记录 Flash、峰值 RAM 和网络环境。

### 4.5 Agent Lite / v0.4

- 工具选择和状态机使用确定性测试模型；
- 最大步数、总超时、单工具超时和取消路径；
- 未注册工具、非法参数和副作用授权拒绝；
- 产物仅在用户显式选择后注入；
- 摘要记忆可追溯到原 session，导入/导出保持旧 Schema 兼容；
- 任何形式的任意脚本/代码执行均作为阻断缺陷。

## 5. 本地发布检查

1. 从干净工作树构建，不复用来源未知的输出目录。
2. 核对版本号、capabilities、协议文档和验证 JSON。
3. 执行对应平台的全量测试，记录原始命令与结果。
4. 检查关键测试是否跳过；关键跳过等同未通过。
5. 从发布物重新计算 SHA-256，并核对架构、签名与许可证。
6. 更新 Changelog、开发日志、测试报告和已知限制。
7. 用全新目录/设备按 README 安装和执行最短主路径。

## 6. GitHub 建仓与上传前置条件

当前本机没有 Git 仓库、Git CLI 或 GitHub CLI。执行上传前必须：

1. 安装并验证 `git --version`；
2. 安装并验证 `gh --version`，或明确采用 Git Credential Manager/SSH；
3. 明确 GitHub owner、仓库名和 public/private；开源目标默认建议 public，但不得代替用户决定；
4. 使用用户确认的 `user.name`/`user.email` 配置提交身份；
5. 认证后用 `gh auth status` 验证目标账号，不在日志中输出 Token；
6. 检查 `.gitignore`、大文件、模型、构建缓存、签名文件和敏感信息；
7. 初始化仓库、创建最小且可审查的提交，再添加远端；
8. 推送开发分支并创建 PR；CI 通过和审查完成后再合并/打标签；
9. GitHub Release 附带验证 JSON、校验清单、发布物和已知限制。

禁止把真实模型、Android 签名私钥、API Key、Bearer Token、本机数据库或用户记忆上传到仓库。

## 7. PR 与合并规则

- 每个 PR 只对应一个清晰的产品规划范围；v0.3 与 v0.4 证据独立。
- 协议/Schema 变化必须同时更新兼容测试和文档。
- 修改权限边界、Agent 工具或网络暴露默认值，必须列为安全相关变化。
- 所有测试失败和关键跳过必须在 PR 描述中公开。
- 二进制文件只有在发布流程需要且来源可复现时提交；大模型文件不入 Git。
- 至少一次人工审查确认产品仍聚焦“跨平台调用/运行模型”这一单一问题。

## 8. 发布与回滚

- 标签必须指向通过门槛的不可变提交；不要移动或覆盖既有标签。
- Release Notes 列出新增、兼容、修复、风险、测试设备和 SHA-256。
- 若协议回归，优先禁用新 capability 并回退到上一兼容端点；不得破坏 v0.1 基线数据。
- 若 Android/ESP32 二进制有问题，撤下受影响附件并发布补丁版本，保留原 Release 的问题说明。
- 若记忆迁移有风险，先备份 Bundle；迁移必须幂等，并提供旧 Schema 导出路径。

