# ShuFu（鼠符）v0.2 测试报告

> 报告日期：2026-06-21  
> 测试对象：ShuFu 0.2.0 桌面核心、Android SDK/App、ARM64 JNI 与发布物  
> 测试平台：Windows 10.0.26200 x64  
> 结论：自动化、跨语言、静态检查和构建验证通过；物理 Android 设备与真实模型推理仍需发布前验证

## 1. 测试范围

本报告验证：

- Python Node、MemoryStore、Discovery、Sync 和 v0.1 兼容；
- Android 数据模型、HTTP Client、UDP Discovery；
- Kotlin SDK 调用真实 Python Node 的跨语言链路；
- Android Kotlin 编译、JVM 单元测试；
- llama.cpp ARM64 JNI Debug/RelWithDebInfo 编译；
- Debug APK 与 AAR 组装；
- Android Release Lint；
- APK 签名方案、ABI 内容和 JNI 导出；
- 仓库 `outputs/` 发布物 SHA-256 完整性。

不覆盖：

- 物理 Android 设备安装和 UI 手工操作；
- 真机 UDP 广播环境差异；
- 真实 GGUF 加载、生成质量、速度、温度和峰值内存；
- 长时间运行、并发、断网恢复、弱网和大 Bundle 压力；
- Linux 实机；
- ESP32（不属于 v0.2）。

## 2. 测试环境

| 项目 | 版本/配置 |
| --- | --- |
| 仓库 | `D:\bookPro` |
| 操作系统 | Microsoft Windows NT 10.0.26200.0 x64 |
| Python | 3.12.13 |
| JDK | Eclipse Temurin 17.0.19+10 |
| Gradle | 8.10.2，离线本地发行版 |
| Android SDK | 35 |
| Build Tools | 35.0.0 |
| Android NDK | 27.2.12479018 |
| CMake | 3.22.1 |
| llama.cpp | b9722 |
| Android ABI | arm64-v8a |
| Python 测试 | `unittest` |
| Android 测试 | JUnit 4 / Gradle Test |

Gradle 测试时显式提供：

- `JAVA_HOME`；
- `ANDROID_HOME` / `ANDROID_SDK_ROOT`；
- `SHUFU_PYTHON`；
- `SHUFU_REPO_ROOT`；
- 本机离线 `GRADLE_USER_HOME`。

跨语言环境变量不可省略，否则 `PythonNodeInteropTest` 会按设计跳过，而不是失败。

## 3. 执行命令

### 3.1 Python

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

### 3.2 Android 单元测试、JNI 与构建

```powershell
$env:SHUFU_PYTHON = (Get-Command python).Source
$env:SHUFU_REPO_ROOT = (Resolve-Path .).Path
cd android
gradle testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug --offline
gradle :shufu-sdk:testDebugUnitTest --rerun-tasks --offline
```

第二条命令用于确保跨语言测试在环境变量生效后实际执行。

### 3.3 Release Lint

```powershell
gradle :shufu-sdk:lintRelease :app:lintRelease --offline
```

### 3.4 产物检查

- `apksigner verify --verbose --print-certs app-debug.apk`；
- `jar tf` 检查 APK/AAR 的 `arm64-v8a` native library；
- NDK `llvm-nm --defined-only libshufu_jni.so` 检查 JNI 导出；
- `Get-FileHash -Algorithm SHA256` 比对发布清单。

## 4. Python 测试结果

| 测试域 | 数量 | 结果 |
| --- | ---: | --- |
| Agent 与 CLI 安全边界 | 3 | 全部通过 |
| UDP 发现 | 1 | 通过 |
| MemoryStore 与同步 | 5 | 全部通过 |
| Node | 2 | 全部通过 |
| HTTP Service | 4 | 全部通过 |
| v0.1 专项兼容 | 4 | 全部通过 |
| 合计 | 19 | **19 通过，0 失败，0 错误，0 跳过** |

执行耗时 5.288 秒；`compileall` 通过。

关键 v0.2 证据：

- UDP responder/client 本机发现成功；
- `changes` cursor 后仅导出新增对象；
- v2 push/pull 往返成功；
- capabilities 公布 0.1/0.2、Schema 1/2 与增量同步；
- v1 端点仍返回 Schema 1。

## 5. Android JVM 与跨语言结果

| Test Suite | 测试数 | 失败 | 错误 | 跳过 | 结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| `DiscoveryClientTest` | 1 | 0 | 0 | 0 | 通过 |
| `ModelsTest` | 1 | 0 | 0 | 0 | 通过 |
| `PythonNodeInteropTest` | 1 | 0 | 0 | 0 | 通过 |
| `ShuFuHttpClientTest` | 1 | 0 | 0 | 0 | 通过 |
| 合计 | 4 | 0 | 0 | 0 | **全部通过** |

JVM 测试累计报告时间 1.302 秒。

跨语言用例实际完成：

1. Kotlin 启动真实 Python `shufu serve` 子进程；
2. 通过 Token 读取 capabilities；
3. Kotlin `ShuFuHttpClient.invoke` 调用 Python Node；
4. 响应包含原始 prompt；
5. Kotlin 拉取 Schema 2 Bundle；
6. 核对同 session 中存在 user/assistant 两条消息；
7. 终止子进程并清理临时目录。

## 6. Android 构建结果

首次完整命令执行 **76 个 Gradle 任务，76 个执行，BUILD SUCCESSFUL，耗时 1 分 2 秒**。

| 构建项 | 结果 | 证据 |
| --- | --- | --- |
| Kotlin SDK Debug | 通过 | `compileDebugKotlin` |
| SDK JVM Test | 通过 | `testDebugUnitTest` |
| llama.cpp Debug ARM64 | 通过 | `configureCMakeDebug` / `buildCMakeDebug` |
| Debug AAR | 通过 | `bundleDebugAar` / `assembleDebug` |
| App Kotlin Debug | 通过 | `app:compileDebugKotlin` |
| Debug APK | 通过 | `app:packageDebug` / `app:assembleDebug` |

当前工作区验证构建：

| 文件 | 大小 | SHA-256 |
| --- | ---: | --- |
| `android/app/build/outputs/apk/debug/app-debug.apk` | 29,090,312 B | `168ba695f7c16142aa697bceccedcfd547c25329241c1a4178d1353361eb30da` |
| `android/shufu-sdk/build/outputs/aar/shufu-sdk-debug.aar` | 2,058,661 B | `8ae2e05a018daf40903007418e4e5f0270aba56e3d23929d9d1eeeb4e82da1b3` |

Debug 构建哈希可能随构建环境、时间戳或工具链元数据变化，不作为可复现构建承诺。

## 7. Native 与 APK 验证

### 7.1 ABI 内容

当前 Debug APK 包含：

- `lib/arm64-v8a/libc++_shared.so`；
- `lib/arm64-v8a/libshufu_jni.so`。

当前 Debug AAR 包含对应的：

- `jni/arm64-v8a/libc++_shared.so`；
- `jni/arm64-v8a/libshufu_jni.so`。

### 7.2 JNI 导出

`llvm-nm` 验证四个公开入口存在：

- `nativeLoadModel`；
- `nativeGenerate`；
- `nativeClose`；
- `nativeVersion`。

### 7.3 签名

Debug APK：

- 验证通过；
- APK Signature Scheme v2：是；
- v1/v3/v3.1/v4：否；
- 签名者：`C=US, O=Android, CN=Android Debug`；
- RSA 2048 位。

该签名只适合开发侧载，不能作为正式商店发布签名。

## 8. Release Lint

`shufu-sdk:lintRelease` 与 `app:lintRelease` 均 BUILD SUCCESSFUL。

| 模块 | Error | Warning | 说明 |
| --- | ---: | ---: | --- |
| shufu-sdk | 0 | 1 | 仅构建 arm64-v8a，ChromeOS 缺少 x86_64 |
| app | 0 | 3 | 缺少显式 App 图标；两处 UI 字符串未资源化 |
| 合计 | 0 | 4 | 不阻塞 v0.2 技术验证，但正式发布前应处理 |

具体观察项：

- `ChromeOsAbiSupport`：当前产品范围只承诺 ARM64 Android；
- `MissingApplicationIcon`：示例 App 尚无正式品牌图标；
- `SetTextI18n` ×2：标题/说明使用代码字符串，尚未国际化。

## 9. 仓库发布物完整性

`outputs/SHA256SUMS-v0.2.txt` 与当前文件重新计算结果一致：

| 发布物 | SHA-256 | 匹配 |
| --- | --- | --- |
| `ShuFu-v0.2-android-arm64.apk` | `91b861fec9cf3dbeb1dbb2986778c9f84d85fe8744e45ab8c33b4991a8d73129` | 是 |
| `ShuFu-v0.2-sdk-arm64.aar` | `156644dccfbd0ba5b45469223bfed9f8ab8445e8d6a00f2c0c7c010dba6f052c` | 是 |

发布 APK/AAR 均包含 `arm64-v8a/libshufu_jni.so` 和 `libc++_shared.so`；发布 APK 的 v2 签名验证通过。

## 10. 验收矩阵

| 验收编号 | 要求 | 本轮证据 | 状态 |
| --- | --- | --- | --- |
| V02-A01 | v0.2 能力协商 | Python Service 测试 | 通过 |
| V02-A02 | UDP 发现 | Python + Kotlin Discovery 测试 | 通过 |
| V02-A03 | 增量拉取 | cursor 单元测试 | 通过 |
| V02-A04 | 幂等推送 | Memory/Service 测试 | 通过 |
| V02-A05 | v0.1 兼容 | v0.1 专项 4/4 | 通过 |
| V02-A06 | Kotlin ↔ Python | Interop 实际执行、无跳过 | 通过 |
| V02-A07 | AAR 可构建 | `assembleDebug` | 通过 |
| V02-A08 | APK 可构建 | `app:assembleDebug` | 通过 |
| V02-A09 | JNI 可编译和导出 | ARM64 构建 + `llvm-nm` | 通过 |
| V02-A10 | 发布物完整 | SHA-256 与清单一致 | 通过 |

## 11. 环境问题与处理记录

| 现象 | 分类 | 处理 | 产品缺陷？ |
| --- | --- | --- | --- |
| `JAVA_HOME` 未设置 | 本机测试环境 | 使用已有 Temurin 17 临时注入 | 否 |
| Wrapper 下载 10 秒超时 | 外部网络/工具环境 | 使用本机 Gradle 8.10.2 离线发行版 | 否 |
| Android SDK 未发现 | 本机测试环境 | 临时设置 `ANDROID_HOME` | 否 |
| Interop 首轮跳过 | 测试配置 | 设置 `SHUFU_PYTHON`、`SHUFU_REPO_ROOT` 强制重跑 | 否 |
| CMake 提示 Git 不存在 | 构建元数据警告 | 不影响 native 编译；版本由固定归档控制 | 否 |

这些记录应转化为 CI 配置，避免未来把“跳过”误报为“通过”。

## 12. 未覆盖风险

| 风险 | 等级 | 下一步 |
| --- | --- | --- |
| 无物理 Android 设备测试 | 高 | 至少覆盖一台 6–8 GB RAM ARM64 手机 |
| 无真实 GGUF 推理 | 高 | 选定许可清晰的小模型，记录加载时间、首 token、峰值内存 |
| 局域网明文 HTTP | 高（公网场景） | 明确仅可信 LAN；后续增加 TLS/配对 Adapter |
| 单 ABI | 中 | 根据社区设备数据决定是否增加 x86_64/armeabi-v7a |
| 大 Bundle/弱网 | 中 | 增加分块、压缩、失败重试和容量测试 |
| App 缺少图标与国际化 | 低至中 | 正式发布前解决四个 lint warning |
| Debug 签名 | 高（发布场景） | 配置独立 release key 与安全保管流程 |
| 并发/长期稳定性 | 中 | 增加 soak、并发调用和异常恢复测试 |

## 13. 测试结论

v0.2 的桌面核心、v0.1 兼容、Android JVM、Kotlin ↔ Python 互操作、ARM64 JNI 编译、APK/AAR 构建、Release Lint 和发布物完整性均有本轮直接证据并通过。

发布判断：

- **开源技术预览 / v0.2 开发验证：通过。**
- **面向社区的正式 Android 稳定版：有条件通过。** 必须先完成物理设备安装与真实 GGUF 推理测试，并替换 Debug 签名；建议同时处理 App 图标和国际化警告。

