package work.day.app.data.platform

import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import work.day.app.domain.model.ResearchItem

/**
 * «Ресурсы YouTube» для генерации: только чтение публичной статистики через YouTube Data API v3.
 *
 * Два запроса на одну нишу:
 *   search.list  — что сейчас набирает просмотры в нише (стоит 100 единиц квоты);
 *   videos.list  — по найденным id: длительность, просмотры, лайки, licensedContent (1 единица).
 *
 * Поэтому ответ кэшируется в [GenerationState] на 6 часов: жечь дневную квоту на каждый
 * тап «Сгенерировать» нельзя. Никаких чужих роликов не скачиваем и не перекладываем —
 * отсюда берётся только структура и цифры.
 */
class YouTubeResearch(private val json: Json = Json { ignoreUnknownKeys = true }) {

    class Error(message: String) : Exception(message)

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .build()

    suspend fun fetch(
        apiKey: String,
        query: String,
        regionCode: String = "RU",
        days: Int = 30,
        maxResults: Int = 12,
    ): Result<List<ResearchItem>> = withContext(Dispatchers.IO) {
        runCatching {
            require(apiKey.isNotBlank()) { "Нужен ключ YouTube Data API (в настройках) или вход через Google" }
            val ids = search(apiKey, query, regionCode, days, maxResults)
            if (ids.isEmpty()) emptyList() else details(apiKey, ids)
        }
    }

    private fun search(apiKey: String, query: String, regionCode: String, days: Int, maxResults: Int): List<String> {
        val url = buildString {
            append("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video")
            append("&q=").append(enc(query))
            append("&order=viewCount")
            append("&publishedAfter=").append(enc(sinceIso(days)))
            if (regionCode.isNotBlank()) append("&regionCode=").append(enc(regionCode))
            append("&maxResults=").append(maxResults.coerceIn(5, 25))
            append("&key=").append(enc(apiKey))
        }
        val root = json.parseToJsonElement(get(url)).jsonObject
        return root["items"]?.jsonArray?.mapNotNull { element ->
            element.jsonObject["id"]?.jsonObject?.get("videoId")?.jsonPrimitive?.content
        }.orEmpty()
    }

    private fun details(apiKey: String, ids: List<String>): List<ResearchItem> {
        if (ids.isEmpty()) return emptyList()
        val url = "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails" +
            "&id=" + enc(ids.joinToString(",")) + "&key=" + enc(apiKey)
        val root = json.parseToJsonElement(get(url)).jsonObject
        return root["items"]?.jsonArray?.mapNotNull { element ->
            val item = element.jsonObject
            val snippet = item["snippet"]?.jsonObject ?: return@mapNotNull null
            val stats = item["statistics"]?.jsonObject
            val content = item["contentDetails"]?.jsonObject
            ResearchItem(
                videoId = item["id"]?.jsonPrimitive?.content.orEmpty(),
                title = snippet["title"]?.jsonPrimitive?.content.orEmpty(),
                channelTitle = snippet["channelTitle"]?.jsonPrimitive?.content.orEmpty(),
                publishedAt = snippet["publishedAt"]?.jsonPrimitive?.content.orEmpty(),
                views = stats?.get("viewCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
                likes = stats?.get("likeCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
                comments = stats?.get("commentCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
                durationSec = ResearchItem.parseDuration(content?.get("duration")?.jsonPrimitive?.content.orEmpty()),
                licensed = content?.get("licensedContent")?.jsonPrimitive?.content?.toBooleanStrictOrNull() ?: false,
            )
        }.orEmpty()
    }

    private fun get(url: String): String {
        val request = Request.Builder().url(url).get().build()
        http.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val reason = json.parseToJsonElement(body.safeJson())
                    .jsonObject["error"]?.jsonObject?.get("message")?.jsonPrimitive?.content
                throw Error(reason ?: "YouTube Data API ответил ${response.code}")
            }
            return body
        }
    }

    /** Ответ может быть не-JSON (прокси, HTML-ошибка) — не падаем в парсере. */
    private fun String.safeJson(): String = if (trimStart().startsWith("{")) this else """{"error":{"message":"не-JSON ответ"}}"""

    private fun sinceIso(days: Int): String {
        val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        calendar.add(Calendar.DAY_OF_YEAR, -days.coerceIn(1, 365))
        return SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }
            .format(calendar.time)
    }

    private fun enc(value: String): String =
        java.net.URLEncoder.encode(value, "UTF-8").replace("+", "%20")
}
