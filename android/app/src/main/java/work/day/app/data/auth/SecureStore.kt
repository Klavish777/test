package work.day.app.data.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Хранилище токенов. Штатный путь — EncryptedSharedPreferences (главный ключ в Android Keystore).
 * Если KeyStore откажет (нестандартная прошивка, ключ потерян после сброса), хранилище
 * деградирует в приватный файл приложения, а не роняет вход: приложение приватное, файлы MODE_PRIVATE.
 */
interface TokenVault {
    fun get(key: String): String?
    fun set(key: String, value: String?)
    fun remove(key: String)
    fun clear()
    fun degraded(): Boolean = false

    /** Двойник для тестов и предпросмотра: тот же контракт, никакой Android-инфраструктуры. */
    class InMemory : TokenVault {
        private val map = mutableMapOf<String, String>()
        override fun get(key: String) = map[key]
        override fun set(key: String, value: String?) {
            if (value.isNullOrBlank()) map.remove(key) else map[key] = value
        }
        override fun remove(key: String) { map.remove(key) }
        override fun clear() = map.clear()
        fun snapshot(): Map<String, String> = map.toMap()
    }
}

/**
 * Реальное хранилище: EncryptedSharedPreferences.
 */
class SecureStore(context: Context, private val scope: CoroutineScope) : TokenVault {

    override fun degraded(): Boolean = degradedFlag
    private var degradedFlag: Boolean = false

    private val prefs: SharedPreferences = runCatching {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            FILE,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }.getOrElse {
        degradedFlag = true
        context.getSharedPreferences(FILE + "_plain", Context.MODE_PRIVATE)
    }

    override fun get(key: String): String? = prefs.getString(key, null)

    override fun set(key: String, value: String?) = write { editor ->
        if (value.isNullOrBlank()) editor.remove(key) else editor.putString(key, value)
    }

    override fun remove(key: String) = write { it.remove(key) }

    override fun clear() = write { it.clear() }

    private inline fun write(crossinline block: (SharedPreferences.Editor) -> Unit) {
        scope.launch(Dispatchers.IO) { block(prefs.edit()).apply() }
    }

    object Keys {
        fun access(provider: String) = "access_$provider"
        fun refresh(provider: String) = "refresh_$provider"
        const val FIREBASE_ID_TOKEN = "firebase_id_token"
    }

    private companion object {
        const val FILE = "workday_tokens"
    }
}
