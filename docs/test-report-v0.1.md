# ShuFu（鼠符）v0.1 测试报告

> 报告日期：2026-06-21  
> 测试对象：当前 v0.2 源码中的 v0.1 冻结协议与兼容行为  
> 测试平台：Windows 10.0.26200 x64，Python 3.12.13  
> 结论：自动化兼容测试与 CLI 主路径通过；真实 GGUF、外部模型服务和 Linux 实机不在本轮覆盖范围

## 1. 测试目的

v0.1 已不作为单独源码分支存在，当前仓库版本为 0.2.0。因此本报告验证的是：

1. v0.1 公共 HTTP 契约仍可由当前节点提供；
2. Schema 1 记忆包仍可导入、导出和迁移；
3. v0.1 的本地 CLI、会话、产物、权限和工具边界没有被 v0.2 破坏；
4. 测试结论不把 v0.2 新功能冒充成 v0.1 原始交付。

产品范围和验收定义见 [product-v0.1.md](product-v0.1.md)，协议字段见 [protocol-v0.1.md](protocol-v0.1.md)。

## 2. 测试环境

| 项目 | 值 |
| --- | --- |
| 仓库 | `D:\bookPro` |
| 软件包版本 | `0.2.0`（维护 v0.1 兼容） |
| 操作系统 | Microsoft Windows NT 10.0.26200.0 x64 |
| Python | 3.12.13 |
| 测试框架 | Python 标准库 `unittest` |
| 数据库 | Python 标准库 SQLite |
| 网络 | 本机随机端口、回环地址 |
| 模型 Runtime | 确定性 `echo` |
| 外部服务 | 无 |

测试均使用临时目录和随机端口，结束后清理，不读取用户真实 ShuFu 会话。

## 3. 测试策略

### 3.1 专项兼容测试

`tests/test_v01_compat.py` 将 v0.1 最重要的外部契约独立冻结，防止普通 v0.2 回归测试通过但旧客户端实际失效。

执行命令：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -p test_v01_compat.py -v
```

### 3.2 全量回归

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

全量回归同时覆盖 v0.2 代码，目的在于确认兼容逻辑没有通过破坏新版本来实现。

### 3.3 CLI 主路径冒烟

在隔离临时目录执行：

1. `shufu run`；
2. `--save-output` 保存 Markdown；
3. `memory export`；
4. 在另一空数据目录 `memory import`；
5. `memory list` 核对 session 与 artifact。

## 4. 专项测试结果

| 编号 | 测试用例 | 覆盖行为 | 结果 |
| --- | --- | --- | --- |
| V01-T01 | `test_v1_invoke_contract_and_session_memory` | `/shufu/v1/invoke` 字段、模型、session、输出和连续调用 | 通过 |
| V01-T02 | `test_v1_memory_export_stays_schema_one` | v1 导出固定 `schema_version=1`，不泄露 v0.2 cursor | 通过 |
| V01-T03 | `test_schema_one_bundle_round_trip` | Schema 1 导出后在新 Store 导入并恢复消息 | 通过 |
| V01-T04 | `test_v1_capabilities_advertise_v01_support` | capabilities 明确公布协议 0.1 和 Bundle Schema 1 | 通过 |

汇总：**4 个测试，4 通过，0 失败，0 错误，0 跳过；耗时 2.208 秒。**

## 5. v0.1 相关回归结果

全量 Python 测试共 **19 个，19 通过，0 失败，0 错误，0 跳过；耗时 5.288 秒**。其中与 v0.1 产品能力直接相关的覆盖包括：

| 能力域 | 相关测试证据 |
| --- | --- |
| 会话连续性 | `test_second_turn_uses_same_session_memory` |
| 空输入校验 | `test_empty_input_is_rejected` |
| session、artifact 与 Bundle | `test_session_history_and_portable_artifact_bundle` |
| 幂等导入 | `test_duplicate_import_is_idempotent` |
| 文件导出导入 | `test_export_file_round_trip` |
| 旧 Schema 1 导入 | `test_v1_legacy_bundle_remains_importable` |
| HTTP invoke 与 capabilities | `test_invoke_and_capabilities` |
| Token 边界 | `test_token_is_required_when_configured` |
| artifact 上传和导出 | `test_artifact_upload_and_export` |
| LAN 显式许可 | `test_lan_requires_explicit_enablement_boundary` |
| 工具副作用许可 | `test_tool_side_effect_requires_explicit_approval` |
| Agent 硬限制 | `test_agent_limits_are_hard_bounded` |

`compileall` 同时通过，未发现 Python 语法或模块编译错误。

## 6. CLI 冒烟结果

| 步骤 | 实际结果 |
| --- | --- |
| 本地调用 | 返回 `ShuFu[assistant]: v0.1 report smoke` |
| 保存产物 | Markdown 文件成功写入并登记 artifact ID |
| 导出 | 记忆 JSON 成功生成 |
| 导入空 Store | 导入 1 session、2 messages、1 artifact |
| 列表核对 | session ID、文件名、MIME、SHA-256、大小均存在 |

结论：**CLI 主路径通过。**

说明：当前 CLI 的默认导出格式随软件版本为 Schema 2；v0.1 的 Schema 1 兼容保证由 `/shufu/v1/memory/export` 和专项测试验证。旧客户端不应通过当前 v0.2 CLI 默认行为推断 v0.1 HTTP 格式。

## 7. 验收矩阵

| 验收编号 | 要求 | 证据 | 状态 |
| --- | --- | --- | --- |
| V01-A01 | 零模型依赖可运行 | CLI echo 冒烟 | 通过 |
| V01-A02 | 同 session 连续对话 | Node 与 v1 invoke 测试 | 通过 |
| V01-A03 | v1 HTTP 契约 | v0.1 专项 4 项 | 通过 |
| V01-A04 | Schema 1 可迁移 | Schema 1 round-trip | 通过 |
| V01-A05 | 重复导入幂等 | duplicate import 测试 | 通过 |
| V01-A06 | 默认网络边界 | LAN 与 Token 测试 | 通过 |
| V01-A07 | 副作用工具需许可 | ToolRegistry 测试 | 通过 |
| V01-A08 | 可配置真实模型 | 适配器代码与参数解析存在 | 部分验证 |

V01-A08 只验证配置和适配器结构。本轮没有提供真实 GGUF 文件或外部 OpenAI-compatible 服务，因此不对实际推理正确性、性能和供应商兼容性作结论。

## 8. 缺陷与观察项

### 8.1 本轮发现并修正

- 最初专项测试错误地期待响应包含 `usage`；v0.1 协议实际字段是 `model/session_id/output/created_at`。测试已按冻结协议修正。这是测试用例偏差，不是产品缺陷。

### 8.2 未关闭风险

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| Linux 未实机执行 | 中 | 代码仅用标准库，但本轮环境是 Windows |
| 真实 GGUF 未执行 | 中 | 需要合法模型文件及匹配硬件 |
| OpenAI-compatible 未联调 | 中 | 不同服务可能有响应差异 |
| Bundle 未签名/加密 | 中 | 不应通过不可信渠道传输敏感记忆 |
| 静态 Token 能力有限 | 中 | 不适合作为公网鉴权机制 |
| 大 Bundle 性能 | 低至中 | Base64 会增加体积，未做压力测试 |

## 9. 测试结论

v0.1 的核心本地调用、会话、产物、权限与 Agent 工具边界通过回归；v0.1 HTTP invoke 和 Schema 1 记忆兼容通过独立专项测试。当前 v0.2 可以继续作为 v0.1 客户端的兼容服务端。

发布判断：**可作为开源兼容基线发布和持续集成；若声明支持某个真实 GGUF、外部服务或 Linux 发行版，应先增加对应环境测试。**

