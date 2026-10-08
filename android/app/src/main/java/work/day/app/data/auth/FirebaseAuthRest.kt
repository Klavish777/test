package work.day.app.data.auth

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.json.JSONObject

/**
 * Firebase Authentication по REST (Identity Toolkit). Нужен только API-ключ проекта Firebase —
 * SDK и google-services.json не требуются, поэтому приложение остаётся без привязки к Google Services.
 *
 * Нет проекта Firebase? Тогда используется локальный аккаунт на устройстве (PasswordHasher),
 * и выбор режима автоматический: есть ключ — Firebase, нет — локально.
 */
class FirebaseAuthRest(private val apiKeyProvider: () -> String) {

    private val json = Json { ignoreUnknownKeys = true }

    class AuthError(message: String) : Exception(message)

    data class FirebaseUser(
        val idToken: String,
        val localId: String,
        val email: String,
        val refreshToken: String,
        val expiresIn: Long,
    )

    suspend fun signUp(email: String, password: String): FirebaseUser =
        post("signUp", JSONObject()
            .put("email", email.trim())
            .put("password", password)
            .put("returnSecureToken", true)
            .toString())

    suspend fun signIn(email: String, password: String): FirebaseUser =
        post("signInWithPassword", JSONObject()
            .put("email", email.trim())
            .put("password", password)
            .put("returnSecureToken", true)
            .toString())

    suspend fun refresh(refreshToken: String): FirebaseUser =
        post(
            "token",
            JSONObject().put("grant_type", "refresh_token").put("refresh_token", refreshToken).toString(),
            keyInBody = false,
        )

    suspend fun sendVerification(idToken: String) =
        postRaw("sendOobCode", JSONObject().put("requestType", "VERIFY_EMAIL").put("idToken", idToken).toString())

    suspend fun sendReset(email: String): Boolean = runCatching {
        postRaw("sendPasswordReset", JSONObject().put("request", email.trim()).toString())
    }.isSuccess

    private suspend fun post(action: String, body: String, keyInBody: Boolean = true): FirebaseUser =
        parse(postRaw(action, body, keyInBody))

    private suspend fun postRaw(action: String, body: String, keyInBody: Boolean = true): String {
        val key = apiKeyProvider()
        if (key.isBlank()) throw AuthError("Firebase API key не задан")
        val url = if (action == "token") {
            "https://securetoken.googleapis.com/v1/token?key=$key"
        } else {
            "https://identitytoolkit.googleapis.com/v1/accounts:$action?key=$key"
        }
        val text = OAuthHttp.postJson(url, body)
        // В error-ответе Firebase кладёт причину в {"error":{"message":"EMAIL_NOT_FOUND"}}
        val root = runCatching { json.parseToJsonElement(text).jsonObject["error"]?.jsonObject?.get("message")?.jsonPrimitive?.content }
            .getOrNull()
        if (!root.isNullOrBlank()) throw AuthError(humanize(root))
        return text
    }

    private fun parse(text: String): FirebaseUser {
        val root = json.parseToJsonElement(text).jsonObject
        return FirebaseUser(
            idToken = root["id_token"]?.jsonPrimitive?.content
                ?: root["idToken"]?.jsonPrimitive?.content
                ?: throw AuthError("Firebase не вернул id_token"),
            localId = root["localId"]?.jsonPrimitive?.content.orEmpty(),
            email = root["email"]?.jsonPrimitive?.content.orEmpty(),
            refreshToken = root["refresh_token"]?.jsonPrimitive?.content
                ?: root["refreshToken"]?.jsonPrimitive?.content.orEmpty(),
            expiresIn = root["expires_in"]?.jsonPrimitive?.content?.toLongOrNull() ?: 3600L,
        )
    }

    private fun humanize(code: String): String = when {
        code.contains("EMAIL_EXISTS") -> "Такой email уже зарегистрирован"
        code.contains("INVALID_EMAIL") -> "Проверь формат почты"
        code.contains("WEAK_PASSWORD") -> "Пароль слишком простой: минимум 6 символов"
        code.contains("EMAIL_NOT_FOUND") -> "Аккаунт с такой почтой не найден"
        code.contains("INVALID_LOGIN_CREDENTIALS") || code.contains("PASSWORD_DOES_NOT_MATCH") -> "Неверный пароль"
        code.contains("TOO_MANY") -> "Слишком много попыток, подожди минуту"
        code.contains("NETWORK") -> "Нет сети для обращения к Firebase"
        else -> code
    }
}
