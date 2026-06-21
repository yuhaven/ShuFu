package ai.shufu.app

import ai.shufu.sdk.ShuFuDiscoveryClient
import ai.shufu.sdk.ShuFuHttpClient
import ai.shufu.sdk.ShuFuMemoryStore
import ai.shufu.sdk.ShuFuSyncEngine
import ai.shufu.sdk.local.LlamaCppRuntime
import ai.shufu.sdk.local.ModelManager
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.util.concurrent.Executors

/**
 * One-screen reference app demonstrating the complete v0.2 Android flow.
 *
 * It intentionally avoids AndroidX and architecture frameworks so SDK behavior
 * remains visible. Production hosts should move state into their own lifecycle
 * architecture and expose clearer node/model selection UI.
 */
class MainActivity : Activity() {
    // Network, SQLite orchestration, and native inference never run on the UI thread.
    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var memory: ShuFuMemoryStore
    private lateinit var syncEngine: ShuFuSyncEngine
    private lateinit var modelManager: ModelManager
    private var localRuntime: LlamaCppRuntime? = null

    private lateinit var nodeUrl: EditText
    private lateinit var token: EditText
    private lateinit var session: EditText
    private lateinit var prompt: EditText
    private lateinit var status: TextView
    private lateinit var output: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        memory = ShuFuMemoryStore(this)
        syncEngine = ShuFuSyncEngine(this, memory)
        modelManager = ModelManager(this)
        setContentView(buildUi())
        setStatus("ShuFu v0.2 ready · 本地记忆节点 ${memory.nodeId.take(8)}")
    }

    /** Build the compact demo UI in code to keep the reference project self-contained. */
    private fun buildUi(): ScrollView {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(28), dp(20), dp(36))
            setBackgroundColor(Color.rgb(244, 239, 230))
        }
        root.addView(TextView(this).apply {
            text = "ShuFu 鼠符"
            textSize = 30f
            setTextColor(Color.rgb(11, 13, 15))
        })
        root.addView(TextView(this).apply {
            text = "Android v0.2 · 发现、调用、记忆接力、本地 GGUF"
            textSize = 14f
            setTextColor(Color.DKGRAY)
            setPadding(0, dp(4), 0, dp(20))
        })

        nodeUrl = field("Node URL", "http://10.0.2.2:7878")
        token = field("可选 Token", "")
        session = field("Session", "default")
        prompt = field("输入", "继续完善 Windows 上的文档")
        root.addView(nodeUrl)
        root.addView(token)
        root.addView(session)
        root.addView(prompt)

        root.addView(buttonRow(
            button("发现节点") { discover() },
            button("同步记忆") { synchronize() },
        ))
        root.addView(buttonRow(
            button("调用 Node") { invokeRemote() },
            button("导入 GGUF") { chooseModel() },
        ))
        root.addView(button("本地生成") { invokeLocal() })

        status = TextView(this).apply {
            textSize = 14f
            setTextColor(Color.rgb(8, 127, 91))
            setPadding(0, dp(20), 0, dp(12))
        }
        output = TextView(this).apply {
            textSize = 17f
            setTextColor(Color.rgb(11, 13, 15))
            setBackgroundColor(Color.WHITE)
            setPadding(dp(16), dp(16), dp(16), dp(16))
            minHeight = dp(180)
        }
        root.addView(status)
        root.addView(output, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        return ScrollView(this).apply { addView(root) }
    }

    private fun discover() = background("正在发现局域网节点…") {
        val nodes = ShuFuDiscoveryClient().discover()
        if (nodes.isEmpty()) {
            setStatus("未发现节点；请在桌面执行 shufu serve --host 0.0.0.0 --allow-lan")
        } else {
            val selected = nodes.first()
            runOnUiThread { nodeUrl.setText(selected.url) }
            setStatus("已发现 ${nodes.size} 个节点，使用 ${selected.name} · ${selected.url}")
        }
    }

    private fun invokeRemote() {
        val text = prompt.text.toString()
        val sessionId = session.text.toString()
        background("正在调用 ShuFu Node…") {
            val client = client()
            val response = client.invoke(text, sessionId = sessionId)
            val report = syncEngine.sync(client, sessionId)
            setOutput(response.output)
            setStatus("远程完成 · 同步 ${report.pulled.messages} 条消息 / ${report.pulled.artifacts} 个产物")
        }
    }

    private fun synchronize() {
        val sessionId = session.text.toString().ifBlank { null }
        background("正在同步 Windows ↔ Android 记忆…") {
            val report = syncEngine.sync(client(), sessionId)
            setStatus("同步完成 · push ${report.pushed.messages} / pull ${report.pulled.messages} · cursor ${report.remoteCursor}")
        }
    }

    private fun chooseModel() {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/octet-stream"
        }, REQUEST_MODEL)
    }

    @Deprecated("v0.2 uses the platform activity result API to avoid an AndroidX dependency")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQUEST_MODEL || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        val name = displayName(uri).let { if (it.endsWith(".gguf", true)) it else "$it.gguf" }
        background("正在导入并校验 GGUF…") {
            val model = modelManager.importFromUri(contentResolver, uri, name)
            val runtime = localRuntime ?: LlamaCppRuntime().also { localRuntime = it }
            runtime.load(model.file.absolutePath)
            setStatus("本地模型已加载 · ${model.file.name} · ${model.size / (1024 * 1024)} MB · ${runtime.version}")
        }
    }

    private fun invokeLocal() {
        val text = prompt.text.toString()
        val sessionId = session.text.toString()
        background("正在 Android 本地生成…") {
            val runtime = localRuntime ?: run {
                val existing = modelManager.list().firstOrNull() ?: error("请先导入一个 GGUF 模型")
                LlamaCppRuntime().also { it.load(existing.file.absolutePath); localRuntime = it }
            }
            // v0.2 uses a deliberately simple text transcript. Model-specific chat
            // templates and token budgeting belong in a future runtime adapter.
            val prior = memory.history(sessionId, 12).joinToString("\n") { "${it.role}: ${it.content}" }
            val fullPrompt = buildString {
                if (prior.isNotBlank()) append(prior).append('\n')
                append("user: ").append(text).append("\nassistant:")
            }
            memory.addMessage(sessionId, "user", text)
            val answer = runtime.generate(fullPrompt, 256)
            memory.addMessage(sessionId, "assistant", answer)
            setOutput(answer)
            setStatus("Android 本地完成 · 已写入 session $sessionId，可同步回 Windows")
        }
    }

    private fun client() = ShuFuHttpClient(
        nodeUrl.text.toString(),
        token.text.toString().ifBlank { null },
    )

    /** Run a blocking SDK operation on the single worker and surface failures in UI. */
    private fun background(message: String, block: () -> Unit) {
        setStatus(message)
        executor.execute {
            try {
                block()
            } catch (error: Throwable) {
                setStatus("失败：${error.message ?: error.javaClass.simpleName}")
            }
        }
    }

    private fun setStatus(text: String) = runOnUiThread { status.text = text }
    private fun setOutput(text: String) = runOnUiThread { output.text = text }

    private fun field(label: String, initial: String) = EditText(this).apply {
        hint = label
        setText(initial)
        setSingleLine(label != "输入")
        setPadding(dp(12), dp(8), dp(12), dp(8))
    }

    private fun button(text: String, action: () -> Unit) = Button(this).apply {
        this.text = text
        isAllCaps = false
        setOnClickListener { action() }
    }

    private fun buttonRow(vararg buttons: Button) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        buttons.forEach { addView(it, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)) }
    }

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) return cursor.getString(0)
        }
        return "model.gguf"
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    override fun onDestroy() {
        localRuntime?.close()
        memory.close()
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private const val REQUEST_MODEL = 42
    }
}
