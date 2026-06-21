package ai.shufu.sdk

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.Executors

class DiscoveryClientTest {
    @Test
    fun discoversLocalResponder() {
        DatagramSocket(0, InetAddress.getByName("127.0.0.1")).use { server ->
            val executor = Executors.newSingleThreadExecutor()
            executor.submit {
                val buffer = ByteArray(1024)
                val request = DatagramPacket(buffer, buffer.size)
                server.receive(request)
                val response = JSONObject()
                    .put("service", "shufu")
                    .put("node_id", "test-node")
                    .put("name", "Desktop")
                    .put("url", "http://127.0.0.1:7878")
                    .put("protocol_version", "0.2")
                    .toString()
                    .toByteArray()
                server.send(DatagramPacket(response, response.size, request.address, request.port))
            }
            val nodes = ShuFuDiscoveryClient(server.localPort, 1_000)
                .discover(listOf(InetAddress.getByName("127.0.0.1")))
            executor.shutdownNow()
            assertEquals(1, nodes.size)
            assertEquals("test-node", nodes.single().nodeId)
        }
    }
}

