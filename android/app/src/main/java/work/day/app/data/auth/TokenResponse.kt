package work.day.app.data.auth

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import work.day.app.domain.model.AuthProvider

/** Ответ эндпоинта обмена кода на токены. Разбор общий: у Google и TikTok поля почти совпадают. */
data class TokenResponse(
    val provider: AuthProvider,
    val accessToken: String,
    val refreshToken: String?,
    val expiresInSec: Long,
    val scope: String,
    val idToken: String?,
    val raw: JsonObject,
) {
    /** 0 значит «токен не ограниченный по времени» (локальный аккаунт, id_token без expires_in). */
    val expiresAt: Long get() = if (expiresInSec > 0) System.currentTimeMillis() + expiresInSec * 1000 else 0L

    class ParseException(message: String, body: String) : Exception("$message · ${body.take(240)}")

    companion object {
        private val json = Json { ignoreUnknownKeys = true; isLenient = true }

        fun parse(provider: AuthProvider, body: String): TokenResponse {
            val root = runCatching { json.parseToJsonElement(body).jsonObject }
                .getOrElse { throw ParseException("ответ не JSON", body) }

            root["error"]?.jsonPrimitive?.content?.let { code ->
                val description = root["error_description"]?.jsonPrimitive?.content
                    ?: root["error_description"]?.jsonObject?.get("message")?.jsonPrimitive?.content
                    ?: root["message"]?.jsonPrimitive?.content
                    .orEmpty()
                throw ParseException(listOf(code, description).filter { it.isNotBlank() }.joinToString(" "), body)
            }

            // TikTok v2 заворачивает полезную нагрузку в {"data": { ... }}
            val data = if (provider == AuthProvider.TIKTOK) root["data"]?.jsonObject ?: root else root
            val token = data["access_token"]?.jsonPrimitive?.content
                ?: throw ParseException("в ответе нет access_token", body)

            return TokenResponse(
                provider = provider,
                accessToken = token,
                refreshToken = data["refresh_token"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() },
                expiresInSec = data["expires_in"]?.jsonPrimitive?.longOrNull
                    ?: data["expires_in"]?.jsonPrimitive?.intOrNull?.toLong()
                    ?: 0L,
                scope = data["scope"]?.jsonPrimitive?.content.orEmpty(),
                idToken = data["id_token"]?.jsonPrimitive?.content,
                raw = data,
            )
        }
    }
}
