# ShuFu 开发日志

本文记录跨版本开发的事实、决策、测试证据与风险。它不替代产品文档、协议或
测试报告；未获得源码和测试证据支持的内容必须标为“计划”“进行中”或“未验证”。

## 1. 记录规则

每次合并或发布至少记录：

1. 日期、版本/开发通道与变更范围；
2. 对应产品规划或验收编号；
3. 影响的平台、协议、数据格式和兼容性；
4. 实际执行的测试、环境、结果和跳过项；
5. 新增风险、未关闭风险与回滚方法；
6. 关联的提交、PR、Issue、发布物和 SHA-256（GitHub 启用后补录）。

“构建成功”不能替代真机测试，“测试未失败”不能包含被跳过的关键用例，开发
分支上的规划条目也不能提前写成发布能力。

## 2. 产品边界快照

- 产品只解决一个问题：让不同平台和硬件以统一、极简的方式调用或本地运行大模型。
- 当前优先平台：Windows/Linux PC、Android、ESP32。
- 华为、小米等闭源设备生态暂不投入适配。
- 当前只做开源产品与社区生态，不以商业化为版本验收目标。
- Agent 能力保持轻量、受限、可审计；宿主只执行预注册工具，不执行模型生成的任意代码。

## 3. 版本状态总览

| 版本 | 状态 | 核心范围 | 权威证据 |
| --- | --- | --- | --- |
| v0.1 | 冻结兼容基线 | 桌面 CLI/Node、Schema 1、基础记忆、Agent 工具边界 | `docs/test-report-v0.1.md`、`outputs/v0.1-verification.json` |
| v0.2 | 开源技术预览验证完成 | Android SDK/App、本地 GGUF 接入、发现、Schema 2 增量同步 | `docs/test-report-v0.2.md`、`outputs/v0.2-verification.json` |
| v0.3 | 协议与 ESP32 SDK 开发预览完成 | 流式线路、Schema 3、双游标、ESP-IDF 组件与受限设备工具 | `docs/test-report-v0.3.md`、`outputs/v0.3-verification.json` |
| v0.4 | 本地 Agent Lite 开发预览完成 | 有界循环、显式产物上下文、可验证摘要与审计 | `docs/test-report-v0.4.md`、`outputs/v0.4-verification.json` |

## 4. 决策记录

### D-001：能力协商优于平台特判

- 决策：客户端读取 capabilities，再决定调用、同步、流式或 Agent 能力。
- 原因：硬编码“Android/ESP32/Windows”会让协议随平台组合膨胀。
- 约束：新增能力必须可发现；未知能力应可忽略；不能只依赖版本字符串。

### D-002：冻结 v0.1 兼容面

- 决策：继续保留 `/shufu/v1/*` 与 Bundle Schema 1。
- 原因：允许旧客户端与受限设备逐步升级。
- 验证：`tests/test_v01_compat.py` 4 项专项测试。

### D-003：跨设备记忆使用不可变对象与幂等导入

- 决策：session、message、artifact 保持稳定 ID；重复导入不生成副本。
- 原因：离线设备和不可靠网络需要重试，而不能依赖一次性事务。
- 当前限制：大产物、弱网、双端游标与冲突可视化仍需演进。

### D-004：Agent Lite 不进入任意执行边界

- 决策：模型只能选择宿主预注册工具；副作用工具要求许可，并受步数和超时限制。
- 原因：这能保留轻量 Agent 价值，同时避免把跨平台调用层变成不受控执行器。
- v0.4 门槛：确定性循环、授权拒绝、超时、步数上限和审计记录已有专项测试；远程 HTTP 与硬件端到端仍不在本开发预览完成范围内。

### D-005：v0.3 核心适配与 v0.4 Agent 独立验收

- 决策：两条开发通道可以并行，但各自维护范围、测试和发布门槛。
- 原因：Agent 实验不能阻塞 ESP32/流式调用这一核心跨平台路径，也不能借核心路径的测试结果证明自身完成。

## 5. 测试证据基线

### v0.1（2026-06-21）

- 测试实现版本：0.2.0；兼容目标：0.1。
- 专项兼容：4/4 通过；完整 Python 回归：19/19 通过。
- CLI：调用、产物保存、Memory export/import 通过。
- 未覆盖：Linux 主机、真实 GGUF、外部 OpenAI-compatible 服务。

### v0.2（2026-06-21）

- Python 19/19；v0.1 兼容 4/4；compileall 与 CLI 冒烟通过。
- Android JVM/互操作 4/4，无跳过；Debug APK/AAR 与 ARM64 JNI 构建通过。
- Release Lint：0 错误、4 警告。
- 未覆盖：物理 Android 设备、真实 GGUF 推理、Release 签名。
- 发布判断：开源技术预览通过；稳定 Android 版仍为有条件状态。

### v0.3（2026-06-21）

- 发布判断：协议与 ESP32 SDK 开发预览完成，不是 ESP32 真机稳定版。
- v0.3 专项 12/12；冻结的 v0.1 兼容 4/4；最终集成全量 Python 54/54；`compileall` 通过。
- NDJSON 流式线路、Schema 3 inline/chunks/external、HTTP Range 和双游标交换通过参考实现测试。
- ESP32 C 使用 Android NDK r27c Clang 及 `-std=c11 -Wall -Wextra -Werror -fsyntax-only` 严格语法检查通过。
- Android 离线 Gradle 共处理 137 tasks，构建、单元测试和 lint 成功。
- 未覆盖：ESP-IDF 完整组件构建、ESP32/ESP32-S3 真机、Wi-Fi/长流/功耗/GPIO 副作用测试。
- 传输边界：当前 Python Runtime 完整生成后再分块发送，不宣称 token 首字节流式。

### v0.4（2026-06-21）

- 发布判断：本地 Agent Lite 开发预览完成，不是通用自主智能体平台。
- v0.4 专项 23/23；v0.3 专项 12/12；v0.1 兼容 4/4；全量 Python 54/54；`compileall` 通过。
- Android 离线 Gradle 共处理 137 tasks，构建、单元测试和 lint 成功。
- 本地 CLI、有界循环、逐次审批、显式 artifact 上下文、可验证摘要和脱敏审计通过。
- 明确未交付：远程 Agent HTTP transport、真实 LLM planner 矩阵、Android 审批 UI 与 ESP32 Agent/GPIO 硬件端到端。

#### v0.4 安全审计修复

| 发现 | 修复与验证 |
| --- | --- |
| 非布尔审批被当作允许 | 仅接受字面量 `True`；其他值均拒绝且不执行 |
| 审批期间嵌套参数可能被 TOCTOU 篡改 | 审批和执行分别使用规范 JSON 深拷贝 |
| 副作用可能在超时终态后继续写入 | 已批准同步副作用等待 handler 收敛后再返回终态 |
| 摘要可伪造来源 | 只接受真实消息 ID，并复核 session、role 与内容指纹 |
| 摘要/artifact 上下文无界 | 限制选择数量、单项长度、总长度并拒绝重复来源 |
| `BaseException` 可逃逸 | 转换为失败结果并保证终态审计 |
| 审计详情可被回写或泄露 | 事件返回不可变语义副本，CLI sink 脱敏敏感字段 |

以上负向用例已纳入 v0.4 的 23 项专项测试和 54 项全量回归。

## 6. 开发时间线

### 2026-06-21：v0.1/v0.2 文档与证据固化

- 建立 v0.1、v0.2 产品文档与测试报告。
- 写入机器可读验证 JSON，区分已通过项目和未覆盖风险。
- v0.1 明确为兼容基线，当前实现版本保持 0.2.0。

### 2026-06-21：启动 v0.3/v0.4 并行开发

- v0.3 开发通道负责 ESP32/ESP-IDF、流式调用及设备侧预注册工具。
- v0.4 开发通道负责受限 Agent Lite、显式产物注入和摘要记忆。
- 独立日志通道负责版本范围、证据、风险、发布流程和后续 GitHub 记录。
- 两条开发通道保持独立范围、测试和发布门槛，日志通道不以开发者摘要代替证据。

### 2026-06-21：v0.3/v0.4 开发预览收尾

- 复核源码版本 0.4.0，以及 v0.3/v0.4 产品、设计、协议和测试报告。
- 复核 `outputs/v0.3-verification.json` 与 `outputs/v0.4-verification.json`。
- 最终证据为 v0.1 4/4、v0.3 12/12、v0.4 23/23、全量 Python 54/54、`compileall` 通过。
- ESP32 只形成严格 C 静态语法证据，没有把 NDK Clang 检查写成 ESP-IDF 或真机通过。
- Android 离线 Gradle 137 tasks 的构建、单测和 lint 成功被记录为兼容回归，不替代 Android 真机 Agent UI 测试。
- v0.4 安全审计问题均有修复和负向回归；HTTP Agent、真实 LLM 与硬件端到端继续标为未交付。

## 7. GitHub 状态与待办

2026-06-21 GitHub 发布基础设施状态：

- 已安装 Git `2.54.0.windows.1` 和 GitHub CLI `2.95.0`；
- GitHub CLI 已通过系统 keyring 登录账号 `yuhaven`；日志不保存或显示认证 Token；
- `D:\bookPro` 已初始化为 Git 仓库，当前分支为 `main`；
- 本地提交身份为 `yuhaven` / `117079932+yuhaven@users.noreply.github.com`；
- 公开仓库 [yuhaven/ShuFu](https://github.com/yuhaven/ShuFu) 已创建；
- `origin` 已配置为 `https://github.com/yuhaven/ShuFu.git`，fetch/push 地址一致；
- 根提交 `0964a9527301f9b2c0556216fb689afe32822f60`（短哈希 `0964a95`，
  message：`release ShuFu v0.4 development preview`）已从 `main` 推送；
- 提交作者为 `yuhaven <117079932+yuhaven@users.noreply.github.com>`；
- 首次提交包含 118 个文件、11,193 行新增；`main` 已跟踪 `origin/main`；
- 首次 push 完成后的复核点工作树干净；
- GitHub 默认分支为 `main`、visibility 为 `PUBLIC`，Issues 和 Discussions 已启用；
- topics 为 `agent`、`ai`、`android`、`edge-ai`、`esp32`、`llm`、`python`。

这是一个新建空仓库的根提交，没有既有 base 可供比较，因此没有创建缺乏有效
diff 的草稿 PR，也没有伪造 PR 记录。Git、认证、公开仓库、根提交和首次 push
均已完成；详细发布门槛见 `docs/release-process.md`。

### 2026-06-21：GitHub 发布前安全预检

本次预检只评估“如果现在建立仓库，哪些文件可能进入首个提交”，没有执行
Git 初始化、提交、认证或网络上传。

- 首次文件枚举使用的过滤正则有误，输出不可用于判断，已明确作废且不计入以下结论；
- 随后改用明确 glob，按现有 `.gitignore` 等价规则排除 `build`、`.cxx`、
  `.gradle` 和 cache 类目录后重新执行；
- 可信重跑得到 117 个候选文件，合计 5,139,217 bytes；
- 没有单个候选文件超过 5 MiB；
- 对常见 private key、GitHub token、OpenAI API key 和 Google API key 格式进行
  静态模式扫描，未发现匹配；该结果只覆盖所列格式，不等同于通用秘密检测证明；
- 未发现 `.env`、`id_rsa`、`id_ed25519`、`hosts.yml`、`credentials`、
  `secrets` 等敏感文件名。

暂存审查还发现 `android/shufu-sdk/.cxx` 构建缓存曾被误暂存。处理方式是把
`.gitignore` 规则补强为 `android/**/.cxx/`，并只从 Git 索引移除该目录；本地
构建缓存未被删除。重新审查后 `.cxx` 暂存文件数为 0，最终候选仍为 117 个文件。

安全预检阶段只审查候选内容，没有在检查过程中创建提交或执行 push；通过以下
最终门槛后，主智能体已完成根提交和首次推送。

提交前最终门槛记录：

- 全量 Python 回归 54/54 通过，耗时 8.944 秒；
- credential 常见格式模式扫描无匹配；
- nested build cache 暂存数为 0。

以上门槛通过后，根提交和首次 push 已按本节记录完成。安全扫描结果只证明所列
模式和文件范围未命中，不应被解释为对所有秘密类型的形式化证明。

## 8. 发布日志收尾结论

- v0.3 和 v0.4 均完成各自定义范围内的开发预览，完成状态不外推到稳定版。
- 产品、设计、协议、测试报告和机器可读验证 JSON 均已存在并交叉核对。
- v0.1 兼容仍是强制门槛；v0.3/v0.4 的新增能力没有替代旧端点或旧 Schema。
- ESP-IDF/ESP32 真机、HTTP Agent、真实 LLM、Android Agent UI 真机均保持“未覆盖/未交付”。
- GitHub 公开仓库、根提交和首次 push 已完成，`main` 正跟踪 `origin/main`；作为新空仓库的根提交没有伪造无意义 PR。
