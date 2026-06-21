package ai.shufu.sdk.local

import java.io.File

/**
 * Thread-safe Kotlin owner of one native llama.cpp model handle.
 *
 * A handle is never reused after [close]; synchronized lifecycle methods prevent
 * concurrent generation and replacement from racing in native code.
 */
class LlamaCppRuntime : LocalModelRuntime {
    private var handle: Long = 0

    override val isLoaded: Boolean get() = handle != 0L
    override val version: String get() = nativeVersion()

    @Synchronized
    override fun load(modelPath: String) {
        val file = File(modelPath)
        require(file.isFile) { "GGUF model not found: ${file.absolutePath}" }
        // Release the old native allocation before replacing the only handle.
        close()
        handle = nativeLoadModel(file.absolutePath)
        check(handle != 0L) { "Native model loader returned an empty handle" }
    }

    @Synchronized
    override fun generate(prompt: String, maxTokens: Int): String {
        check(isLoaded) { "Load a GGUF model before local generation" }
        require(prompt.isNotBlank()) { "prompt must not be blank" }
        return nativeGenerate(handle, prompt, maxTokens)
    }

    @Synchronized
    override fun close() {
        if (handle != 0L) {
            nativeClose(handle)
            handle = 0
        }
    }

    private external fun nativeLoadModel(modelPath: String): Long
    private external fun nativeGenerate(handle: Long, prompt: String, maxTokens: Int): String
    private external fun nativeClose(handle: Long)
    private external fun nativeVersion(): String

    companion object {
        init {
            // Loading here makes missing ABI/native packaging fail at first use,
            // before a model path or prompt is accepted.
            System.loadLibrary("shufu_jni")
        }
    }
}
