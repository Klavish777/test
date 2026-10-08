package work.day.app.data.auth

import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import work.day.app.domain.model.AuthProvider
import work.day.app.domain.model.ProviderLink

/**
 * TikTok Login Kit v2 (Open API v2). Редирект — на кастомную схему приложения, обмен кода —
 * напрямую open.tiktokapis.com с PKCE.
 *
 * Важно: client_key и redirect_uri берутся из твоего приложения в TikTok for Developers, а
 * список доступных scope определяется после ревью. app_no_review даёт user.info.basic и video.list;
 * user.info.stats (подписчики, лайки, просмотры) и любые publish-права требуют проверки.
 * Work Day права на публикацию не запрашивает вообще.
 */
class TikTokOAuth {

    companion object {
        const val AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
        const val TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
        const val USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
        const val USER_STATS_URL = "https://open.tiktokapis.com/v2/user/stats/"

        /** Что просим по умолчанию; stats добавится сам, если он одобрен в консоли. */
        val BASIC_SCOPES = listOf("user.info.basic", "video.list")
        const val STATS_SCOPE = "user.info.stats"
    }

    fun authorizeUrl(clientKey: String, redirectUri: String, challenge: String, state: String, withStats: Boolean): String {
        val scopes = if (withStats) BASIC_SCOPES + STATS_SCOPE else BASIC_SCOPES
        return Urls.build(
            AUTHORIZE_URL,
            mapOf(
                "client_key" to clientKey,
                "response_type" to "code",
                // У TikTok scope разделяются запятыми, у Google — пробелами.
                "scope" to scopes.joinToString(","),
                "redirect_uri" to redirectUri,
                "state" to state,
                "code_challenge" to challenge,
                "code_challenge_method" to "S256",
            ),
        )
    }

    suspend fun exchange(code: String, clientKey: String, clientSecret: String, redirectUri: String, verifier: String): TokenResponse =
        TokenResponse.parse(
            provider = AuthProvider.TIKTOK,
            body = OAuthHttp.postJson(TOKEN_URL, tokenBody(code, clientKey, clientSecret, redirectUri, verifier)),
        )

    private fun tokenBody(code: String, clientKey: String, clientSecret: String, redirectUri: String, verifier: String): String =
        buildString {
            append('{')
            field("client_key", clientKey); append(',')
            field("grant_type", "authorization_code"); append(',')
            field("code", code); append(',')
            field("redirect_uri", redirectUri); append(',')
            field("code_verifier", verifier)
            if (clientSecret.isNotBlank()) { append(','); field("client_secret", clientSecret) }
            append('}')
        }

    suspend fun refresh(clientKey: String, clientSecret: String, refreshToken: String): TokenResponse {
        val body = buildString {
            append('{')
            field("client_key", clientKey); append(',')
            field("grant_type", "refresh_token"); append(',')
            field("refresh_token", refreshToken)
            if (clientSecret.isNotBlank()) { append(','); field("client_secret", clientSecret) }
            append('}')
        }
        return TokenResponse.parse(AuthProvider.TIKTOK, OAuthHttp.postJson(TOKEN_URL, body))
    }

    suspend fun profile(accessToken: String): TikTokProfile {
        val fields = "open_id,union_id,avatar_url,display_name,username,bio_description"
        val root = OAuthHttp.getJson("$USER_INFO_URL?fields=$fields", accessToken)
        val user = root["data"]?.jsonObject?.get("user")?.jsonObject
        return TikTokProfile(
            openId = user?.get("open_id")?.jsonPrimitive?.content.orEmpty(),
            unionId = user?.get("union_id")?.jsonPrimitive?.content.orEmpty(),
            display = user?.get("display_name")?.jsonPrimitive?.content.orEmpty(),
            username = user?.get("username")?.jsonPrimitive?.content.orEmpty(),
            avatar = user?.get("avatar_url")?.jsonPrimitive?.content.orEmpty(),
        )
    }

    /** @return null, если scope user.info.stats не одобрен — тогда приложение честно живёт без цифр. */
    suspend fun stats(accessToken: String): TikTokStats? = runCatching {
        val root = OAuthHttp.getJson(USER_STATS_URL, accessToken)
        val viewer = root["data"]?.jsonObject?.get("viewer_stats")?.jsonObject
        TikTokStats(
            followers = viewer?.get("follower_count")?.jsonPrimitive?.longOrNull ?: 0L,
            likes = viewer?.get("likes_count")?.jsonPrimitive?.longOrNull ?: 0L,
            videos = viewer?.get("video_count")?.jsonPrimitive?.longOrNull ?: 0L,
            following = viewer?.get("following_count")?.jsonPrimitive?.longOrNull ?: 0L,
        )
    }.getOrNull()

    fun linkOf(profile: TikTokProfile, followers: Long, scopes: List<String>): ProviderLink = ProviderLink(
        provider = AuthProvider.TIKTOK,
        subject = profile.openId.ifBlank { profile.username },
        displayName = profile.display.ifBlank { "@${profile.username}" },
        avatarUrl = profile.avatar,
        email = "",
        scopes = scopes,
        followers = followers,
    )

    private fun StringBuilder.field(key: String, value: String) {
        append('"').append(key).append("\":\"")
        value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").let { append(it) }
        append('"')
    }

    data class TikTokProfile(
        val openId: String,
        val unionId: String,
        val display: String,
        val username: String,
        val avatar: String,
    )

    data class TikTokStats(val followers: Long, val likes: Long, val videos: Long, val following: Long)
}
