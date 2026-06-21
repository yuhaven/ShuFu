package ai.shufu.sdk

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelsTest {
    @Test
    fun parsesV2MemoryBundleAndCapabilities() {
        val bundle = MemoryBundle.fromJson(
            JSONObject()
                .put("schema_version", 2)
                .put("cursor", 9)
                .put("source_node_id", "desktop")
                .put("sessions", JSONArray())
                .put("messages", JSONArray())
                .put("artifacts", JSONArray())
        )
        assertEquals(2, bundle.schemaVersion)
        assertEquals(9, bundle.cursor)
        assertEquals("desktop", bundle.sourceNodeId)

        val capabilities = NodeCapabilities.fromJson(
            JSONObject()
                .put("node_id", "node")
                .put("protocol_version", "0.2")
                .put("runtime", "echo")
                .put("memory", JSONObject().put("incremental_sync", true))
        )
        assertTrue(capabilities.incrementalSync)
    }
}

