package work.day.app.domain.model

import kotlinx.serialization.Serializable

@Serializable
enum class AuthProvider(val label: String, val what: String) {
    @kotlinx.serialization.SerialName("google") GOOGLE(
        "Google",
        "YouTube и Shorts: название канала, подписчики, просмотры, удержание и источники трафика. " +
            "Права только на чтение.",
    ),
    @kotlinx.serialization.SerialName("tiktok") TIKTOK(
        "TikTok",
        "TikTok Studio: Followers, Likes, Videos и список роликов. Доступ зависит от того, какие scope " +
            "одобрили твоему приложению в TikTok for Developers.",
    ),
    @kotlinx.serialization.SerialName("password") PASSWORD(
        "Логин и пароль",
        "Аккаунт Work Day: защищает приложение на устройстве и (при подключённом Firebase) переносит " +
            "настройки между устройствами.",
    );

    companion object {
        fun byName(name: String): AuthProvider? = entries.firstOrNull { it.name.equals(name, ignoreCase = true) }
    }
}

/** Привязанный провайдер. subject — стабильный id пользователя у провайдера. */
@Serializable
data class ProviderLink(
    val provider: AuthProvider,
    val subject: String = "",
    val email: String = "",
    val displayName: String = "",
    val avatarUrl: String = "",
    val scopes: List<String> = emptyList(),
    /** Абсолютное время жизни access-токена (System.currentTimeMillis), 0 — не истекает. */
    val expiresAt: Long = 0L,
    val canRefresh: Boolean = false,
    val connectedAt: Long = 0L,
    val followers: Long = 0L,
) {
    val isExpired: Boolean get() = expiresAt > 0 && expiresAt - CLOCK_SKEW_MS < System.currentTimeMillis()
    val needsAttention: Boolean get() = isExpired && !canRefresh
    val title: String get() = displayName.ifBlank { email.ifBlank { provider.label } }

    companion object {
        private const val CLOCK_SKEW_MS = 60_000L
    }
}

/** Состояние входа в приложение. Гостевой режим разрешён: без площадок агенты всё равно работают. */
@Serializable
data class Session(
    val links: List<ProviderLink> = emptyList(),
    val guestMode: Boolean = false,
    val lockEnabled: Boolean = false,
    val email: String = "",
    /** Локальный пароль: соль и хеш PBKDF2. Сам пароль не храним нигде. */
    val passwordSalt: String = "",
    val passwordHash: String = "",
    val authBackend: AuthBackend = AuthBackend.LOCAL,
) {
    val hasPassword: Boolean get() = passwordHash.isNotBlank() && passwordSalt.isNotBlank()
    val isSignedIn: Boolean get() = links.isNotEmpty() || email.isNotBlank() || hasPassword
    fun link(provider: AuthProvider): ProviderLink? = links.firstOrNull { it.provider == provider }
    val needsAuth: Boolean get() = !isSignedIn && !guestMode
}

enum class AuthBackend { LOCAL, FIREBASE }

/** Промежуточное состояние OAuth-перехвата: что именно ждём от редиректа. */
data class PendingOAuth(
    val provider: AuthProvider,
    val verifier: String,
    val state: String,
    val startedAt: Long = System.currentTimeMillis(),
) {
    val isStale: Boolean get() = System.currentTimeMillis() - startedAt > TIMEOUT_MS

    companion object {
        const val TIMEOUT_MS = 5 * 60 * 1000L
    }
}

/** Конфигурация клиентов: что пользователь вставляет из своих консолей разработчика. */
@Serializable
data class AuthClients(
    val googleClientId: String = "",
    val tiktokClientKey: String = "",
    val tiktokClientSecret: String = "",
    val firebaseApiKey: String = "",
    /**
     * `user.info.stats` TikTok выдаёт только после ручного ревью, а запрос неодобренного
     * scope роняет всю авторизацию. Поэтому просим его лишь когда владелец приложения
     * подтвердил, что scope одобрен в консоли.
     */
    val tiktokWithStats: Boolean = false,
    val redirectUri: String = DEFAULT_REDIRECT,
) {
    val readyForGoogle: Boolean get() = googleClientId.isNotBlank()
    val readyForTikTok: Boolean get() = tiktokClientKey.isNotBlank()
    val readyForFirebase: Boolean get() = firebaseApiKey.isNotBlank()

    companion object {
        const val DEFAULT_REDIRECT = "workdayauth://oauth2callback"
    }
}
