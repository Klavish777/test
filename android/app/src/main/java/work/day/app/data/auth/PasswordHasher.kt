package work.day.app.data.auth

import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * Хеш пароля: PBKDF2WithHmacSHA256, 210 000 итераций, 16-байтная соль от SecureRandom.
 * Локальный аккаунт нужен для замка на устройстве; синхронизацию между устройствами делает
 * Firebase Auth (см. FirebaseAuthRest), а не этот класс.
 */
object PasswordHasher {

    private const val ITERATIONS = 210_000
    private const val KEY_BITS = 256
    private const val SALT_BYTES = 16

    fun newSalt(): String = randomBytes(SALT_BYTES).toHex()

    fun hash(password: String, saltHex: String): String {
        require(password.isNotEmpty()) { "Пустой пароль" }
        val spec = PBEKeySpec(password.toCharArray(), saltHex.hexToBytes(), ITERATIONS, KEY_BITS)
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        return factory.generateSecret(spec).encoded.toHex()
    }

    /** Сверка без раннего выхода: время сравнения не зависит от того, где разошлось. */
    fun verify(password: String, saltHex: String, expectedHex: String): Boolean {
        if (saltHex.isBlank() || expectedHex.isBlank() || password.isEmpty()) return false
        val actual = runCatching { hash(password, saltHex) }.getOrNull() ?: return false
        return MessageDigest.isEqual(actual.toByteArray(), expectedHex.toByteArray())
    }

    fun randomBytes(size: Int): ByteArray = ByteArray(size).also { SecureRandom().nextBytes(it) }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }

    private fun String.hexToBytes(): ByteArray {
        require(length % 2 == 0 && length > 0) { "Некорректная соль" }
        return chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }
}
