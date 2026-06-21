package ai.shufu.sdk

import org.json.JSONArray
import org.json.JSONObject

/** Immutable conversation record shared by the Android store and UI. */
data class ShuFuMessage(
    val id: String,
    val sessionId: String,
    val role: String,
    val content: String,
    val createdAt: String,
)

/** Stable response shape of the v0.1-compatible invoke endpoint. */
data class InvokeResponse(
    val model: String,
    val sessionId: String,
    val output: String,
    val createdAt: String,
) {
    companion object {
        fun fromJson(json: JSONObject) = InvokeResponse(
            model = json.getString("model"),
            sessionId = json.getString("session_id"),
            output = json.getString("output"),
            createdAt = json.getString("created_at"),
        )
    }
}

/** Capability subset needed by Android to negotiate v0.2 synchronization. */
data class NodeCapabilities(
    val nodeId: String,
    val protocolVersion: String,
    val runtime: String,
    val incrementalSync: Boolean,
) {
    companion object {
        fun fromJson(json: JSONObject) = NodeCapabilities(
            nodeId = json.getString("node_id"),
            protocolVersion = json.getString("protocol_version"),
            runtime = json.getString("runtime"),
            incrementalSync = json.getJSONObject("memory").getBoolean("incremental_sync"),
        )
    }
}

/** Untrusted LAN advertisement; discovery does not authenticate this node. */
data class DiscoveredNode(
    val nodeId: String,
    val name: String,
    val url: String,
    val protocolVersion: String,
    val address: String,
) {
    companion object {
        fun fromJson(json: JSONObject, address: String) = DiscoveredNode(
            nodeId = json.getString("node_id"),
            name = json.getString("name"),
            url = json.getString("url"),
            protocolVersion = json.getString("protocol_version"),
            address = address,
        )
    }
}

/** Counts of newly imported objects, plus the source cursor when available. */
data class SyncResult(
    val sessions: Int,
    val messages: Int,
    val artifacts: Int,
    val cursor: Long = 0,
)

/**
 * Thin wrapper around the protocol JSON.
 *
 * Keeping unknown fields in the original object preserves forward compatibility
 * and lets v0.1 clients ignore v0.2 metadata without lossy model conversions.
 */
class MemoryBundle private constructor(val json: JSONObject) {
    val schemaVersion: Int get() = json.getInt("schema_version")
    val cursor: Long get() = json.optLong("cursor", 0)
    val sourceNodeId: String? get() = json.optString("source_node_id").ifBlank { null }

    override fun toString(): String = json.toString()

    companion object {
        fun parse(text: String): MemoryBundle = MemoryBundle(JSONObject(text))
        fun fromJson(json: JSONObject): MemoryBundle = MemoryBundle(json)
        fun empty(sourceNodeId: String): MemoryBundle = MemoryBundle(
            JSONObject()
                .put("schema_version", 2)
                .put("bundle_id", java.util.UUID.randomUUID().toString())
                .put("source_node_id", sourceNodeId)
                .put("after", 0)
                .put("cursor", 0)
                .put("exported_at", java.time.Instant.now().toString())
                .put("sessions", JSONArray())
                .put("messages", JSONArray())
                .put("artifacts", JSONArray())
        )
    }
}
