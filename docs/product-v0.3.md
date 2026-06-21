# ShuFu（鼠符）v0.3 产品文档

> 产品主题：让 ESP32 获得模型能力，而不是让 ESP32 承担模型  
> 文档状态：当前参考实现  
> 更新时间：2026-06-21

## 1. 产品定位

ShuFu v0.3 把 v0.2 的 Windows/Linux + Android 链路延伸到 ESP32。用户在 PC 上安装并启动一个 ShuFu Node，ESP32 固件只需集成小型 SDK，就能以相同 session 调用模型、逐段接收结果，并把明确批准的结果映射到 GPIO 或传感器函数。

```text
模型/GGUF/API -> Windows/Linux Node -> 局域网 -> ESP32
                            \-> Android
```

鼠符的“赋予生命”在本版本中有清楚边界：智能来自 Node，设备动作来自固件白名单，模型不会变成任意代码执行器。

## 2. 目标用户

- 制作 ESP32 语音盒、桌面机器人、状态屏和传感器助手的开发者；
- 需要在 PC、Android 与微控制器之间延续同一上下文的开源项目；
- 想接入云模型或本地 GGUF，但不愿在每种硬件重复实现协议、记忆和安全边界的团队。

## 3. 核心体验

### 3.1 PC 启动 Node

```powershell
shufu serve --host 0.0.0.0 --allow-lan --token "replace-me"
```

Node 仍默认只监听回环地址。只有用户显式开启 LAN 才允许 ESP32 接入；家庭或实验室网络也建议配置 Token。

### 3.2 CLI 验证流式链路

```powershell
shufu invoke "设备状态" `
  --url http://192.168.1.20:7878 `
  --token replace-me `
  --session esp32-lab `
  --stream
```

CLI 逐段打印 delta，Node 保存完整 user/assistant 消息，因此相同 session 可继续对话。

### 3.3 ESP-IDF 集成

将 `esp32/components/shufu` 作为本地组件依赖，在 Wi-Fi 连接后调用：

```c
shufu_client_config_t config = {
    .node_url = "http://192.168.1.20:7878",
    .bearer_token = "replace-me",
    .timeout_ms = 120000,
    .stream_chunk_size = 64,
};
shufu_invoke_stream(
    &config, "assistant", "desk-device", "给我一句状态提示", on_event, NULL
);
```

SDK 不接管 Wi-Fi、不保存 Token、不启动后台任务，避免侵入宿主的 FreeRTOS 生命周期。

## 4. 功能清单

| 功能 | 用户价值 | 明确边界 |
| --- | --- | --- |
| NDJSON 流调用 | 低内存设备无需缓存完整响应 | 当前 Node 的首 delta 仍受阻塞 Runtime 延迟影响 |
| Schema 3 分块 | 大产物逐块校验、失败可定位 | JSON/Base64 有编码开销 |
| 同源外部引用 | 元数据与内容分离、支持 Range | 不自动访问任意 URL |
| 双游标同步 | 不再每次完整推送，方向独立恢复 | 不是云端实时同步服务 |
| ESP32 固件工具 | 连接 GPIO/传感器 | 只运行预注册 C 函数 |
| 副作用逐次许可 | 防止模型直接控制执行器 | 宿主必须实现真实确认 UI/策略 |
| v0.1/v0.2 兼容 | 旧 CLI、Android 与 Bundle 继续使用 | 新能力必须显式协商 |

## 5. 工具接入原则

传感器读取示例可注册为 `sensor.read_temperature`，GPIO 写入可注册为 `gpio.set_led`。工具处理函数编译在固件内，参数是待校验 JSON 数据。

完整动作路径应为：

```text
模型建议工具调用
  -> 固件校验工具名和参数
  -> 若有副作用，向用户/宿主策略请求本次许可
  -> shufu_tool_execute(..., allow_side_effect=true)
  -> 结果作为数据返回或展示
```

默认拒绝是正常产品行为。不得为了“更智能”而缓存永久授权或加入通用 Shell。

## 6. 同步操作

v0.3 CLI 默认使用双游标：

```powershell
shufu sync --url http://192.168.1.20:7878 --token replace-me
```

需要连接旧 v0.2 Node 时：

```powershell
shufu sync --protocol v2 --url http://192.168.1.20:7878
```

可选择 `--artifact-mode auto|inline|chunks|external`。external 仅在客户端可以继续访问同一 Node 时使用；离线迁移应选择 chunks 或 inline。

## 7. 数据与安全

- 会话、消息和产物默认存储在 Node/客户端本地；
- Token 是共享密钥，不等同于设备身份、用户账号或端到端加密；
- 局域网 HTTP 可能被监听，敏感环境应使用隔离网络或外部 TLS 反向代理；
- 外部产物引用只允许解析到当前 Node；
- 每块及完整内容都做 SHA-256 校验；
- 发现、模型输出、artifact 文本均不自动转为可信指令。

## 8. 版本完成定义

v0.3 的软件参考实现已覆盖：Python 流协议、CLI、Schema 3、双游标、外部引用/Range、ESP-IDF 组件结构、受限 C 工具注册表和自动化测试。

正式宣称“ESP32 可发布”之前仍必须在目标芯片上完成：

1. ESP-IDF 5.1+ 完整构建；
2. 至少 ESP32、ESP32-S3 的 Wi-Fi 调用；
3. 长响应、断网、重连、低堆内存压测；
4. TLS 代理或受信 LAN 部署验证；
5. GPIO/传感器真机副作用确认流程；
6. 功耗、看门狗与任务栈评估。

这些未完成项不影响协议参考实现的可测试性，但决定硬件发行质量，不能用桌面语法编译代替。

## 9. v0.4 接口

v0.3 的固件白名单和逐次许可为 v0.4 Agent Lite 提供底座。v0.4 可以规划有限步骤，但仍不得绕过 v0.3 的工具注册、参数校验、副作用确认和最大资源限制。
