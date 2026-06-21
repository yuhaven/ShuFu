# ShuFu v0.4 测试报告

> 测试日期：2026-06-21  
> 工作目录：`D:\bookPro`  
> 结论：v0.4 Python 实现与 CLI 集成通过；远程 Agent HTTP、真实模型与嵌入式端到端尚未交付

## 1. 验证范围

本报告覆盖 Agent Lite、有界工具循环、逐次副作用审批、取消与审计、显式 artifact 上下文、可验证摘要记忆，以及 CLI、版本号和 capabilities 集成。v0.4 不提供任意代码执行、后台自治任务或远程 Agent HTTP 接口。

## 2. 最终结果

| 测试集 | 结果 | 耗时 |
| --- | ---: | ---: |
| v0.1 专项 | 4/4 | 2.177s |
| v0.3 专项 | 12/12 | 3.038s |
| v0.4 专项 | 23/23 | 0.702s |
| 全量 Python 回归 | 54/54 | 9.100s |
| Python `compileall` | 通过 | — |

执行方式：

```powershell
$env:PYTHONPATH = 'D:\bookPro\src'
$python = 'C:\Users\MLTZ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s tests -p 'test_v04*.py' -v
& $python -m unittest discover -s tests -v
& $python -m compileall -q src tests
```

## 3. 验收矩阵

| 验收项 | 自动化证据 | 状态 |
| --- | --- | --- |
| 严格动作协议 | planner 只接受无多余字段的 JSON `tool`/`final` 动作 | 通过 |
| 固定步骤和时间预算 | 步骤耗尽、planner 超时、只读工具超时均产生明确终态 | 通过 |
| 每次副作用单独审批 | 仅字面量 `True` 批准；非布尔值、拒绝和取消均不执行 | 通过 |
| 防参数篡改 | 审批与执行分别使用规范 JSON 深拷贝，嵌套参数不可 TOCTOU 篡改 | 通过 |
| 副作用终态一致性 | 已批准副作用同步收敛后才返回，避免终态后后台继续写入 | 通过 |
| 异常封装 | `BaseException` 也转换为失败结果并写入终态审计 | 通过 |
| 审计不可变与脱敏 | 审计详情返回副本；持久化 sink 脱敏 token、secret、content 等字段 | 通过 |
| Artifact 显式上下文 | 只有明确选择的同会话 artifact 可进入上下文，并验证 MIME、大小、UTF-8 与哈希 | 通过 |
| 摘要来源可信 | 摘要只能引用真实原文 ID，保存和读取时校验会话、角色及内容指纹 | 通过 |
| 上下文有界 | 限制摘要数量、单条长度、总长度并拒绝重复来源 | 通过 |
| CLI 集成 | 支持 `memory messages`、`summary add/list/show` 与本地 `agent`；副作用交互审批 | 通过 |
| 能力协商 | 最新版本 0.4，同时保留 v0.1–v0.3 协议兼容信息，明确 `http_transport=false` | 通过 |

## 4. 安全审计与修复

合并前专项审计发现并修复了以下问题：非布尔审批被视为允许、审批期间嵌套参数可变、副作用在超时终态后继续运行、伪造摘要来源、摘要上下文无界、`BaseException` 逃逸以及审计详情可被外部修改。相应负向测试已加入 v0.4 专项并纳入 54 项全量回归。

## 5. 已知边界

- v0.4 Agent 当前只通过本地 Python CLI 接入，不宣称提供 HTTP Agent transport。
- 尚未用真实 LLM 统计 planner 严格 JSON 的遵循率；非法格式会明确失败，不自动猜测修复。
- 已批准副作用不能被 Python 安全强杀，因此控制器等待 handler 收敛后再返回 `timed_out`；生产 handler 必须短小、幂等并配置自身 I/O 超时。
- 尚未完成 Android 审批 UI、ESP32 GPIO 实物、断电恢复和跨设备 Agent 端到端验证。
- 当前审计日志为本地脱敏 JSONL；加密、轮转和集中采集由部署层负责。

## 6. 发布判定

v0.4 可作为 **本地 Agent Lite 开发预览版** 发布。应明确标注“不含远程 Agent HTTP 和嵌入式 Agent 端到端”，不得宣传为通用自主智能体平台。
