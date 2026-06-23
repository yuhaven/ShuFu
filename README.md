<div align="center">

# ShuFu（鼠符）

**让设备拥有可控的大模型调用与记忆接力能力。**

一个极简、开源、跨平台的模型运行层：桌面跑节点，Android 发现与调用，ESP32 接入设备能力，Agent Lite 在白名单和逐次审批下行动。

[![Version](https://img.shields.io/badge/version-v0.4.0-3DDC97?style=flat-square)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Android](https://img.shields.io/badge/android-SDK%20%2B%20App-3DDC84?style=flat-square&logo=android&logoColor=white)](android/README.md)
[![ESP--IDF](https://img.shields.io/badge/ESP--IDF-client-E7352C?style=flat-square)](esp32/README.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-FFB454?style=flat-square)](LICENSE)

</div>

---

## 它是什么

ShuFu 是一层“小而清楚”的 AI 运行与调用基础设施。它不试图把所有设备变成完整智能体，而是把模型、记忆、产物、节点发现、同步和有限工具调用整理成一套可验证的协议。

- **Windows / Linux**：运行 Python CLI、HTTP Node、本地 GGUF 或 OpenAI-compatible runtime。
- **Android**：通过 SDK/App 发现节点、调用模型、同步记忆，并可在 ARM64 上运行 GGUF。
- **ESP32**：通过 ESP-IDF Client 调用 ShuFu Node，只暴露固件预注册的工具边界。
- **Agent Lite**：只使用宿主白名单工具；副作用每次审批；上下文由用户显式选择。

> 当前版本是 v0.4 development preview。它适合技术预览、协议验证和早期协作，不是稳定的通用自主智能体平台。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 本地运行 | 内置零依赖 `echo` runtime，可选 `llama-cpp-python` GGUF runtime 和 OpenAI-compatible runtime |
| 节点调用 | HTTP Node 默认仅监听 `127.0.0.1`，局域网必须显式开启并可配置 token |
| 记忆接力 | SQLite 会话记忆、Markdown/文档产物索引、导入导出、增量同步和 v0.1 Bundle 兼容 |
| 流式协议 | v0.3 NDJSON 流式调用、Schema 3 分块/引用产物、双游标同步 |
| Android | 可复用 AAR SDK、示例 App、SQLite 存储、模型管理、llama.cpp `b9722` JNI |
| ESP32 | ESP-IDF 组件、固定缓冲流解析、GPIO/传感器工具注册边界 |
| Agent Lite | 严格 JSON planner、1-10 步限制、时间预算、取消、逐次副作用审批和脱敏审计 |
| 摘要记忆 | 摘要与原始消息分库，保存来源 ID、角色、时间和内容 SHA-256 |

## 快速开始

```powershell
python -m pip install -e .
shufu doctor
shufu run "你好，鼠符"
```

默认使用内置 `echo` runtime，因此无需模型、无需网络，也能验证 CLI 到 runtime 的完整链路。

保存输出并接入会话记忆：

```powershell
shufu run "写一份项目会议纪要" --session project-a --save-output meeting.md
shufu memory list --session project-a
shufu memory export project-a-memory.json --session project-a
```

在另一台设备或另一个节点继续：

```powershell
shufu memory import project-a-memory.json
shufu run "继续完善刚才的会议纪要" --session project-a
```

## 常用命令

| 场景 | 命令 |
| --- | --- |
| 安装本地 GGUF 支持 | `python -m pip install -e ".[llama]"` |
| 调用 GGUF 模型 | `shufu run "你好" --runtime llama --model-path C:\models\model.gguf` |
| 启动本机节点 | `shufu serve` |
| 显式开放局域网 | `shufu serve --host 0.0.0.0 --allow-lan --token "replace-me"` |
| 调用远端节点 | `shufu invoke "从另一进程调用模型" --session project-a` |
| 流式调用 | `shufu invoke "流式返回内容" --stream --session project-a` |
| 双游标同步 | `shufu sync --url http://192.168.1.20:7878 --token replace-me --session project-a` |
| 查看原始消息 | `shufu memory messages --session project-a` |
| 创建摘要记忆 | `shufu summary add "用户正在完善设备协议" --session project-a --source-message-id MESSAGE_ID` |

## Agent Lite

Agent Lite 的目标不是“放权给模型”，而是让模型在有限步骤内请求少量宿主能力，同时把危险边界留在宿主和用户手里。

```powershell
shufu agent "根据已选文档给出下一步" --session project-a `
  --artifact-id ARTIFACT_ID --summary-id SUMMARY_ID `
  --runtime openai --base-url http://127.0.0.1:11434
```

运行边界：

- 只有 `--artifact-id` / `--summary-id` 显式选择的数据会进入本次上下文；
- 工具必须由宿主预注册，模型不能注册、下载或执行任意工具；
- 写入产物等副作用每次都会请求批准，拒绝时不会调用 handler；
- 默认 `echo` runtime 不是 JSON planner，Agent 命令需要显式选择 `llama` 或 `openai` runtime；
- 当前 `agent.http_transport=false`，远程 Agent HTTP transport 尚未开放。

## 平台接入

### Android

Android 工程位于 [`android/`](android/README.md)，包含：

- `shufu-sdk`：模型调用、节点发现、记忆、同步、模型管理和 llama.cpp JNI；
- `app`：可直接安装的极简示例 App。

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

如需使用已缓存的 llama.cpp 官方归档：

```powershell
.\gradlew.bat assembleDebug -PshufuLlamaArchive=C:\cache\llama.cpp-b9722.zip
```

### ESP32

ESP-IDF 组件位于 [`esp32/components/shufu`](esp32/components/shufu)，仅调用 ShuFu Node，不在 MCU 本地运行大语言模型。示例、接入方式和硬件验证边界见 [`esp32/README.md`](esp32/README.md)。

## 测试

```powershell
python -m unittest discover -s tests -v
```

版本专项：

```powershell
python -m unittest discover -s tests -p "test_v03*.py" -v
python -m unittest discover -s tests -p "test_v04*.py" -v
python -m unittest discover -s tests -p test_v01_compat.py -v
```

Android 跨语言用例需要显式提供 Python 和仓库路径，否则会跳过：

```powershell
$env:SHUFU_PYTHON = (Get-Command python).Source
$env:SHUFU_REPO_ROOT = (Resolve-Path .).Path
cd android
.\gradlew.bat :shufu-sdk:testDebugUnitTest --rerun-tasks
```

## 文档导航

| 版本 | 产品文档 | 设计说明 | 协议 | 测试报告 | 机器可读验证 |
| --- | --- | --- | --- | --- | --- |
| v0.1 | [产品文档](docs/product-v0.1.md) | [设计](docs/v0.1-design.md) | [Protocol](docs/protocol-v0.1.md) | [测试报告](docs/test-report-v0.1.md) | [验证 JSON](outputs/v0.1-verification.json) |
| v0.2 | [产品文档](docs/product-v0.2.md) | [设计](docs/v0.2-design.md) | [Protocol](docs/protocol-v0.2.md) | [测试报告](docs/test-report-v0.2.md) | [验证 JSON](outputs/v0.2-verification.json) |
| v0.3 | [产品文档](docs/product-v0.3.md) | [设计](docs/v0.3-design.md) | [Protocol](docs/protocol-v0.3.md) | [测试报告](docs/test-report-v0.3.md) | [验证 JSON](outputs/v0.3-verification.json) |
| v0.4 | [产品文档](docs/product-v0.4.md) | [设计](docs/v0.4-design.md) | [Protocol](docs/protocol-v0.4.md) | [测试报告](docs/test-report-v0.4.md) | [验证 JSON](outputs/v0.4-verification.json) |

## 路线图

- v0.1：冻结兼容基线，提供 CLI、Node、记忆 Bundle 和基础运行时边界；
- v0.2：Android SDK/App、本地 GGUF、UDP 发现和增量同步；
- v0.3：NDJSON 流式调用、Schema 3 产物、ESP-IDF Client；
- v0.4：Agent Lite、显式 artifact 上下文、摘要记忆和审计；
- v1.0：在真实设备、真实模型和真实开发者工作流中收敛稳定协议。

## 贡献

欢迎围绕协议、Android SDK、ESP32 组件、真实设备验证和安全边界一起推进。开始前建议先阅读：

- [`docs/product-v0.4.md`](docs/product-v0.4.md)
- [`docs/protocol-v0.4.md`](docs/protocol-v0.4.md)
- [`docs/release-process.md`](docs/release-process.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## License

Apache-2.0. 详见 [`LICENSE`](LICENSE)。
