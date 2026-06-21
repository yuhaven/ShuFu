package ai.shufu.sdk

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID

/**
 * Android implementation of ShuFu's portable session and artifact store.
 *
 * Metadata lives in SQLite while artifact bytes are content-addressed by
 * SHA-256 in app-private storage. Stable object IDs make repeated imports safe.
 */
class ShuFuMemoryStore(context: Context) : SQLiteOpenHelper(
    context.applicationContext,
    "shufu-memory-v2.sqlite3",
    null,
    2,
) {
    private val appContext = context.applicationContext
    private val artifactDirectory = File(appContext.filesDir, "shufu/artifacts").apply { mkdirs() }

    val nodeId: String by lazy {
        writableDatabase.rawQuery("SELECT value FROM meta WHERE key = 'node_id'", null).use { cursor ->
            check(cursor.moveToFirst()) { "ShuFu node_id missing" }
            cursor.getString(0)
        }
    }

    /** Create the latest schema for a fresh installation. */
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE sessions(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, title TEXT)")
        db.execSQL("CREATE TABLE messages(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)")
        db.execSQL("CREATE INDEX idx_messages_session_time ON messages(session_id, created_at)")
        db.execSQL("CREATE TABLE artifacts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, name TEXT NOT NULL, mime_type TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL)")
        db.execSQL("CREATE INDEX idx_artifacts_session ON artifacts(session_id, created_at)")
        db.execSQL("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execSQL("CREATE TABLE changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, session_id TEXT, changed_at TEXT NOT NULL)")
        db.execSQL("CREATE INDEX idx_changes_session_seq ON changes(session_id, seq)")
        db.insertOrThrow("meta", null, ContentValues().apply {
            put("key", "node_id")
            put("value", UUID.randomUUID().toString())
        })
    }

    /** Upgrade v0.1-era local data by adding v0.2 cursor metadata in place. */
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL("CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, session_id TEXT, changed_at TEXT NOT NULL)")
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_changes_session_seq ON changes(session_id, seq)")
            db.execSQL("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.insertWithOnConflict("meta", null, ContentValues().apply {
                put("key", "node_id")
                put("value", UUID.randomUUID().toString())
            }, SQLiteDatabase.CONFLICT_IGNORE)
        }
    }

    /** Append one immutable message and record it in the local change sequence. */
    @Synchronized
    fun addMessage(
        sessionId: String,
        role: String,
        content: String,
        id: String = UUID.randomUUID().toString(),
        createdAt: String = Instant.now().toString(),
    ): String {
        require(role in setOf("system", "user", "assistant", "tool")) { "Unsupported role: $role" }
        val db = writableDatabase
        db.beginTransaction()
        try {
            ensureSession(db, sessionId, createdAt)
            val inserted = db.insertWithOnConflict("messages", null, ContentValues().apply {
                put("id", id)
                put("session_id", sessionId)
                put("role", role)
                put("content", content)
                put("created_at", createdAt)
            }, SQLiteDatabase.CONFLICT_IGNORE)
            db.execSQL("UPDATE sessions SET updated_at = ? WHERE id = ?", arrayOf(createdAt, sessionId))
            if (inserted != -1L) recordChange(db, "message", id, sessionId, createdAt)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return id
    }

    /** Return the latest messages in chronological prompt order. */
    @Synchronized
    fun history(sessionId: String, limit: Int = 20): List<ShuFuMessage> {
        if (limit <= 0) return emptyList()
        val messages = mutableListOf<ShuFuMessage>()
        readableDatabase.rawQuery(
            "SELECT id, session_id, role, content, created_at FROM (SELECT rowid AS ordering, id, session_id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?) ORDER BY created_at ASC, ordering ASC",
            arrayOf(sessionId, limit.toString()),
        ).use { cursor ->
            while (cursor.moveToNext()) messages += cursor.toMessage()
        }
        return messages
    }

    /** Store bytes by digest while retaining a session-specific artifact record. */
    @Synchronized
    fun addArtifact(
        sessionId: String,
        name: String,
        mimeType: String,
        content: ByteArray,
        id: String = UUID.randomUUID().toString(),
        createdAt: String = Instant.now().toString(),
    ): JSONObject {
        val digest = sha256(content)
        val target = File(artifactDirectory, digest)
        if (!target.exists()) target.writeBytes(content)
        val db = writableDatabase
        db.beginTransaction()
        try {
            ensureSession(db, sessionId, createdAt)
            val inserted = db.insertWithOnConflict("artifacts", null, ContentValues().apply {
                put("id", id)
                put("session_id", sessionId)
                put("name", File(name).name)
                put("mime_type", mimeType)
                put("sha256", digest)
                put("size", content.size)
                put("created_at", createdAt)
            }, SQLiteDatabase.CONFLICT_IGNORE)
            if (inserted != -1L) recordChange(db, "artifact", id, sessionId, createdAt)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return JSONObject()
            .put("id", id)
            .put("session_id", sessionId)
            .put("name", File(name).name)
            .put("mime_type", mimeType)
            .put("sha256", digest)
            .put("size", content.size)
            .put("created_at", createdAt)
    }

    /**
     * Export a complete bundle or resolve changes after [after] to full records.
     * Sending immutable records rather than patches keeps imports idempotent.
     */
    @Synchronized
    fun exportBundle(sessionId: String? = null, after: Long = 0): MemoryBundle {
        val db = readableDatabase
        val sessions = JSONArray()
        val messages = JSONArray()
        val artifacts = JSONArray()

        if (after <= 0) {
            querySessions(db, sessionId).forEach(sessions::put)
            queryMessages(db, sessionId).forEach(messages::put)
            queryArtifacts(db, sessionId).forEach { artifacts.put(withContent(it)) }
        } else {
            val sessionIds = linkedSetOf<String>()
            val messageIds = linkedSetOf<String>()
            val artifactIds = linkedSetOf<String>()
            val args = mutableListOf(after.toString())
            val where = if (sessionId == null) "seq > ?" else "seq > ? AND session_id = ?".also { args += sessionId }
            db.rawQuery("SELECT entity_type, entity_id, session_id FROM changes WHERE $where ORDER BY seq", args.toTypedArray()).use { cursor ->
                while (cursor.moveToNext()) {
                    cursor.getString(2)?.let(sessionIds::add)
                    when (cursor.getString(0)) {
                        "message" -> messageIds += cursor.getString(1)
                        "artifact" -> artifactIds += cursor.getString(1)
                    }
                }
            }
            sessionIds.mapNotNull { queryOne(db, "sessions", it) }.forEach(sessions::put)
            messageIds.mapNotNull { queryOne(db, "messages", it) }.forEach(messages::put)
            artifactIds.mapNotNull { queryOne(db, "artifacts", it) }.forEach { artifacts.put(withContent(it)) }
        }

        return MemoryBundle.fromJson(
            JSONObject()
                .put("schema_version", 2)
                .put("bundle_id", UUID.randomUUID().toString())
                .put("source_node_id", nodeId)
                .put("after", after)
                .put("cursor", currentCursor(sessionId))
                .put("exported_at", Instant.now().toString())
                .put("sessions", sessions)
                .put("messages", messages)
                .put("artifacts", artifacts)
        )
    }

    /**
     * Import Schema 1/2 data transactionally and verify every artifact digest.
     * Existing IDs win; automatic conflict overwrites are intentionally avoided.
     */
    @Synchronized
    fun importBundle(bundle: MemoryBundle): SyncResult {
        require(bundle.schemaVersion in 1..2) { "Unsupported bundle schema ${bundle.schemaVersion}" }
        var sessionCount = 0
        var messageCount = 0
        var artifactCount = 0
        val db = writableDatabase
        db.beginTransaction()
        try {
            val sessions = bundle.json.getJSONArray("sessions")
            for (i in 0 until sessions.length()) {
                val item = sessions.getJSONObject(i)
                val id = item.getString("id")
                val inserted = db.insertWithOnConflict("sessions", null, ContentValues().apply {
                    put("id", id)
                    put("created_at", item.optString("created_at", Instant.now().toString()))
                    put("updated_at", item.optString("updated_at", Instant.now().toString()))
                    if (!item.isNull("title")) put("title", item.optString("title"))
                }, SQLiteDatabase.CONFLICT_IGNORE)
                if (inserted != -1L) {
                    sessionCount++
                    recordChange(db, "session", id, id, item.optString("updated_at", Instant.now().toString()))
                }
            }
            val messages = bundle.json.getJSONArray("messages")
            for (i in 0 until messages.length()) {
                val item = messages.getJSONObject(i)
                val session = item.getString("session_id")
                ensureSession(db, session, item.getString("created_at"))
                val inserted = db.insertWithOnConflict("messages", null, ContentValues().apply {
                    put("id", item.getString("id"))
                    put("session_id", session)
                    put("role", item.getString("role"))
                    put("content", item.getString("content"))
                    put("created_at", item.getString("created_at"))
                }, SQLiteDatabase.CONFLICT_IGNORE)
                if (inserted != -1L) {
                    messageCount++
                    recordChange(db, "message", item.getString("id"), session, item.getString("created_at"))
                }
            }
            val artifacts = bundle.json.getJSONArray("artifacts")
            for (i in 0 until artifacts.length()) {
                val item = artifacts.getJSONObject(i)
                val content = Base64.decode(item.getString("content_base64"), Base64.DEFAULT)
                require(sha256(content) == item.getString("sha256")) { "Artifact hash mismatch: ${item.getString("id")}" }
                val digest = item.getString("sha256")
                val target = File(artifactDirectory, digest)
                if (!target.exists()) target.writeBytes(content)
                val session = item.getString("session_id")
                ensureSession(db, session, item.getString("created_at"))
                val inserted = db.insertWithOnConflict("artifacts", null, ContentValues().apply {
                    put("id", item.getString("id"))
                    put("session_id", session)
                    put("name", item.getString("name"))
                    put("mime_type", item.getString("mime_type"))
                    put("sha256", digest)
                    put("size", item.getLong("size"))
                    put("created_at", item.getString("created_at"))
                }, SQLiteDatabase.CONFLICT_IGNORE)
                if (inserted != -1L) {
                    artifactCount++
                    recordChange(db, "artifact", item.getString("id"), session, item.getString("created_at"))
                }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return SyncResult(sessionCount, messageCount, artifactCount, bundle.cursor)
    }

    private fun ensureSession(db: SQLiteDatabase, sessionId: String, timestamp: String) {
        val inserted = db.insertWithOnConflict("sessions", null, ContentValues().apply {
            put("id", sessionId)
            put("created_at", timestamp)
            put("updated_at", timestamp)
        }, SQLiteDatabase.CONFLICT_IGNORE)
        if (inserted != -1L) recordChange(db, "session", sessionId, sessionId, timestamp)
    }

    private fun recordChange(db: SQLiteDatabase, type: String, id: String, sessionId: String?, time: String) {
        db.insertOrThrow("changes", null, ContentValues().apply {
            put("entity_type", type)
            put("entity_id", id)
            put("session_id", sessionId)
            put("changed_at", time)
        })
    }

    private fun currentCursor(sessionId: String?): Long {
        val query = if (sessionId == null) "SELECT COALESCE(MAX(seq), 0) FROM changes" else "SELECT COALESCE(MAX(seq), 0) FROM changes WHERE session_id = ?"
        val args = if (sessionId == null) null else arrayOf(sessionId)
        return readableDatabase.rawQuery(query, args).use { cursor -> cursor.moveToFirst(); cursor.getLong(0) }
    }

    private fun querySessions(db: SQLiteDatabase, sessionId: String?): List<JSONObject> = queryTable(
        db, "sessions", listOf("id", "created_at", "updated_at", "title"), sessionId
    )

    private fun queryMessages(db: SQLiteDatabase, sessionId: String?): List<JSONObject> = queryTable(
        db, "messages", listOf("id", "session_id", "role", "content", "created_at"), sessionId
    )

    private fun queryArtifacts(db: SQLiteDatabase, sessionId: String?): List<JSONObject> = queryTable(
        db, "artifacts", listOf("id", "session_id", "name", "mime_type", "sha256", "size", "created_at"), sessionId
    )

    private fun queryTable(db: SQLiteDatabase, table: String, columns: List<String>, sessionId: String?): List<JSONObject> {
        val selection = if (sessionId == null) null else if (table == "sessions") "id = ?" else "session_id = ?"
        val args = if (sessionId == null) null else arrayOf(sessionId)
        val result = mutableListOf<JSONObject>()
        db.query(table, columns.toTypedArray(), selection, args, null, null, "created_at ASC").use { cursor ->
            while (cursor.moveToNext()) result += cursor.toJson(columns)
        }
        return result
    }

    private fun queryOne(db: SQLiteDatabase, table: String, id: String): JSONObject? {
        val columns = when (table) {
            "sessions" -> listOf("id", "created_at", "updated_at", "title")
            "messages" -> listOf("id", "session_id", "role", "content", "created_at")
            else -> listOf("id", "session_id", "name", "mime_type", "sha256", "size", "created_at")
        }
        return db.query(table, columns.toTypedArray(), "id = ?", arrayOf(id), null, null, null).use { cursor ->
            if (cursor.moveToFirst()) cursor.toJson(columns) else null
        }
    }

    private fun withContent(metadata: JSONObject): JSONObject {
        val content = File(artifactDirectory, metadata.getString("sha256")).readBytes()
        return JSONObject(metadata.toString()).put("content_base64", Base64.encodeToString(content, Base64.NO_WRAP))
    }

    private fun Cursor.toMessage() = ShuFuMessage(
        id = getString(0),
        sessionId = getString(1),
        role = getString(2),
        content = getString(3),
        createdAt = getString(4),
    )

    private fun Cursor.toJson(columns: List<String>): JSONObject = JSONObject().also { json ->
        columns.forEachIndexed { index, name ->
            if (isNull(index)) json.put(name, JSONObject.NULL)
            else if (getType(index) == Cursor.FIELD_TYPE_INTEGER) json.put(name, getLong(index))
            else json.put(name, getString(index))
        }
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }
}
