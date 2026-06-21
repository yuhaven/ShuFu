package ai.shufu.sdk

import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class ShuFuHttpClientTest {
    private lateinit var server: ServerSocket
    private lateinit var executor: ExecutorService
    private lateinit var client: ShuFuHttpClient

    @Before
    fun startServer() {
        server = ServerSocket(0, 20, InetAddress.getByName("127.0.0.1"))
        executor = Executors.newCachedThreadPool()
        executor.submit {
            while (!server.isClosed) {
                try {
                    val socket = server.accept()
                    executor.submit { respond(socket) }
                } catch (_: Exception) {
                    break
                }
            }
        }
        client = ShuFuHttpClient("http://127.0.0.1:${server.localPort}")
    }

    private fun respond(socket: Socket) {
        socket.use {
            val reader = BufferedReader(InputStreamReader(it.getInputStream(), Charsets.UTF_8))
            val requestLine = reader.readLine() ?: return
            val path = requestLine.split(' ').getOrNull(1)?.substringBefore('?').orEmpty()
            var contentLength = 0
            while (true) {
                val line = reader.readLine() ?: break
                if (line.isEmpty()) break
                if (line.startsWith("Content-Length:", ignoreCase = true)) {
                    contentLength = line.substringAfter(':').trim().toInt()
                }
            }
            if (contentLength > 0) {
                val body = CharArray(contentLength)
                var read = 0
                while (read < contentLength) {
                    val count = reader.read(body, read, contentLength - read)
                    if (count < 0) break
                    read += count
                }
            }
            val json = when (path) {
                "/shufu/v1/capabilities" -> JSONObject()
                    .put("node_id", "desktop")
                    .put("protocol_version", "0.2")
                    .put("runtime", "echo")
                    .put("memory", JSONObject().put("incremental_sync", true))
                "/shufu/v1/invoke" -> JSONObject()
                    .put("model", "assistant")
                    .put("session_id", "project")
                    .put("output", "continued")
                    .put("created_at", "2026-06-19T00:00:00Z")
                "/shufu/v2/sync/pull" -> JSONObject()
                    .put("schema_version", 2)
                    .put("source_node_id", "desktop")
                    .put("cursor", 7)
                    .put("sessions", JSONArray())
                    .put("messages", JSONArray())
                    .put("artifacts", JSONArray())
                else -> JSONObject().put("sessions", 0).put("messages", 0).put("artifacts", 0).put("cursor", 7)
            }
            val bytes = json.toString().toByteArray()
            it.getOutputStream().use { output ->
                output.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                output.write(bytes)
            }
        }
    }

    @After
    fun stopServer() {
        server.close()
        executor.shutdownNow()
    }

    @Test
    fun invokesAndPullsV2Memory() {
        assertTrue(client.capabilities().incrementalSync)
        assertEquals("continued", client.invoke("continue", sessionId = "project").output)
        assertEquals(7, client.pullSync(sessionId = "project").cursor)
    }
}
