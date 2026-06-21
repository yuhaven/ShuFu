# ShuFu v0.4 产品文档

## 1. 产品定位

ShuFu v0.4 让同一套跨平台模型调用层具备“小而安全”的行动能力：模型可以在有限步骤内读取宿主信息、请求一个预注册操作并给出结果；用户始终掌握文档是否进入上下文以及副作用是否发生。

一句话定义：**让模型能使用少量宿主能力，但绝不把设备控制权交给任意模型输出。**

## 2. 对路线图的交付

| 路线图条目 | v0.4 交付 |
| --- | --- |
| Agent Lite 循环 | 1–10 步、>0–300 秒预算、严格 JSON 动作 |
| 用户选择的产物注入 | 默认不加载；显式 ID、同 session、文本/大小/哈希校验 |
| 摘要记忆 | 独立数据库、原始来源 ID/哈希、默认无长期事实 |

v0.4 建立在 v0.1 的 `Runtime`、`ToolRegistry` 和记忆边界之上，不改变 v0.2 Android、本地 GGUF 或 v0.3 ESP32/流式调用的职责。

## 3. 典型用户体验

### 3.1 无副作用任务

用户输入“读取传感器并解释温度”。宿主只注册 `read_temperature`。Agent 最多执行规定步骤，读取结果后给出答案；只读工具达到步骤/时间上限则明确结束。

### 3.2 有副作用任务

用户输入“温度过高就打开风扇”。当 planner 请求 `set_fan` 时，UI 必须显示工具名、说明与参数。用户本次批准后才执行；同一 run 第二次请求仍会再次询问。拒绝不会调用 handler，并在审计中记录。

### 3.3 参考文档

用户勾选 `device-manual.md` 后发起 run。系统验证文档并以不可信 user data 交给模型。没有勾选的同 session 文档也不会进入 prompt；文档中的“忽略规则”等文字不能提升为系统权限。

### 3.4 会话摘要

用户或宿主显式生成摘要时，必须提交当前 session 中真实存在的原始消息 ID。摘要保存在独立库并记录来源角色、时间与哈希；每次读取或进入上下文前都会重新核对原始来源。原始消息不删除、不覆盖。默认不能把“可能、推测、当前状态”自动写成长期事实。

## 4. 功能清单

### 4.1 Agent Lite

- 复用宿主 `ToolRegistry`；
- strict JSON planner；
- 工具/最终答复两种动作；
- 全局步骤和时间上限；
- 工具输出长度限制；
- 用户取消；
- 完整运行内审计事件；
- planner、工具和审批异常均转为明确状态。

### 4.2 工具安全

- 工具只能由宿主代码预注册；
- 不支持模型注册/下载工具；
- 不提供 Shell、动态代码或通用文件执行器；
- 副作用标记来自宿主；
- 每次副作用独立审批；
- 可选工具取消回调。
- 审批只接受布尔值 `True`，字符串或对象一律视为拒绝；
- 审批和执行使用深拷贝后的 canonical JSON 参数快照；
- 已批准的副作用在当前控制流完成后才返回终态。

### 4.3 上下文安全

- artifact 与 summary 均需显式选择；
- 原始消息、摘要、artifact 在数据模型中分开；
- artifact 类型、大小、session、UTF-8、哈希验证；
- artifact/summary 只以 user role 数据块进入 planner；
- task 始终作为最后一条 user message。

### 4.4 摘要记忆

- 独立 SQLite；
- 来源 ID/role/time/content SHA-256；
- 创建、读取和进入上下文时从原始 MemoryStore 复核来源；
- 摘要正文和来源数量上限；
- 默认禁止长期事实；
- 允许事实时必须由宿主显式策略开启。

## 5. 默认配置

| 配置 | 默认 | 硬范围/说明 |
| --- | --- | --- |
| Agent steps | 3 | 1–10 |
| Agent time budget | 10 秒 | >0–300 秒；planner/只读工具严格截止，已批准副作用安全收敛优先 |
| tool observation | 8192 字符 | 128–65536 |
| selected artifacts | 0 | 最多 4 |
| artifact bytes | 64 KiB/个 | 策略最大 1 MiB/个 |
| artifact total | 128 KiB | 策略最大 4 MiB |
| summary chars | 4096 | 最大 65536 |
| summary sources | 100 | 最大 1000 |
| long-term fact count/size | 32 条 / 512 字符 | 仅显式开启后适用 |
| long-term facts | 关闭 | 宿主显式开启 |

## 6. Python 宿主示例

```python
from shufu.agent import AgentLimits, Tool, ToolRegistry
from shufu.agent_lite import AgentLite, RuntimePlanner
from shufu.context import ContextBuilder
from shufu.summary import SummaryStore

registry = ToolRegistry()
registry.register(Tool("read_temperature", "Read temperature", read_temperature))
registry.register(Tool("set_fan", "Set fan state", set_fan, side_effect=True))

summaries = SummaryStore(home / "derived", memory)
context = ContextBuilder(memory, summaries=summaries).build(
    "room-a",
    "检查温度；必要时建议打开风扇",
    selected_artifact_ids=user_selected_ids,
    selected_summary_ids=user_selected_summary_ids,
)
agent = AgentLite(
    RuntimePlanner(runtime, "assistant"),
    registry,
    limits=AgentLimits(max_steps=3, timeout_seconds=10),
    approval_handler=show_one_time_approval,
    audit_sink=store_redacted_audit,
)
result = agent.run(context)
```

示例中的 handler 和审批 UI 由宿主提供。CLI 已内置脱敏 JSONL 审计、`list_artifacts` 只读工具和逐次审批的 `save_text_artifact`；不要注册接受任意命令字符串的“万能工具”。

命令行入口：

```powershell
shufu memory messages --session project-a
shufu summary add "会话摘要" --session project-a --source-message-id MESSAGE_ID
shufu agent "继续任务" --session project-a --artifact-id ARTIFACT_ID `
  --summary-id SUMMARY_ID --runtime openai --base-url http://127.0.0.1:11434
```

Node capabilities 会公布本地 `agent_lite`、显式 artifact 上下文和独立 summary memory；远程 Agent HTTP 端点尚未开放，因此明确返回 `http_transport=false`。

## 7. 非目标

- 多智能体编排和长期后台任务；
- 任意 Shell、Python、JavaScript 执行；
- 自动安装插件或从网络加载 handler；
- 自动遍历所有 artifact/RAG 索引；
- 自动创建长期人物画像或事实库；
- 账号、RBAC、云控制台和计费；
- 用提示词替代操作系统权限、鉴权或物理安全。

## 8. 平台策略

- Windows/Linux：运行 Python Agent Lite 参考控制器和模型 runtime；
- Android：由 AAR/UI 负责用户选择、批准和取消，可调用桌面 Node；v0.4 核心不要求手机运行 Python；
- ESP32：只暴露固件预注册的 GPIO/传感器工具，设备不接受远程代码；步骤控制可放在桌面/Android 宿主；
- 华为、小米闭源生态继续不在当前投入范围。

## 9. 风险与控制

| 风险 | 确定性控制 | 剩余风险 |
| --- | --- | --- |
| 模型请求危险操作 | 宿主白名单 + 每次副作用批准 | 用户可能误批准 |
| 模型生成代码 | 只解析 tool/final JSON，不存在执行器 | 宿主不应注册万能命令工具 |
| 文档提示注入 | 显式选择、user-role 数据、固定 system policy | 模型仍可能受内容影响，故高风险动作继续审批 |
| 无限循环 | 1–10 步硬限制 | 已批准的同步副作用可能超过时间预算才安全收敛 |
| 阻塞工具 | planner/只读工具 deadline；副作用同步执行 | 宿主仍必须给设备/网络 handler 配置内部超时 |
| 错误摘要污染 | 原文分离、真实来源复验、默认无事实 | 摘要正文仍可能不准确，应允许用户查看原文 |
| 审计泄密 | 有界事件、不可变快照、CLI 敏感字段脱敏 | 自定义宿主 sink 仍需定义自身策略 |

## 10. 验收与发布门槛

v0.4 核心发布必须满足：

1. `tests/test_v04_agent.py`、`test_v04_context_summary.py` 和 `test_v04_cli.py` 全部通过；
2. 既有 `test_agent_and_cli.py` 边界测试通过；
3. 没有 `eval`、`exec`、`subprocess` 或模型输出动态 import 路径；
4. 副作用逐次审批、拒绝不执行、取消/超时可审计；
5. 未选择 artifact 时 prompt 中无 artifact；
6. 摘要与 raw memory 分库且来源可查；
7. CLI 本地入口、摘要命令和脱敏审计通过测试；HTTP 未实现时 capabilities 必须报告 `http_transport=false`。

当前核心测试证据见 [test-report-v0.4.md](test-report-v0.4.md)，实现原理见 [v0.4-design.md](v0.4-design.md)，数据契约见 [protocol-v0.4.md](protocol-v0.4.md)。
