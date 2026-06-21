package ai.shufu.sdk

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.net.ServerSocket
import java.nio.file.Files
import java.nio.file.Path
import java.util.Comparator

class PythonNodeInteropTest {
    @Test
    fun kotlinSdkInvokesAndSynchronizesWithRealPythonNode() {
        val python = System.getenv("SHUFU_PYTHON")
        val repo = System.getenv("SHUFU_REPO_ROOT")
        assumeTrue("SHUFU_PYTHON and SHUFU_REPO_ROOT enable the interop test", !python.isNullOrBlank() && !repo.isNullOrBlank())

        val port = ServerSocket(0).use { it.localPort }
        val home = Files.createTempDirectory("shufu-python-interop")
        val process = ProcessBuilder(
            python,
            "-m",
            "shufu",
            "--home",
            home.toString(),
            "serve",
            "--port",
            port.toString(),
            "--token",
            "interop-secret",
        )
            .directory(Path.of(repo).toFile())
            .redirectErrorStream(true)
            .apply { environment()["PYTHONPATH"] = Path.of(repo, "src").toString() }
            .start()

        try {
            val client = ShuFuHttpClient("http://127.0.0.1:$port", "interop-secret", connectTimeoutMs = 500)
            var ready = false
            repeat(40) {
                if (!ready) {
                    try {
                        ready = client.capabilities().protocolVersion == "0.2"
                    } catch (_: Exception) {
                        Thread.sleep(100)
                    }
                }
            }
            assertTrue("Python ShuFu node did not become ready", ready)
            val response = client.invoke("Android interop", sessionId = "cross-device")
            assertTrue(response.output.contains("Android interop"))
            val bundle = client.pullSync(sessionId = "cross-device")
            assertEquals(2, bundle.schemaVersion)
            assertEquals(2, bundle.json.getJSONArray("messages").length())
        } finally {
            process.destroy()
            if (!process.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) process.destroyForcibly()
            Files.walk(home).sorted(Comparator.reverseOrder()).forEach(Files::deleteIfExists)
        }
    }
}

