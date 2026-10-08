package work.day.app.data.auth

import java.security.MessageDigest

/**
 * PKCE (RFC 7636) для публичного клиента: код подтверждения остаётся в приложении,
 * в браузер уходит только его SHA-256 в base64url без «=». Поэтому перехваченный
 * code без верификтора не обменивается на токен.
 */
object Pkce {

    fun verifier(): String = base64Url(PasswordHasher.randomBytes(32))

    fun challenge(verifier: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII))
        return base64Url(digest)
    }

    fun state(): String = base64Url(PasswordHasher.randomBytes(16))

    private fun base64Url(bytes: ByteArray): String =
        java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
}
