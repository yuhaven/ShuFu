# ShuFu（鼠符）v0.4

ShuFu 是一个极简、开源的大模型运行与调用层。Windows/Linux 可以运行模型节点；Android 可以发现、调用、同步并本地运行 GGUF；ESP32 通过 ESP-IDF SDK 调用节点；Agent Lite 在严格白名单、逐次审批和显式上下文选择下使用少量宿主能力。

当前 v0.4 包含：

- 本地 CLI 与 HTTP Node；
- 内置零依赖 `echo` runtime，便于立即运行和测试；
- 可选 `llama-cpp-python` 本地 GGUF runtime；
- OpenAI-compatible runtime；
- SQLite 会话记忆；
- Markdown/文档产物索引与跨节点导入导出；
- 本机默认可信、局域网显式开启、可选单令牌；
- 有界 Agent Lite、严格 JSON planner、逐次副作用审批和脱敏审计；
- UDP 局域网节点发现；
- 带游标的增量记忆同步，并兼容 v0.1 Bundle；
- Android App 与可复用 AAR SDK；
- Android SQLite 会话/产物存储；
- Android ARM64 llama.cpp `b9722` JNI 本地推理；
- GGUF 导入、下载和 SHA-256 校验。
- v0.3 NDJSON 流式调用、Schema 3 分块/引用产物和双游标同步；
- ESP-IDF Client、固定缓冲流解析与预注册 GPIO/传感器工具边界；
- 用户显式选择的 artifact 上下文；
- 与原始消息分离、逐来源校验的摘要记忆。

## 快速开始

```powershell
python -m pip install -e .
shufu doctor
shufu run "你好，鼠符"
```

默认使用内置 runtime，因此无需模型和网络即可验证完整链路。

保存模型输出为 Markdown，并加入当前会话记忆：

```powershell
shufu run "写一份项目会议纪要" --session project-a --save-output meeting.md
shufu memory list --session project-a
shufu memory export project-a-memory.json --session project-a
```

另一台设备或未来 Android 客户端可以导入：

```powershell
shufu memory import project-a-memory.json
shufu run "继续完善刚才的会议纪要" --session project-a
```

## 本地模型

安装可选依赖后运行 GGUF 模型：

```powershell
python -m pip install -e ".[llama]"
shufu run "你好" --runtime llama --model-path C:\models\model.gguf
```

## 启动节点

```powershell
shufu serve
```

默认只监听 `127.0.0.1:7878`。开放局域网必须显式执行：

```powershell
shufu serve --host 0.0.0.0 --allow-lan --token "replace-me"
```

启用 `--allow-lan` 后默认同时开启 UDP 7879 发现服务。Android App 可以自动找到该节点。

调用节点：

```powershell
shufu invoke "从另一进程调用模型" --session project-a
```

使用 v0.3 双游标同步两个 ShuFu 节点：

```powershell
shufu sync --url http://192.168.1.20:7878 --token replace-me --session project-a
```

流式调用：

```powershell
shufu invoke "流式返回内容" --stream --session project-a
```

## Agent Lite 与摘要记忆

先查看原始消息 ID，再创建可追溯摘要：

```powershell
shufu memory messages --session project-a
shufu summary add "用户正在完善设备协议" --session project-a `
  --source-message-id MESSAGE_ID
```

运行本地 Agent Lite。只有通过 `--artifact-id` / `--summary-id` 明确选择的数据才会进入本次上下文；写入产物等副作用每次都会询问批准：

```powershell
shufu agent "根据已选文档给出下一步" --session project-a `
  --artifact-id ARTIFACT_ID --summary-id SUMMARY_ID `
  --runtime openai --base-url http://127.0.0.1:11434
```

默认 `echo` runtime 不是 JSON planner，因此 Agent 命令要求显式选择 `llama` 或 `openai` runtime。Agent HTTP transport 尚未开放，capabilities 会明确报告 `http_transport=false`。

## ESP32

ESP-IDF 组件位于 `esp32/components/shufu`，仅调用 ShuFu Node，不在 MCU 本地运行大语言模型。示例、接入方式和硬件验证边界见 [esp32/README.md](esp32/README.md)。

## Android

Android 工程位于 `android/`，包含：

- `shufu-sdk`：模型调用、发现、记忆、同步、模型管理和 llama.cpp JNI；
- `app`：可直接安装的极简示例 App。

构建：

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

如果 CI 已缓存 llama.cpp 官方归档：

```powershell
.\gradlew.bat assembleDebug -PshufuLlamaArchive=C:\cache\llama.cpp-b9722.zip
```

详细说明见 [android/README.md](android/README.md)。

## 测试

```powershell
python -m unittest discover -s tests -v
```

分别运行 v0.3 / v0.4 专项：

```powershell
python -m unittest discover -s tests -p "test_v03*.py" -v
python -m unittest discover -s tests -p "test_v04*.py" -v
```

只运行冻结的 v0.1 兼容契约：

```powershell
python -m unittest discover -s tests -p test_v01_compat.py -v
```

Android 的 `PythonNodeInteropTest` 需要显式提供 Python 和仓库路径，否则该用例会跳过：

```powershell
$env:SHUFU_PYTHON = (Get-Command python).Source
$env:SHUFU_REPO_ROOT = (Resolve-Path .).Path
cd android
.\gradlew.bat :shufu-sdk:testDebugUnitTest --rerun-tasks
```

## 文档导航

| 版本 | 产品文档 | 设计说明 | 协议 | 测试报告 | 机器可读验证 |
| --- | --- | --- | --- | --- | --- |
| v0.1 | [详细产品文档](docs/product-v0.1.md) | [设计](docs/v0.1-design.md) | [Protocol v0.1](docs/protocol-v0.1.md) | [测试报告](docs/test-report-v0.1.md) | [验证 JSON](outputs/v0.1-verification.json) |
| v0.2 | [详细产品文档](docs/product-v0.2.md) | [设计](docs/v0.2-design.md) | [Protocol v0.2](docs/protocol-v0.2.md) | [测试报告](docs/test-report-v0.2.md) | [验证 JSON](outputs/v0.2-verification.json) |
| v0.3 | [详细产品文档](docs/product-v0.3.md) | [设计](docs/v0.3-design.md) | [Protocol v0.3](docs/protocol-v0.3.md) | [测试报告](docs/test-report-v0.3.md) | [验证 JSON](outputs/v0.3-verification.json) |
| v0.4 | [详细产品文档](docs/product-v0.4.md) | [设计](docs/v0.4-design.md) | [Protocol v0.4](docs/protocol-v0.4.md) | [测试报告](docs/test-report-v0.4.md) | [验证 JSON](outputs/v0.4-verification.json) |

v0.1 是冻结兼容基线；当前源码版本是 v0.4，并持续提供 `/shufu/v1/*`、Schema 1，以及 v0.2/v0.3 的兼容能力。
