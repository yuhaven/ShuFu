package ai.shufu.sdk

import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException

/**
 * Bounded UDP discovery client for nearby v0.2 nodes.
 *
 * Results are reachability hints, not authenticated identities. Applications
 * should display the URL and use a token before exchanging sensitive memory.
 */
class ShuFuDiscoveryClient(
    private val port: Int = 7879,
    private val timeoutMs: Int = 1_200,
) {
    fun discover(targets: List<InetAddress> = listOf(InetAddress.getByName("255.255.255.255"))): List<DiscoveredNode> {
        val found = linkedMapOf<String, DiscoveredNode>()
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = timeoutMs
            val request = "SHUFU_DISCOVER_V2".toByteArray(Charsets.UTF_8)
            targets.forEach { target ->
                socket.send(DatagramPacket(request, request.size, target, port))
            }
            val deadline = System.currentTimeMillis() + timeoutMs
            while (System.currentTimeMillis() < deadline) {
                val buffer = ByteArray(4096)
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(packet)
                    val json = JSONObject(String(packet.data, 0, packet.length, Charsets.UTF_8))
                    if (json.optString("service") != "shufu") continue
                    val node = DiscoveredNode.fromJson(json, packet.address.hostAddress ?: "")
                    // A node can answer through more than one interface; nodeId
                    // provides deterministic deduplication during this window.
                    found[node.nodeId] = node
                } catch (_: SocketTimeoutException) {
                    break
                } catch (_: Exception) {
                    // Malformed packets are ignored; discovery must not crash the app.
                }
            }
        }
        return found.values.sortedWith(compareBy(DiscoveredNode::name, DiscoveredNode::nodeId))
    }
}
