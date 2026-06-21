# ShuFu Android v0.2

## 模块

- `shufu-sdk`：AAR SDK、SQLite MemoryStore、UDP 发现、HTTP Client、同步引擎、模型管理、llama.cpp JNI；
- `app`：不依赖 AndroidX 的极简示例应用。

## 构建要求

- JDK 17；
- Android SDK 35；
- Build Tools 35.0.0；
- Android NDK `27.2.12479018`；
- CMake `3.22.1`。

```powershell
cd android
.\gradlew.bat testDebugUnitTest :shufu-sdk:assembleDebug :app:assembleDebug
```

首次构建会下载并校验 llama.cpp `b9722`：

```text
SHA-256 7144212cca13b6014dac1a7f284f2b551de91f9c8f80c5ecbf9cfde4cb549540
```

离线构建：

```powershell
.\gradlew.bat assembleDebug -PshufuLlamaArchive=C:\cache\llama.cpp-b9722.zip
```

## 桌面连接

Windows/Linux：

```powershell
shufu serve --host 0.0.0.0 --allow-lan --token replace-me
```

Android App：

1. 点击“发现节点”；
2. 输入相同 Token；
3. 设置与 Windows 相同的 Session；
4. 点击“调用 Node”或“同步记忆”。

## 本地 GGUF

1. 点击“导入 GGUF”；
2. 从系统文档选择器选择模型；
3. 模型复制到 App 私有目录并计算 SHA-256；
4. 点击“本地生成”；
5. 结果进入当前 session，可以同步回桌面。

v0.2 APK 只包含 ARM64 Native Library，不包含模型。建议从较小量化模型开始，并遵守模型许可证。

## AAR 使用

```kotlin
val client = ShuFuHttpClient("http://192.168.1.20:7878", token = "replace-me")
val response = client.invoke("继续完善文档", sessionId = "project-a")
```

发现：

```kotlin
val nodes = ShuFuDiscoveryClient().discover()
```

同步：

```kotlin
val memory = ShuFuMemoryStore(context)
val report = ShuFuSyncEngine(context, memory).sync(client, "project-a")
```

本地模型：

```kotlin
val runtime = LlamaCppRuntime()
runtime.load(modelFile.absolutePath)
val answer = runtime.generate("user: 你好\nassistant:")
```

