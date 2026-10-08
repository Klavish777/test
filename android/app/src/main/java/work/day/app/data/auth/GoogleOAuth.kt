package work.day.app.data.auth

import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import work.day.app.domain.model.AuthProvider
import work.day.app.domain.model.ProviderLink

/**
 * Google OAuth 2.0 для публичного Android-клиента: authorization code + PKCE, редирект
 * на кастомную схему приложения. Клиентский секрет не используется — это штатный режим
 * для installed app (в консоли тип клиента «Android» или «Web» без секрета для PKCE).
 *
 * Scope только на чтение: youtube.readonly + yt-analytics.readonly. Прав на публикацию
 * приложение не запрашивает принципиально.
 */
class GoogleOAuth {

    companion object {
        const val AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
        const val TOKEN_URL = "https://oauth2.googleapis.com/token"
        const val REVOKE_URL = "https://oauth2.googleapis.com/revoke"
        const val USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
        const val YOUTUBE_CHANNELS = "https://www.googleapis.com/youtube/v3/channels"

        val SCOPES: List<String> = listOf(
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
        )
    }

    fun authorizeUrl(clientId: String, redirectUri: String, challenge: String, state: String): String =
        Urls.build(
            AUTHORIZE_URL,
            mapOf(
                "client_id" to clientId,
                "redirect_uri" to redirectUri,
                "response_type" to "code",
                "scope" to SCOPES.joinToString(" "),
                "code_challenge" to challenge,
                "code_challenge_method" to "S256",
                "state" to state,
                // access_type=offline + prompt=consent — иначе Google не отдаёт refresh_token
                "access_type" to "offline",
                "prompt" to "consent select_account",
            ),
        )

    suspend fun exchange(code: String, clientId: String, redirectUri: String, verifier: String): TokenResponse {
        val body = OAuthHttp.postForm(
            TOKEN_URL,
            mapOf(
                "code" to code,
                "client_id" to clientId,
                "redirect_uri" to redirectUri,
                "grant_type" to "authorization_code",
                "code_verifier" to verifier,
            ),
        )
        return TokenResponse.parse(AuthProvider.GOOGLE, body)
    }

    suspend fun refresh(clientId: String, refreshToken: String): TokenResponse {
        val body = OAuthHttp.postForm(
            TOKEN_URL,
            mapOf(
                "refresh_token" to refreshToken,
                "client_id" to clientId,
                "grant_type" to "refresh_token",
            ),
        )
        return TokenResponse.parse(AuthProvider.GOOGLE, body)
    }

    suspend fun profile(accessToken: String): ProviderLink {
        val info = OAuthHttp.getJson(USERINFO_URL, accessToken)
        return ProviderLink(
            provider = AuthProvider.GOOGLE,
            subject = info["sub"]?.jsonPrimitive?.content.orEmpty(),
            email = info["email"]?.jsonPrimitive?.content.orEmpty(),
            displayName = info["name"]?.jsonPrimitive?.content ?: info["given_name"]?.jsonPrimitive?.content.orEmpty(),
            avatarUrl = info["picture"]?.jsonPrimitive?.content.orEmpty(),
            scopes = SCOPES,
        )
    }

    /** Канал автора по токену: mine=true вместо ручного ID канала. */
    suspend fun myChannel(accessToken: String): GoogleChannel? {
        val url = "$YOUTUBE_CHANNELS?part=snippet,statistics&mine=true"
        val root = runCatching { OAuthHttp.getJson(url, accessToken) }.getOrNull() ?: return null
        val item = root?.get("items")?.jsonArray?.firstOrNull()?.jsonObject ?: return null
        val stats = item["statistics"]?.jsonObject
        val snippet = item["snippet"]?.jsonObject
        return GoogleChannel(
            channelId = item["id"]?.jsonPrimitive?.content.orEmpty(),
            title = snippet?.get("title")?.jsonPrimitive?.content.orEmpty(),
            subscribers = stats?.get("subscriberCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
            views = stats?.get("viewCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
            videos = stats?.get("videoCount")?.jsonPrimitive?.content?.toLongOrNull() ?: 0L,
        )
    }

    suspend fun revoke(accessToken: String) = runCatching { OAuthHttp.postForm(REVOKE_URL, mapOf("token" to accessToken)) }

    data class GoogleChannel(
        val channelId: String,
        val title: String,
        val subscribers: Long,
        val views: Long,
        val videos: Long,
    )
}
