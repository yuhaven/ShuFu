# ShuFu v0.3 测试报告

> 测试日期：2026-06-21  
> 工作目录：`D:\bookPro`  
> 结论：协议、Python 参考实现和 ESP32 C 静态验证通过；ESP-IDF 完整构建与真机未验证

## 1. 测试范围

本报告验证流式调用、Schema 3 产物、双游标同步和 ESP32 SDK 的静态安全边界，并回归 v0.1/v0.2。Android NDK Clang 仅用于严格 C 语法检查，不等同于 ESP-IDF 工具链或硬件验证。

## 2. 自动化结果

| 测试集 | 结果 | 说明 |
| --- | ---: | --- |
| v0.3 Python 专项 | 12/12 | 流式、Schema 3、Range、双游标、ESP32 静态边界 |
| v0.1 Python 专项 | 4/4 | 旧版兼容回归 |
| 最终集成全量 Python | 54/54 | 包含 v0.1–v0.4 |
| ESP32 C 严格语法 | 通过 | `-std=c11 -Wall -Wextra -Werror -fsyntax-only` |

Python 命令：

```powershell
$env:PYTHONPATH = 'D:\bookPro\src'
$python = 'C:\Users\MLTZ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s tests -p 'test_v03*.py' -v
& $python -m unittest discover -s tests -v
```

C 静态验证文件：`shufu_stream.c`、`shufu_tools.c`、`shufu_client.c` 和 `portable_test.c`。轻量 ESP/cJSON stub 只补足声明；验证通过仅说明 C11 类型与警告门禁通过。

## 3. 验收矩阵

| 需求 | 证据 | 状态 |
| --- | --- | --- |
| NDJSON 流式调用 | `start/delta/done` 顺序、Unicode 分块、连续 sequence、CLI stream | 通过 |
| Schema 3 分块产物 | inline/chunks round-trip、块哈希与总哈希损坏拒绝 | 通过 |
| 外部引用 | 默认拒绝；显式同源 resolver、大小/哈希校验和 HTTP Range 206 | 通过 |
| 双游标同步 | pushed/pulled cursor 单调推进、双向 exchange、来源回声排除 | 通过 |
| v0.1/v0.2 兼容 | 旧端点与 Schema 1/2 契约保留 | 通过 |
| ESP32 调用边界 | SDK 只调用 Node，不含本地 LLM/GGUF 入口 | 静态通过 |
| ESP32 工具安全 | 固定函数指针白名单、逐次副作用许可、无动态执行原语 | 静态通过 |
| 固定内存流解析 | 固定容量、无动态分配、超长 NDJSON 明确失败 | 静态通过 |
| ESP-IDF 完整构建 | 当前环境未安装 ESP-IDF | 未覆盖 |
| ESP32 真机运行 | 当前无开发板 | 未覆盖 |

## 4. 已知风险

- 当前 Python Runtime 是“生成完成后分块发送”，还不是模型 token 首字节流。
- ESP32 默认 NDJSON 单行上限为 1024 字节，Node 端 delta 必须保持小块。
- ESP-IDF HTTP 回调分片、chunked transfer、Wi-Fi 重连、任务栈、看门狗和功耗需真机验证。
- LAN HTTP/静态 Token 不适合不可信网络；生产部署需由宿主提供 TLS 或可信隧道。
- external 引用依赖源 Node 可用；离线迁移应使用 chunks。
- 示例 GPIO handler 只展示边界，生产代码必须按 JSON Schema 严格解析参数。

## 5. 发布判定

v0.3 可作为 **协议与 ESP32 SDK 开发预览版** 发布，不应标注为“ESP32 真机稳定版”。硬件稳定标签需要 ESP-IDF 5.1+ 构建矩阵、ESP32/ESP32-S3 真机、长流压力、断网恢复和副作用确认测试。
