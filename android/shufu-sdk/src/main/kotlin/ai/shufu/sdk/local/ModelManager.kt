package ai.shufu.sdk.local

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import java.io.File
import java.net.HttpURLConnection
import java.net.URI
import java.security.MessageDigest

/** Metadata for one GGUF file kept in the application's private directory. */
data class ManagedModel(
    val file: File,
    val sha256: String,
    val size: Long,
)

/**
 * Imports, downloads, verifies, and enumerates user-provided GGUF files.
 *
 * Models are never bundled or loaded automatically. Writes use a `.part` file
 * so a failed transfer cannot replace a previously usable model.
 */
class ModelManager(context: Context) {
    private val directory = File(context.applicationContext.filesDir, "shufu/models").apply { mkdirs() }

    fun list(): List<ManagedModel> = directory.listFiles()
        .orEmpty()
        .filter { it.isFile && it.extension.equals("gguf", ignoreCase = true) }
        .sortedBy { it.name }
        .map { ManagedModel(it, sha256(it), it.length()) }

    fun importFromUri(resolver: ContentResolver, uri: Uri, fileName: String): ManagedModel {
        require(fileName.lowercase().endsWith(".gguf")) { "Local model must use .gguf" }
        val target = safeTarget(fileName)
        val partial = File(directory, "${target.name}.part")
        resolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "Unable to open selected model" }
            partial.outputStream().use(input::copyTo)
        }
        replace(partial, target)
        return ManagedModel(target, sha256(target), target.length())
    }

    fun download(url: String, fileName: String, expectedSha256: String? = null): ManagedModel {
        require(url.startsWith("https://") || url.startsWith("http://")) { "Model URL must use HTTP(S)" }
        val target = safeTarget(fileName)
        val partial = File(directory, "${target.name}.part")
        val connection = URI.create(url).toURL().openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 15_000
            connection.readTimeout = 120_000
            connection.instanceFollowRedirects = true
            require(connection.responseCode in 200..299) { "Model download failed: HTTP ${connection.responseCode}" }
            connection.inputStream.use { input -> partial.outputStream().use(input::copyTo) }
        } finally {
            connection.disconnect()
        }
        val digest = sha256(partial)
        if (expectedSha256 != null && !digest.equals(expectedSha256, ignoreCase = true)) {
            partial.delete()
            throw IllegalArgumentException("Model SHA-256 mismatch")
        }
        replace(partial, target)
        return ManagedModel(target, digest, target.length())
    }

    private fun safeTarget(fileName: String): File {
        // Requiring a single basename prevents traversal outside app-private storage.
        val baseName = File(fileName).name
        require(baseName == fileName && baseName.lowercase().endsWith(".gguf")) { "Invalid model file name" }
        return File(directory, baseName)
    }

    private fun replace(source: File, target: File) {
        if (target.exists() && !target.delete()) error("Unable to replace ${target.name}")
        if (!source.renameTo(target)) {
            source.copyTo(target, overwrite = true)
            source.delete()
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
