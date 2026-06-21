# ShuFu（鼠符）v0.1 产品文档

> 文档状态：已冻结的首个可运行版本基线  
> 对应协议：ShuFu Protocol v0.1  
> 当前维护方式：v0.2 源码继续兼容 v0.1 API 与 Memory Bundle Schema 1  
> 最后整理：2026-06-21

## 1. 产品概述

ShuFu 是一个极简、开源的大模型运行与调用层。名称来自《成龙历险记》中的“鼠符咒”：产品不试图取代模型、操作系统或硬件厂商，而是给不同设备提供统一的模型调用、会话连续性和安全扩展能力。

v0.1 只验证一个核心命题：**在 Windows/Linux 上安装一个小型组件后，用户可以立即调用模型、保留会话，并通过稳定协议把能力暴露给其他设备。**

本版本的产品原则是：

1. 安装后先能运行，再逐步选择真实模型；
2. 模型运行时与产品协议解耦；
3. 默认仅本机可访问，局域网暴露必须显式开启；
4. 会话和产物可迁移，但不引入云账号和中心服务；
5. Agent 只保留轻量、安全的扩展点，不执行模型生成的任意代码。

## 2. 用户与核心场景

### 2.1 目标用户

| 用户 | 主要诉求 | v0.1 提供的价值 |
| --- | --- | --- |
| 本地模型使用者 | 用统一方式运行 GGUF 或已有模型服务 | `shufu run` 屏蔽运行时差异 |
| 开发者 | 为应用增加稳定的模型调用接口 | 本地 HTTP/JSON Node 与 Python Client |
| 开源贡献者 | 理解并扩展最小核心 | Runtime、MemoryStore、Node 清晰分层 |
| 多设备方案设计者 | 先冻结跨设备契约 | v0.1 API 与 Schema 1 Bundle |

### 2.2 关键用户故事

- 作为首次使用者，我不下载模型也能用 `echo` runtime 验证安装和完整链路。
- 作为本地模型用户，我可以通过一个参数切换到 GGUF 模型。
- 作为已有推理服务用户，我可以连接 OpenAI-compatible `/v1/chat/completions` 服务。
- 作为项目用户，我可以给对话指定 session，下次继续同一上下文。
- 作为内容创作者，我可以把模型输出保存为文件，并将文件作为会话产物登记。
- 作为设备集成开发者，我可以通过 `/shufu/v1/*` 调用节点和迁移记忆。

## 3. 版本范围

### 3.1 已交付

- Windows/Linux Python 3.10+ CLI；
- 零外部模型依赖的 `echo` runtime；
- 可选 `llama-cpp-python` GGUF runtime；
- OpenAI-compatible runtime；
- HTTP Node 与 Python Client；
- SQLite 会话、消息、产物元数据；
- SHA-256 内容寻址的产物文件；
- Schema 1 JSON 记忆包导入/导出；
- 本机默认监听与显式局域网边界；
- 可选静态 Bearer Token；
- Agent Lite 的 ToolRegistry 与执行上限模型。

### 3.2 明确不做

- 不适配华为、小米等闭源设备生态；
- v0.1 不交付 Android App、Android SDK 或 ESP32 SDK；
- 不做云账号、计费、模型市场、管理控制台；
- 不做 RAG、向量数据库、长期人格或自动事实提取；
- 不做自主 Agent 循环；
- 不运行模型生成的 Shell、脚本或下载代码；
- 不把服务直接暴露到互联网；
- 不在 ESP32 本地运行大语言模型。

## 4. 产品架构

```text
CLI / Python Client / Future Device Client
                   │
          ShuFu Protocol v0.1
                   │
               ShuFu Node
              ╱          ╲
       Runtime            MemoryStore
      ╱   │    ╲          ╱       ╲
   echo  GGUF  OpenAI   SQLite   artifacts/
```

### 4.1 组件职责

| 组件 | 职责 | 不负责 |
| --- | --- | --- |
| CLI | 参数解析、用户入口、启动 Node | 模型推理实现 |
| Client | v0.1 HTTP/JSON 请求 | 本地存储与重试策略 |
| Node | 校验请求、拼接记忆、调用 Runtime、回写响应 | 具体模型加载 |
| Runtime | 输入消息窗口，返回一条文本 | 会话持久化与网络服务 |
| MemoryStore | session、message、artifact 与 Bundle | 自动选择提示资料 |
| ToolRegistry | 注册宿主工具、控制副作用执行 | 自主规划与任意代码执行 |

这种边界允许后续替换推理后端、网络传输或存储实现，同时保留上层调用方式。

## 5. 功能规格

### 5.1 首次运行与诊断

```powershell
python -m pip install -e .
shufu doctor
shufu run "你好，鼠符"
```

`doctor` 输出版本、Python、操作系统、CPU 架构、数据目录和 runtime 状态。默认 `echo` runtime 是确定性的，只用于验证安装、记忆链路和测试，不代表真实模型质量。

### 5.2 本地调用

```powershell
shufu run "继续完善产品规划" --session product-plan
```

调用顺序固定为：

1. 校验输入和 session；
2. 写入 user message；
3. 按 `memory_window` 读取最近消息；
4. 调用所选 Runtime；
5. 写入 assistant message；
6. 返回模型、session、文本和 UTC 时间。

### 5.3 运行时选择

| Runtime | 参数 | 用途 | 依赖 |
| --- | --- | --- | --- |
| `echo` | 默认 | 安装验证、开发、测试 | 无第三方依赖 |
| `llama` | `--model-path`、`--context-size` | 桌面本地 GGUF 推理 | `llama-cpp-python` |
| `openai` | `--base-url`、`--api-key` | 调用兼容服务 | 仅标准库 HTTP |

Runtime 接口只接收 `model` 与消息序列并返回文本。新增运行时不应直接访问 SQLite 或 HTTP Handler。

### 5.4 会话和产物

```powershell
shufu run "生成会议纪要" --session project-a --save-output meeting.md
shufu memory list --session project-a
shufu memory export project-a.json --session project-a
shufu memory import project-a.json
```

- session 是用户指定的稳定字符串；
- message 角色限定为 `system/user/assistant/tool`；
- 推理只装载最近 N 条消息，防止上下文无限增长；
- artifact 内容按 SHA-256 保存，数据库记录业务 ID 与元数据；
- artifact 不会自动进入提示词，避免文档中的提示注入被无意执行；
- 导入通过稳定对象 ID 去重，内容哈希用于验证产物完整性。

### 5.5 HTTP Node

```powershell
shufu serve
shufu invoke "从另一个进程调用" --session project-a
```

默认地址为 `127.0.0.1:7878`。开放局域网时必须显式声明：

```powershell
shufu serve --host 0.0.0.0 --allow-lan --token "replace-me"
```

v0.1 端点：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 存活检查 |
| GET | `/shufu/v1/capabilities` | 节点、运行时和扩展能力 |
| POST | `/shufu/v1/invoke` | 调用模型并保存会话 |
| GET | `/shufu/v1/memory/export` | 导出 Schema 1 Bundle |
| POST | `/shufu/v1/memory/import` | 幂等导入 Bundle |
| POST | `/shufu/v1/artifacts` | 上传产物 |
| GET | `/shufu/v1/artifacts/{id}` | 获取产物元数据和内容 |

完整字段定义见 [protocol-v0.1.md](protocol-v0.1.md)。

## 6. 数据设计

### 6.1 SQLite 实体

| 实体 | 关键字段 | 说明 |
| --- | --- | --- |
| sessions | id、created_at、updated_at、title | 会话容器 |
| messages | id、session_id、role、content、created_at | 不可变消息 |
| artifacts | id、session_id、name、mime_type、sha256、size、created_at | 产物索引 |
| meta | key、value | 节点级元数据预留 |

默认数据目录为 `~/.shufu`，可通过 `SHUFU_HOME` 或 CLI `--home` 修改。

### 6.2 Bundle Schema 1

Schema 1 包含：

- `schema_version=1`；
- `exported_at`；
- `sessions[]`；
- `messages[]`；
- `artifacts[]`，内容使用 Base64。

它适合小型会话与文档的显式迁移，不适合大模型文件或大规模自动同步。接收端必须忽略未知字段，以便向后兼容。

## 7. Agent Lite 边界

v0.1 的 Agent 能力是一个安全扩展点，而不是自主代理产品：

- Tool 只能由宿主代码预注册；
- 工具名限制为字母、数字和下划线；
- 参数必须是对象；
- 标记 `side_effect=true` 的工具需要显式许可；
- `AgentLimits` 将步骤限制在 1–10，超时限制在 0–300 秒；
- 默认推理流程不会自动调用工具；
- 不提供 eval、Shell、动态模块下载或隐式文件访问。

后续引入 Agent 循环时必须继续沿用这些硬边界，并增加可审计日志、取消机制和逐工具权限。

## 8. 安全、隐私与失败处理

| 风险 | v0.1 策略 | 剩余限制 |
| --- | --- | --- |
| 未授权局域网访问 | 默认回环；LAN 显式开启；可选 Token | Token 无轮换与用户隔离 |
| 会话泄露 | 默认本机 SQLite；导出显式触发 | 本地数据库未加密 |
| 产物篡改 | SHA-256 校验 | Bundle 本身未签名 |
| 重复导入 | 稳定 ID、`INSERT OR IGNORE` | 不解决同 ID 不同内容冲突 |
| 上下文膨胀 | `memory_window` | 无自动摘要 |
| 远程服务异常 | CLI 返回可读错误 | v0.1 无自动重试和熔断 |

## 9. 非功能要求

- 安装：核心仅依赖 Python 标准库；
- 可移植：Windows/Linux 使用相同命令和数据结构；
- 可测试：`echo` runtime 使测试不依赖网络和模型；
- 可恢复：SQLite 事务保护写入，Bundle 导入幂等；
- 可理解：核心模块保持单一职责；
- 兼容：v0.1 API 路径和 Schema 1 在 v0.2 中继续可用；
- 时间：持久化时间统一使用 UTC ISO 8601。

## 10. 验收标准

| 编号 | 验收项 | 判定方式 |
| --- | --- | --- |
| V01-A01 | 零模型依赖可运行 | `shufu run` 返回 echo 响应 |
| V01-A02 | 同 session 连续对话 | 第二次调用读取之前消息 |
| V01-A03 | HTTP 调用可用 | `/shufu/v1/invoke` 返回约定字段 |
| V01-A04 | Schema 1 可迁移 | 导出、导入后消息与产物一致 |
| V01-A05 | 重复导入不复制对象 | 二次导入计数为 0 |
| V01-A06 | 默认网络边界安全 | 非回环地址需要 `--allow-lan` |
| V01-A07 | 有副作用工具需许可 | 未许可执行抛出 `PermissionError` |
| V01-A08 | 可切换真实模型 | llama/OpenAI-compatible 参数可配置 |

对应验证证据见 [test-report-v0.1.md](test-report-v0.1.md)。

## 11. 已知限制与演进

- v0.1 没有 Android/ESP32 可安装物；
- Bundle 每次完整导出，文件使用 Base64，体积会膨胀；
- 没有节点自动发现；
- 没有流式 token；
- ToolRegistry 尚未连接模型决策循环；
- 局域网仅有静态 Token，不适用于互联网服务。

这些限制在 v0.2 中由 Android、节点发现和增量同步部分改善；ESP32、流式调用与 Agent Lite 循环仍属于后续版本。

