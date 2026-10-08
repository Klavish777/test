package work.day.app.data.platform

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import work.day.app.domain.model.ChannelProfile

data class YouTubeChannelStats(
    val channelId: String,
    val title: String,
    val subscribers: Long,
    val views: Long,
    val videos: Long,
)

/**
 * Только чтение: YouTube Data API v3 (публичная статистика канала).
 * Никаких записей и действий от имени автора — права ключа только на чтение.
 */
class YouTubeDataApi(private val json: Json = Json { ignoreUnknownKeys = true }) {

    class Error(message: String) : Exception(message)

    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .build()

    suspend fun fetchChannelStats(
        apiKey: String,
        channelId: String,
        accessToken: String? = null,
    ): Result<YouTubeChannelStats> =
        withContext(Dispatchers.IO) {
            runCatching {
                val token = accessToken?.trim()?.takeIf { it.isNotEmpty() }
                require(token != null || apiKey.isNotBlank()) { "Нужен вход через Google или ключ YouTube Data API" }
                val mine = token != null && channelId.isBlank()
                require(mine || channelId.isNotBlank()) { "Нужен ID канала" }
                val query = if (mine) "part=statistics,snippet&mine=true" else "part=statistics,snippet&id=$channelId"
                val withKey = if (token == null) "$query&key=$apiKey" else query
                val url = "https://www.googleapis.com/youtube/v3/channels?$withKey"
                val request = Request.Builder().url(url).apply {
                    if (token != null) header("Authorization", "Bearer $token")
                }.build()
                val response = http.newCall(request).execute()
                val text = response.use { it.body?.string().orEmpty() }
                if (!response.isSuccessful) throw Error("YouTube API ${response.code}: ${text.take(200)}")
                parseChannel(text) ?: throw Error("Канал не найден — проверь ID")
            }
        }

    private fun parseChannel(body: String): YouTubeChannelStats? {
        val items = json.parseToJsonElement(body).jsonObject["items"]?.jsonArray ?: return null
        val item = items.firstOrNull()?.jsonObject ?: return null
        val stats = item["statistics"]?.jsonObject
        val snippet = item["snippet"]?.jsonObject
        return YouTubeChannelStats(
            channelId = item["id"]?.jsonPrimitive?.content.orEmpty(),
            title = snippet?.get("title")?.jsonPrimitive?.content.orEmpty(),
            subscribers = stats?.get("subscriberCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
            views = stats?.get("viewCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
            videos = stats?.get("videoCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
        )
    }

    fun applyTo(stats: YouTubeChannelStats, profile: ChannelProfile): ChannelProfile = profile.copy(
        youtubeChannelId = stats.channelId.ifBlank { profile.youtubeChannelId },
        youtubeTitle = stats.title.ifBlank { profile.youtubeTitle },
        youtubeSubscribers = stats.subscribers,
    )
}
