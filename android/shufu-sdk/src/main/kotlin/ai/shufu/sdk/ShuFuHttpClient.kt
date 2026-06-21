package ai.shufu.sdk

import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URI
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

/**
 * Dependency-free synchronous client for ShuFu Node endpoints.
 *
 * Callers must invoke it off Android's main thread. Retries are intentionally
 * left to the host because replaying a model request may incur cost or effects.
 */
class ShuFuHttpClient(
    baseUrl: String,
    private val token: String? = null,
    private val connectTimeoutMs: Int = 5_000,
    private val readTimeoutMs: Int = 120_000,
) {
    val baseUrl: String = baseUrl.trimEnd('/')

    fun capabilities(): NodeCapabilities = NodeCapabilities.fromJson(request("GET", "/shufu/v1/capabilities"))

    /** Invoke the stable v0.1 route so the same SDK can talk to old and new nodes. */
    fun invoke(
        input: String,
        model: String = "assistant",
        sessionId: String = "default",
        memoryWindow: Int = 20,
    ): InvokeResponse {
        require(input.isNotBlank()) { "input must not be blank" }
        val body = JSONObject()
            .put("model", model)
            .put("session_id", sessionId)
            .put("input", input)
            .put("memory_window", memoryWindow)
        return InvokeResponse.fromJson(request("POST", "/shufu/v1/invoke", body))
    }

    /** Pull only remote objects recorded after [after] in the selected scope. */
    fun pullSync(after: Long = 0, sessionId: String? = null): MemoryBundle {
        val query = buildString {
            append("after=").append(after)
            if (!sessionId.isNullOrBlank()) {
                append("&session_id=")
                append(URLEncoder.encode(sessionId, StandardCharsets.UTF_8.name()))
            }
        }
        return MemoryBundle.fromJson(request("GET", "/shufu/v2/sync/pull?$query"))
    }

    /** Push a Schema 1/2 bundle; object IDs make repeated pushes idempotent. */
    fun pushSync(bundle: MemoryBundle): SyncResult {
        val json = request("POST", "/shufu/v2/sync/push", bundle.json)
        return SyncResult(
            sessions = json.optInt("sessions"),
            messages = json.optInt("messages"),
            artifacts = json.optInt("artifacts"),
            cursor = json.optLong("cursor"),
        )
    }

    private fun request(method: String, path: String, body: JSONObject? = null): JSONObject {
        val connection = URI.create("$baseUrl$path").toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = connectTimeoutMs
            connection.readTimeout = readTimeoutMs
            connection.setRequestProperty("Accept", "application/json")
            token?.takeIf { it.isNotBlank() }?.let {
                connection.setRequestProperty("Authorization", "Bearer $it")
            }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(StandardCharsets.UTF_8)) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }.orEmpty()
            // Preserve status and body for host diagnostics instead of collapsing
            // every protocol failure into a generic networking exception.
            if (status !in 200..299) {
                throw ShuFuHttpException(status, text.ifBlank { "HTTP $status" })
            }
            return JSONObject(text)
        } finally {
            connection.disconnect()
        }
    }
}

/** HTTP-level failure returned by a reachable ShuFu node. */
class ShuFuHttpException(val statusCode: Int, message: String) : java.io.IOException(message)
