package ai.shufu.sdk

import android.content.Context

/** Summary of one explicit foreground synchronization operation. */
data class SyncReport(
    val pushed: SyncResult,
    val pulled: SyncResult,
    val remoteCursor: Long,
)

/**
 * Coordinates idempotent push/pull without owning a background lifecycle.
 *
 * Remote cursors are keyed by node ID and session because a cursor has meaning
 * only within the change sequence that created it.
 */
class ShuFuSyncEngine(
    context: Context,
    private val memory: ShuFuMemoryStore,
) {
    private val preferences = context.applicationContext.getSharedPreferences("shufu-sync-v2", Context.MODE_PRIVATE)

    fun sync(client: ShuFuHttpClient, sessionId: String? = null): SyncReport {
        val capabilities = client.capabilities()
        require(capabilities.incrementalSync) { "Remote node does not support ShuFu v0.2 sync" }
        val cursorKey = "${capabilities.nodeId}:${sessionId.orEmpty()}"
        val remoteCursor = preferences.getLong(cursorKey, 0)

        // v0.2 deliberately pushes a full idempotent bundle. This avoids maintaining
        // a second acknowledgement cursor while the protocol is still young.
        val pushed = client.pushSync(memory.exportBundle(sessionId))
        val remoteBundle = client.pullSync(remoteCursor, sessionId)
        val pulled = memory.importBundle(remoteBundle)
        // Advance only after import succeeds. A failed import therefore causes a
        // safe replay on the next sync rather than silently skipping data.
        preferences.edit().putLong(cursorKey, remoteBundle.cursor).apply()
        return SyncReport(pushed, pulled, remoteBundle.cursor)
    }
}
