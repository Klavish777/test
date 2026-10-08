package work.day.app.data.auth

import java.net.URLDecoder

/**
 * Мини-строитель и мини-парсер URL на чистом JVM.
 * Сделано намеренно вместо android.net.Uri: эти две функции решают за долю секунды
 * «куда ушёл code_verifier» и «совпал ли state», и они покрыты юнит-тестами,
 * которые невозможно запустить против android.net.Uri без Robolectric.
 */
object Urls {

    fun build(base: String, params: Map<String, String>): String {
        val query = params.entries
            .filter { it.value.isNotBlank() }
            .joinToString("&") { (key, value) -> "${enc(key)}=${enc(value)}" }
        return if (query.isEmpty()) base else base + (if (base.contains('?')) "&" else "?") + query
    }

    /** И query, и fragment: явный поток отдаёт code в query, implicit — в fragment. */
    fun params(uri: String): Map<String, String> {
        val marker = if (uri.contains('?')) '?' else '#'
        val raw = uri.substringAfter(marker, "")
        if (raw.isBlank()) return emptyMap()
        return raw.split('&').mapNotNull { pair ->
            val key = pair.substringBefore('=', "").trim()
            if (key.isEmpty()) null else key.decoded() to pair.substringAfter('=', "").decoded().trim()
        }.toMap()
    }

    fun firstParam(uri: String, name: String): String? = params(uri)[name]

    /** Разбирает code/state/error из редиректа и возвращает null, если это не редирект. */
    fun redirectOf(uri: String): Redirect? {
        val map = params(uri)
        if (map.isEmpty()) return null
        return Redirect(
            code = map["code"]?.takeIf { it.isNotBlank() },
            state = map["state"],
            error = map["error"]?.takeIf { it.isNotBlank() },
            errorDescription = map["error_description"],
            raw = map,
        )
    }

    data class Redirect(
        val code: String?,
        val state: String?,
        val error: String?,
        val errorDescription: String?,
        val raw: Map<String, String>,
    )

    private fun String.decoded(): String = runCatching { URLDecoder.decode(this, "UTF-8") }.getOrDefault(this)

    private fun enc(value: String): String =
        java.net.URLEncoder.encode(value, "UTF-8")
            .replace("+", "%20")
            .replace("*", "%2A")
            .replace("%7E", "~")
}
