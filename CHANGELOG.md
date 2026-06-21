# Changelog

ShuFu（鼠符）的重要变更记录在此文件中。格式参考 Keep a Changelog；在 Git
标签建立前，版本日期表示该版本证据完成验证的日期，不表示已经发布到 GitHub。

## [Unreleased]

当前没有已验证但尚未归入版本的功能。

## [0.4.0 development preview] - 2026-06-21

状态：**本地 Agent Lite 开发预览完成**。这不是稳定版或通用自主智能体平台。

### Added

- 有界 Agent Lite 循环、严格 JSON 动作、最大步数、超时、取消与终态审计。
- 宿主预注册工具和逐次副作用审批；拒绝时不调用 handler。
- 仅由用户显式选择的同会话 artifact 上下文，并校验 MIME、大小、UTF-8 与哈希。
- 与原始消息分库的摘要记忆，保存真实来源 ID、角色和内容指纹。
- 本地 CLI Agent、摘要命令和脱敏 JSONL 审计；capabilities 明确
  `http_transport=false`。

### Security

合并审计发现并修复：

- 审批值必须是字面量布尔 `True`，不再接受其他 truthy 值；
- 审批和执行使用规范参数深拷贝，消除嵌套参数 TOCTOU；
- 已批准副作用在 handler 安全收敛后才形成终态，避免终态后继续写入；
- 摘要只能引用真实消息，并在保存和读取时复核来源；
- artifact 与摘要上下文具有数量、单项和总量边界；
- `BaseException` 也被转换为失败结果并记录终态；
- 审计快照不可由外部回写，持久化 sink 对敏感字段脱敏。

### Verified

- v0.4 专项 23/23、v0.3 专项 12/12、v0.1 兼容 4/4 通过。
- 全量 Python 54/54，`compileall` 通过。
- Android 离线 Gradle 共处理 137 tasks，构建、单元测试和 lint 成功。
- 版本、CLI、capabilities 和 v0.1–v0.3 兼容信息完成集成验证。

### Known limitations

- 没有远程 Agent HTTP transport，Agent 仅通过本地 Python CLI 接入。
- 没有真实 LLM planner 遵循率矩阵。
- 没有 Android 审批 UI、ESP32 Agent/GPIO 硬件端到端验证。
- 本地审计日志尚未覆盖加密、轮转和集中采集。

证据：[产品文档](docs/product-v0.4.md)、[测试报告](docs/test-report-v0.4.md)、
[验证 JSON](outputs/v0.4-verification.json)。

## [0.3.0 development preview] - 2026-06-21

状态：**协议与 ESP32 SDK 开发预览完成**。这不是 ESP32 真机稳定版。

### Added

- NDJSON 流式线路协议和 Python 参考实现。
- Bundle Schema 3：inline、chunks 和 external artifact 表示，以及 HTTP Range。
- 双游标交换和来源节点回声抑制，继续保留不可变 ID 与幂等导入。
- ESP-IDF 组件结构、固定缓冲区 C 分帧器和受限工具注册表。
- GPIO/传感器动作只允许宿主预注册函数，并使用逐次副作用 allowlist。

### Verified

- v0.3 专项 12/12、v0.1 兼容 4/4 通过。
- 最终集成全量 Python 54/54，`compileall` 通过。
- ESP32 C 使用 Android NDK r27c Clang 和
  `-std=c11 -Wall -Wextra -Werror -fsyntax-only` 严格语法检查通过。
- Android 离线 Gradle 共处理 137 tasks，构建、单元测试和 lint 成功。

### Known limitations

- C 检查不等同于 ESP-IDF 工具链构建；本轮没有安装/运行 ESP-IDF 5.1+。
- 没有 ESP32/ESP32-S3 真机、Wi-Fi 重连、长流、功耗或 GPIO 副作用验证。
- Python Runtime 在完整生成后按字符块发送，不宣称 token 首字节流式。

证据：[产品文档](docs/product-v0.3.md)、[测试报告](docs/test-report-v0.3.md)、
[验证 JSON](outputs/v0.3-verification.json)。

## [0.2.0] - 2026-06-21

### Added

- Windows/Linux Python Node v0.2 能力协商与 UDP 局域网发现。
- Schema 2 Memory Bundle、增量 pull、幂等 push 与游标同步。
- Android Kotlin SDK：远程调用、发现、本地记忆和同步。
- Android ARM64 llama.cpp JNI、本地 GGUF 模型管理、Debug AAR/APK。

### Compatibility

- 保留 `/shufu/v1/*` 调用端点。
- 保留 Memory Bundle Schema 1 导入导出兼容性。

### Verified

- Python：19 项测试通过，0 失败、0 错误、0 跳过。
- v0.1 专项兼容：4 项通过。
- Android JVM/跨语言：4 项通过，Python Node 互操作未跳过。
- ARM64 Debug APK、AAR、JNI 构建通过；Release Lint 0 错误、4 警告。
- 发布物 SHA-256 与 `outputs/SHA256SUMS-v0.2.txt` 一致。

### Known limitations

- 未在物理 Android 设备上测试。
- 未执行真实 GGUF 推理和性能测试。
- APK 使用 Android Debug 签名，仅适合技术预览。
- 局域网仍为明文 HTTP，不能作为公网部署方案。

证据：[产品文档](docs/product-v0.2.md)、[测试报告](docs/test-report-v0.2.md)、
[验证 JSON](outputs/v0.2-verification.json)。

## [0.1.0 compatibility baseline] - 2026-06-21

### Added

- 极简 CLI：诊断、单次调用、Node 服务、记忆导入导出和产物保存。
- Echo、GGUF/llama.cpp 和 OpenAI-compatible 运行时适配边界。
- SQLite 会话/消息/产物记忆和 Bundle Schema 1。
- 默认回环监听、显式 LAN 开关和可选静态 Bearer Token。
- Agent Lite 的工具注册、参数校验、超时、步数和副作用许可边界。

### Verified

- 冻结的 v0.1 HTTP/Schema 契约专项测试：4 项通过。
- 在当前 0.2.0 实现上执行完整 Python 回归：19 项通过。
- CLI 调用、保存产物、导出和导入冒烟通过。

### Known limitations

- 当前仓库不保存独立的 v0.1 源码快照；v0.1 是冻结兼容基线。
- Linux、真实 GGUF 和外部 OpenAI-compatible 服务未实机验证。
- Bundle 未签名/加密，静态 Token 不适用于公网。

证据：[产品文档](docs/product-v0.1.md)、[测试报告](docs/test-report-v0.1.md)、
[验证 JSON](outputs/v0.1-verification.json)。
