# ShuFu ESP32 SDK v0.3

该目录提供 ESP-IDF 组件。ESP32 只通过 HTTP 调用 Windows/Linux 上的 ShuFu Node，**不下载模型、不加载 GGUF，也不在本地运行 LLM**。

## 能力

- `shufu_invoke_stream()`：消费 `/shufu/v3/invoke/stream` NDJSON 事件；
- `shufu_stream_parser_t`：固定 1024 字节行缓冲、无堆分配的流分帧器；
- `shufu_tool_registry_t`：最多 16 个由固件预注册的函数；
- GPIO 写入等副作用工具，每次执行都要求 `allow_side_effect=true`；
- 不存在 Shell、动态库、脚本解释器或模型生成代码执行入口。

## 集成

将 `components/shufu` 复制到 ESP-IDF 项目的 `components/`，或在项目的 `idf_component.yml` 中使用本地 `path` 依赖。应用负责 Wi-Fi 生命周期、Node URL/Token 的安全存储、JSON 参数校验和用户确认界面。

```c
shufu_client_config_t config = {
    .node_url = "http://192.168.1.20:7878",
    .bearer_token = "replace-me",
    .timeout_ms = 120000,
};
shufu_invoke_stream(&config, "assistant", "device-1", "当前状态？", on_event, NULL);
```

示例工程位于 `examples/node_client`。本仓库当前 CI/开发机没有 ESP-IDF 工具链与真实开发板，因此该示例不是硬件验证证明；可移植的流解析器和工具注册表会单独做 C 语法与行为测试。
