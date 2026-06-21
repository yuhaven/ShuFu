# ShuFu（鼠符）v0.2 产品文档

> 文档状态：当前实现版本  
> 对应软件版本：0.2.0  
> 对应协议：ShuFu Protocol v0.2，并保持 v0.1 兼容  
> 最后整理：2026-06-21

## 1. 产品概述

v0.2 将 v0.1 的桌面最小闭环扩展为第一条可运行的跨设备链路：Windows/Linux 负责运行或转接模型，Android 负责发现节点、调用模型、携带记忆，并可在设备本地运行 GGUF 小模型。

```text
Windows / Linux ShuFu Node
       ⇅ 发现、调用、增量同步
Android App / ShuFu AAR SDK
       ↓
Android ARM64 本地 GGUF
```

产品仍只解决一个问题：**让不同平台以一致方式获得模型能力和连续上下文。** v0.2 不扩张为云平台、模型市场或通用自动化系统。

## 2. 目标、指标与边界

### 2.1 版本目标

1. 提供可安装的 Android ARM64 App；
2. 提供可嵌入第三方 App 的 Android AAR；
3. 自动发现可信局域网中的桌面 ShuFu Node；
4. Android 调用 Node，并使用同一 session 连续交互；
5. Windows/Linux 与 Android 之间同步消息和文档产物；
6. Android 可导入并运行用户选择的 GGUF 模型；
7. 不破坏 v0.1 客户端、API 和 Schema 1 Bundle。

### 2.2 成功判据

- 新用户可用内置 echo runtime 启动桌面 Node；
- Android SDK 能发现并调用真实 Python Node；
- Bundle Schema 2 支持 cursor 增量拉取与幂等推送；
- Android 本地记忆和桌面记忆可双向接力；
- APK 和 AAR 可重复构建并通过校验；
- v0.1 专项兼容测试持续通过。

### 2.3 非目标

- 不适配华为、小米等闭源生态或厂商专有设备；
- v0.2 不交付 ESP32 SDK；
- 不支持 iOS、macOS 原生客户端；
- 不做账号、RBAC、云同步、计费和模型商店；
- 不把 Node 作为互联网公开服务；
- 不自动下载、自动信任或后台加载未知模型；
- 不提供完整自主 Agent 循环；
- 不承诺所有 Android 设备都能运行任意规模模型。

## 3. 用户与使用场景

| 场景 | 用户操作 | 产品行为 |
| --- | --- | --- |
| 桌面模型节点 | 启动 `shufu serve` | 暴露统一调用、能力和同步接口 |
| Android 自动发现 | 点击“发现节点” | UDP 广播并填入首个发现节点 URL |
| 远程调用 | 输入 prompt 和 session | 调用桌面 Node，随后同步记忆 |
| 跨端接力 | 点击“同步记忆” | 推送本地 Bundle，按 cursor 拉取远端增量 |
| Android 本地推理 | 导入 GGUF 后点击“本地生成” | JNI 调用 llama.cpp，结果写入同一 session |
| SDK 集成 | App 引入 AAR | 直接使用 Client、MemoryStore、SyncEngine 等 API |

## 4. 系统架构

### 4.1 桌面端

桌面继续使用 v0.1 的 CLI、Node、Runtime、MemoryStore，并新增：

- UDP Discovery Responder；
- 持久化 `node_id`；
- `changes.seq` 单调变更日志；
- Schema 2 Bundle；
- `/shufu/v2/sync/pull` 与 `/shufu/v2/sync/push`；
- `shufu discover` 与 `shufu sync`。

### 4.2 Android SDK

| 类 | 职责 | 关键边界 |
| --- | --- | --- |
| `ShuFuHttpClient` | capabilities、invoke、pull、push | 不决定线程模型，不保存数据 |
| `ShuFuDiscoveryClient` | UDP 节点发现 | 仅返回候选节点，不建立信任 |
| `ShuFuMemoryStore` | SQLite 消息、产物、变更游标 | 使用 App 私有目录 |
| `ShuFuSyncEngine` | 编排 push/pull/import/cursor | 不做后台常驻同步 |
| `ModelManager` | 导入、下载、校验、列出 GGUF | 文件名限制，支持 SHA-256 |
| `LlamaCppRuntime` | Kotlin/JNI 生命周期与生成接口 | 单模型句柄、同步生成 |

SDK 刻意不依赖 Retrofit、协程、依赖注入或 AndroidX。宿主应用负责线程、生命周期、UI 和更高层错误策略。

### 4.3 Android App

示例 App 是一个单页面参考实现，包含：

- Node URL；
- 可选 Token；
- Session；
- 输入框；
- 发现节点、同步记忆、调用 Node；
- 导入 GGUF、本地生成；
- 状态与输出区域。

所有网络和推理操作进入单线程 executor，UI 更新切回主线程。App 用于证明链路和展示 SDK，不是最终设计系统。

## 5. 桌面产品功能

### 5.1 启动与发现

```powershell
shufu serve --host 0.0.0.0 --allow-lan --token "replace-me"
```

启用 LAN 后，Discovery Responder 监听 UDP 7879。客户端发送固定字节串 `SHUFU_DISCOVER_V2`，节点返回：

- `service=shufu`；
- `node_id`；
- 节点名称；
- HTTP URL；
- `protocol_version=0.2`。

发现只解决“找到节点”，不证明节点身份。敏感环境应使用手工 URL、Token 和隔离网络。

### 5.2 增量同步

```powershell
shufu sync --url http://192.168.1.20:7878 --token replace-me --session project-a
```

`changes.seq` 是节点本地单调游标。消息、产物或 session 首次写入时记录变更。`after=N` 只返回序号大于 N 的相关对象。

当前同步原则：

1. 对象使用不可变 ID；
2. 导入使用 ID 幂等去重；
3. artifact 内容必须通过 SHA-256 校验；
4. cursor 只在对应源节点语境下有效；
5. 不覆盖同 ID 的本地已有对象；
6. 不自动解决“同 ID 不同内容”的恶意或损坏冲突。

## 6. Android 产品功能

### 6.1 远程模型调用

```kotlin
val client = ShuFuHttpClient(
    "http://192.168.1.20:7878",
    token = "replace-me",
)
val result = client.invoke(
    "继续完善文档",
    sessionId = "project-a",
)
```

连接超时默认 5 秒，读取超时默认 120 秒。非 2xx 响应抛出带状态码的 `ShuFuHttpException`。SDK 不自动重试，避免重复调用产生不可见成本或副作用。

### 6.2 Android 记忆

Android 数据位于 App 私有空间：

- `shufu-memory-v2.sqlite3` 保存结构化数据；
- `files/shufu/artifacts/` 按 SHA-256 保存产物内容；
- 每个安装实例生成稳定 `node_id`；
- `changes` 表提供本地 cursor；
- 数据随 App 卸载清除，除非宿主另行备份。

### 6.3 同步流程

```text
Android export full bundle
          │
          ├── POST /shufu/v2/sync/push ──> Desktop import
          │
read saved cursor for this remote node
          │
          └── GET /shufu/v2/sync/pull?after=N
                                      │
                              Android import + save cursor
```

v0.2 每次 push 本地完整 Bundle，pull 使用远端 cursor 增量。这一策略优先保证简单、可恢复和可诊断；重复内容通过 ID 去重。v0.3 可增加“远端已确认本地 cursor”，减少完整推送。

### 6.4 Android 本地 GGUF

`ModelManager` 提供两种模型进入方式：

1. 通过系统文档选择器导入；
2. 通过 HTTP(S) URL 下载，可指定期望 SHA-256。

文件先写入 `.part`，完成和校验后再替换目标。文件名必须是单一 `.gguf` 基础名，避免目录穿越。

`LlamaCppRuntime` 的 v0.2 参数：

- llama.cpp 固定版本 `b9722`；
- Android NDK r27c；
- 仅 `arm64-v8a`；
- CPU 推理，`n_gpu_layers=0`；
- 贪心采样；
- 每次生成新建 context；
- `max_tokens` 被限制为 1–2048；
- 模型句柄使用 mutex 保护，不允许并发生成破坏状态。

模型不打包在 APK 中。实际可运行模型大小取决于设备 RAM、系统占用、模型量化和上下文长度。

## 7. Protocol v0.2

### 7.1 兼容端点

所有 `/shufu/v1/*` 端点继续保留。特别是 `/shufu/v1/memory/export` 必须返回 Schema 1，而不是 Schema 2。

### 7.2 新端点

| 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- |
| GET | `/shufu/v2/sync/pull` | `after`、可选 `session_id` | Schema 2 Bundle |
| POST | `/shufu/v2/sync/push` | Schema 1 或 2 Bundle | 导入计数与当前 cursor |

Schema 2 在 Schema 1 基础上增加：

- `bundle_id`：本次导出的唯一 ID；
- `source_node_id`：源节点身份；
- `after`：本次查询起始游标；
- `cursor`：导出范围当前最新游标。

完整约定见 [protocol-v0.2.md](protocol-v0.2.md)。

## 8. 数据一致性与兼容策略

| 情况 | 处理方式 |
| --- | --- |
| 重复 session/message/artifact | 通过 ID 忽略重复插入 |
| artifact 内容损坏 | SHA-256 不一致时拒绝整个导入 |
| v0.1 Bundle 导入 v0.2 | 接受 Schema 1 |
| v0.1 客户端从 v0.2 导出 | v1 端点强制生成 Schema 1 |
| Android 拉取中断 | cursor 只在成功导入后保存，下次重新拉取 |
| 节点重新安装 | 新 `node_id`，Android 为其建立独立 cursor |
| 同一 ID 不同内容 | 保留先到对象；当前不自动覆盖或合并 |

## 9. 安全与隐私

### 9.1 默认安全边界

- 桌面 Node 默认绑定回环地址；
- 非回环监听需要 `--allow-lan`；
- 可配置 Bearer Token；
- Android 数据存储在 App 私有目录；
- 模型必须由用户选择或显式提供 URL；
- 下载模型可进行 SHA-256 校验；
- ToolRegistry 的副作用工具必须显式许可。

### 9.2 已知安全限制

- 局域网 HTTP 和 UDP 发现均未加密；
- UDP 响应可被伪造；
- 静态 Token 没有过期、轮换、用户隔离；
- Bundle 未签名且可能包含敏感原文；
- Android 示例 App 会显示并使用首个发现节点；
- 下载模型的真实性只有在提供可信期望哈希时才可验证；
- 本版本不适合直接暴露到公网。

## 10. 轻量 Agent 规划

v0.2 仍只提供 Agent 安全底座：ToolRegistry、工具描述、副作用标记和硬执行上限。它没有接入 Android UI，也没有默认自主循环。

后续分支引入 Agent Lite 时，应满足：

1. 工具白名单由宿主注册；
2. 文件、网络、设备控制分别授权；
3. 副作用操作在执行前展示给用户；
4. 每轮有步骤、时间和 token 上限；
5. 工具输入输出写入可审计日志；
6. 用户可随时取消；
7. 文档产物默认作为数据，不自动提升为系统指令。

## 11. 构建、安装与发布物

### 11.1 桌面

```powershell
python -m pip install -e .
shufu doctor
```

### 11.2 Android

构建环境：JDK 17、Android SDK 35、Build Tools 35.0.0、NDK `27.2.12479018`、CMake 3.22.1。

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

发布物：

- `outputs/ShuFu-v0.2-android-arm64.apk`；
- `outputs/ShuFu-v0.2-sdk-arm64.aar`；
- `outputs/SHA256SUMS-v0.2.txt`；
- `outputs/v0.2-verification.json`。

APK 使用 Android Debug 证书，仅用于开发验证和侧载测试；正式发布必须配置独立签名、版本升级策略和供应链流程。

## 12. 可观测性与错误语义

- `/health` 用于存活检查；
- `/capabilities` 用于功能协商，不应仅靠版本字符串猜测能力；
- HTTP 非法请求返回 JSON `INVALID_REQUEST`；
- 未授权返回 401 `AUTH_REQUIRED`；
- artifact 不存在返回 404 `ARTIFACT_NOT_FOUND`；
- Android Client 保留 HTTP 状态码和响应正文；
- JNI 将 C++ 异常转换为 Java `IllegalStateException`；
- 当前没有结构化日志、指标、链路追踪和崩溃上报。

## 13. 验收标准

| 编号 | 验收项 | 判定方式 |
| --- | --- | --- |
| V02-A01 | 桌面 v0.2 能力协商 | capabilities 返回 0.1/0.2、同步和 Agent 能力 |
| V02-A02 | UDP 发现可用 | 客户端发现测试节点并读取 URL/ID |
| V02-A03 | 增量拉取正确 | cursor 后仅包含新增对象 |
| V02-A04 | 幂等推送正确 | 重复导入不产生重复记录 |
| V02-A05 | v0.1 兼容 | v1 invoke、Schema 1 导入导出通过 |
| V02-A06 | Android Client 互操作 | Kotlin SDK 调用真实 Python Node |
| V02-A07 | Android SDK 可构建 | Debug AAR 构建成功 |
| V02-A08 | Android App 可构建 | ARM64 Debug APK 构建成功 |
| V02-A09 | JNI 可编译和导出 | ARM64 native library 含四个 JNI 入口 |
| V02-A10 | 发布物完整 | APK/AAR SHA-256 与清单一致 |

对应测试范围、环境和未覆盖项见 [test-report-v0.2.md](test-report-v0.2.md)。

## 14. 已知限制与后续路线

- 尚未进行物理 Android 设备安装、性能、峰值内存和长时间稳定性测试；
- Android 仅支持 ARM64；
- 本地推理不支持流式 token、温度、top-p 和聊天模板；
- 同步 push 仍是完整 Bundle，大产物效率有限；
- 无 TLS、设备配对和冲突可视化；
- 无后台同步和断点下载；
- ESP32 尚未交付。

建议 v0.3 优先完成 ESP-IDF Client、流式调用、产物分块/引用和双游标同步；Agent Lite 作为独立实验分支推进，不阻塞核心跨平台调用层。

