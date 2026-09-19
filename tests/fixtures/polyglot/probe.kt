// Kotlin's quarter of the probe tree: a way in, a boundary, a loop and a branch.

package probe

import java.io.File

const val RETRIES = 3

data class Setting(
    val key: String,
    val value: String,
)

/** Read a config file, one line at a time. */
fun loadConfig(path: String): List<Setting> {
    val out = mutableListOf<Setting>()
    val file = File(path)
    if (!file.exists()) {
        return out
    }
    for (line in file.readLines()) {
        if (!line.contains("=")) {
            continue
        }
        val parts = line.split("=", limit = 2)
        out.add(Setting(parts[0].trim(), parts[1].trim()))
    }
    return out
}

private fun root(): String = System.getenv("PROBE_ROOT") ?: "."

fun main() {
    val settings = loadConfig("${root()}/probe.cfg")
    println("${settings.size} settings")
}
