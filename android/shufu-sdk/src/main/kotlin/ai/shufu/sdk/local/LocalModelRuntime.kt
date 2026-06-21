package ai.shufu.sdk.local

/** Runtime-neutral lifecycle for an on-device text-generation backend. */
interface LocalModelRuntime : AutoCloseable {
    val isLoaded: Boolean
    val version: String
    fun load(modelPath: String)
    fun generate(prompt: String, maxTokens: Int = 256): String
}
