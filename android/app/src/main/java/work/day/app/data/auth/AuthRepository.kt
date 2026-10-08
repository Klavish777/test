package work.day.app.data.auth

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.json.JsonObject
import work.day.app.core.PersistedStore
import work.day.app.domain.model.AuthBackend
import work.day.app.domain.model.AuthClients
import work.day.app.domain.model.AuthProvider
import work.day.app.domain.model.PendingOAuth
import work.day.app.domain.model.ProviderLink
import work.day.app.domain.model.Session

/**
 * Единственное место, которое знает, вошёл ли человек и во что именно превращается этот вход.
 *
 * Разделение сознательное: сессия (email, провайдеры, scope, срок жизни токена) лежит в обычном
 * JSON-файле приложения, а сами токены — в SecureStore (Keystore). Поэтому выгрузка настроек
 * или баг-репорт секретов наружу не отдаёт.
 */
class AuthRepository(
    private val store: PersistedStore<Session>,
    private val secure: TokenVault,
    private val clients: () -> AuthClients,
    @Suppress("unused") private val scope: CoroutineScope,
) {

    private val google = GoogleOAuth()
    private val tiktok = TikTokOAuth()
    private val firebase = FirebaseAuthRest { clients().firebaseApiKey }

    private val _state = MutableStateFlow(store.value)
    val state: StateFlow<Session> = _state.asStateFlow()

    val session: Session get() = store.value.also { _state.value = it }

    /** Цифры канала из YouTube — контейнер применяет их к профилю автора. */
    var onGoogleChannel: ((GoogleOAuth.GoogleChannel) -> Unit)? = null

    private var pending: PendingOAuth? = null
    val pendingProvider: AuthProvider? get() = pending?.provider.takeUnless { pending?.isStale == true }

    // ─── вход без провайдеров ─────────────────────────────────────────────────

    fun continueAsGuest() = mutate { it.copy(guestMode = true) }

    /** Выход: сначала отзыв на стороне Google (best effort), потом локальная зачистка. */
    suspend fun signOut() {
        secure.get(SecureStore.Keys.access(AuthProvider.GOOGLE))?.let { google.revoke(it) }
        secure.clear()
        store.replace(Session())
        _state.value = store.value
    }

    /** Логин/пароль: Firebase, если задан API-ключ проекта, иначе локальный аккаунт устройства. */
    suspend fun signIn(email: String, password: String): Result<Unit> = runCatching {
        validate(email, password)
        if (clients().readyForFirebase) {
            val user = firebase.signIn(email, password)
            applyFirebase(user, email)
        } else {
            val s = store.value
            if (s.passwordHash.isBlank()) error("Аккаунта на этом устройстве нет — зарегистрируйся")
            if (!s.email.equals(email.trim(), ignoreCase = true)) error("Почта не совпадает с указанной при регистрации")
            if (!PasswordHasher.verify(password, s.passwordSalt, s.passwordHash)) error("Неверный пароль")
            mutate { it.copy(guestMode = false) }
        }
    }

    /** Регистрация: без Firebase это по сути установка пароля на приложение + привязка почты. */
    suspend fun register(email: String, password: String, confirm: String): Result<Unit> = runCatching {
        validate(email, password)
        require(password == confirm) { "Пароли не совпадают" }
        if (clients().readyForFirebase) {
            val user = firebase.signUp(email, password)
            applyFirebase(user, email)
            runCatching { firebase.sendVerification(user.idToken) }
        } else {
            val salt = PasswordHasher.newSalt()
            mutate {
                it.copy(
                    email = email.trim().lowercase(),
                    passwordSalt = salt,
                    passwordHash = PasswordHasher.hash(password, salt),
                    authBackend = AuthBackend.LOCAL,
                    guestMode = false,
                    lockEnabled = true,
                )
            }
        }
    }

    suspend fun requestPasswordReset(email: String): Result<Unit> = runCatching {
        check(clients().readyForFirebase) { "Сброс по почте доступен, когда подключён Firebase" }
        firebase.sendReset(email)
        Unit
    }

    private suspend fun applyFirebase(user: FirebaseAuthRest.FirebaseUser, email: String) {
        secure.set(SecureStore.Keys.FIREBASE_ID_TOKEN, user.idToken)
        secure.set(KEY_FIREBASE_REFRESH, user.refreshToken)
        mutate {
            it.copy(
                email = user.email.ifBlank { email }.trim().lowercase(),
                authBackend = AuthBackend.FIREBASE,
                guestMode = false,
                links = it.links.filterNot { l -> l.provider == AuthProvider.PASSWORD } + ProviderLink(
                    provider = AuthProvider.PASSWORD,
                    subject = user.localId,
                    email = user.email.ifBlank { email },
                    displayName = user.email.ifBlank { email }.substringBefore('@'),
                    scopes = listOf("firebase:identity-toolkit"),
                    expiresAt = System.currentTimeMillis() + user.expiresIn * 1000,
                    canRefresh = user.refreshToken.isNotBlank(),
                    connectedAt = System.currentTimeMillis(),
                ),
            )
        }
    }

    private fun validate(email: String, password: String) {
        require(email.contains('@') && email.length > 5) { "Нужен корректный email" }
        require(password.length >= 6) { "Пароль от 6 символов" }
    }

    // ─── замок на приложении ───────────────────────────────────────────────────

    /**
     * Разблокировка всегда сверяется локальным хешем: даже если аккаунт заведён в Firebase,
     * пароль устройства проверяется без сети. Это осознанно: в метро запрос к Firebase
     * не должен быть условием входа в собственные заметки.
     */
    fun verifyLock(password: String): Boolean {
        val s = store.value
        if (s.passwordHash.isBlank()) return true
        return PasswordHasher.verify(password, s.passwordSalt, s.passwordHash)
    }

    fun hasLockPassword(): Boolean = store.value.passwordHash.isNotBlank()

    fun setLock(enabled: Boolean, password: String? = null): Result<Unit> = runCatching {
        if (!enabled) {
            mutate { it.copy(lockEnabled = false) }
            return@runCatching
        }
        val pwd = password
        if (pwd == null) {
            check(store.value.passwordHash.isNotBlank()) { "Сначала задай пароль на экране входа" }
            mutate { it.copy(lockEnabled = true) }
        } else {
            require(pwd.length >= 6) { "Пароль от 6 символов" }
            val salt = PasswordHasher.newSalt()
            mutate {
                it.copy(passwordSalt = salt, passwordHash = PasswordHasher.hash(pwd, salt), lockEnabled = true)
            }
        }
    }

    // ─── OAuth ────────────────────────────────────────────────────────────────

    /** Готовит ссылку авторизации и запоминает верификатор PKCE + state. */
    fun beginLink(provider: AuthProvider): Result<String> = runCatching {
        require(provider != AuthProvider.PASSWORD) { "Логин и пароль — это форма, а не редирект" }
        val cfg = clients()
        val verifier = Pkce.verifier()
        val state = Pkce.state()
        pending = PendingOAuth(provider, verifier, state)
        when (provider) {
            AuthProvider.GOOGLE -> {
                check(cfg.readyForGoogle) { "В настройках не указан Google Client ID" }
                google.authorizeUrl(cfg.googleClientId, cfg.redirectUri, Pkce.challenge(verifier), state)
            }
            AuthProvider.TIKTOK -> {
                check(cfg.readyForTikTok) { "В настройках не указан TikTok Client Key" }
                tiktok.authorizeUrl(cfg.tiktokClientKey, cfg.redirectUri, Pkce.challenge(verifier), state, withStats = cfg.tiktokWithStats)
            }
            AuthProvider.PASSWORD -> error("недостижимо")
        }
    }

    fun cancelLink(reason: String = "отменено") {
        pending = null
        _lastMessage = reason
    }

    private var _lastMessage: String? = null
    val lastMessage: String? get() = _lastMessage

    /** Вызывается из OAuthRedirectActivity после возврата из браузера. */
    suspend fun completeRedirect(uri: String): Result<ProviderLink> {
        val wait = pending
        if (wait == null || wait.isStale) {
            pending = null
            return Result.failure(AuthHttpException("Авторизация не начата или устарела (лимит 5 минут)"))
        }
        val redirect = Urls.redirectOf(uri)
            ?: return Result.failure(AuthHttpException("это не редирект авторизации: ${uri.take(80)}"))
        redirect.error?.let { error ->
            pending = null
            val reason = listOfNotNull(error, redirect.errorDescription).joinToString(": ")
            return Result.failure(AuthHttpException("отказ авторизации: $reason"))
        }
        if (redirect.state != wait.state) {
            pending = null
            return Result.failure(AuthHttpException("state не совпал — редирект отклонён"))
        }
        val code = redirect.code
            ?: return Result.failure(AuthHttpException("в редиректе нет code"))
        pending = null

        return runCatching {
            val cfg = clients()
            val token = when (wait.provider) {
                AuthProvider.GOOGLE -> google.exchange(code, cfg.googleClientId, cfg.redirectUri, wait.verifier)
                AuthProvider.TIKTOK -> tiktok.exchange(code, cfg.tiktokClientKey, cfg.tiktokClientSecret, cfg.redirectUri, wait.verifier)
                AuthProvider.PASSWORD -> error("недостижимо")
            }
            secure.set(SecureStore.Keys.access(wait.provider.name), token.accessToken)
            token.refreshToken?.let { secure.set(SecureStore.Keys.refresh(wait.provider.name), it) }

            var link = when (wait.provider) {
                AuthProvider.GOOGLE -> google.profile(token.accessToken).copy(
                    scopes = parseScopes(token.scope, GoogleOAuth.SCOPES),
                    expiresAt = token.expiresAt,
                    canRefresh = token.refreshToken != null,
                    connectedAt = System.currentTimeMillis(),
                )
                else -> {
                    val profile = tiktok.profile(token.accessToken)
                    val stats = tiktok.stats(token.accessToken)
                    tiktok.linkOf(
                        profile = profile,
                        followers = stats?.followers ?: 0L,
                        scopes = parseScopes(token.scope, TikTokOAuth.BASIC_SCOPES),
                    ).copy(
                        expiresAt = token.expiresAt,
                        canRefresh = token.refreshToken != null,
                        connectedAt = System.currentTimeMillis(),
                    )
                }
            }
            if (wait.provider == AuthProvider.GOOGLE) {
                google.myChannel(token.accessToken)?.let { channel ->
                    link = link.copy(
                        displayName = link.displayName.ifBlank { channel.title },
                        followers = channel.subscribers,
                    )
                    onGoogleChannel?.invoke(channel)
                }
            }
            mutate {
                it.copy(
                    guestMode = false,
                    links = it.links.filterNot { l -> l.provider == wait.provider } + link,
                )
            }
            link
        }
    }

    /** Google отдаёт список scope через пробел, TikTok — через запятую; принимаем оба варианта. */
    private fun parseScopes(raw: String, fallback: List<String>): List<String> =
        raw.split(',', ' ', '\n', '\t').map { it.trim() }.filter { it.isNotEmpty() }.ifEmpty { fallback }

    private suspend fun refreshInternal(provider: AuthProvider): TokenResponse {
        val cfg = clients()
        val refresh = secure.get(SecureStore.Keys.refresh(provider.name))
            ?: throw AuthHttpException("Refresh-токена нет — войди заново")
        return when (provider) {
            AuthProvider.GOOGLE -> google.refresh(cfg.googleClientId, refresh)
            AuthProvider.TIKTOK -> tiktok.refresh(cfg.tiktokClientKey, cfg.tiktokClientSecret, refresh)
            AuthProvider.PASSWORD -> {
                val user = firebase.refresh(secure.get(KEY_FIREBASE_REFRESH).orEmpty())
                secure.set(SecureStore.Keys.FIREBASE_ID_TOKEN, user.idToken)
                secure.set(KEY_FIREBASE_REFRESH, user.refreshToken)
                TokenResponse(
                    provider = AuthProvider.PASSWORD,
                    accessToken = user.idToken,
                    refreshToken = user.refreshToken,
                    expiresInSec = user.expiresIn,
                    scope = "firebase:identity-toolkit",
                    idToken = user.idToken,
                    raw = JsonObject(emptyMap()),
                )
            }
        }
    }

    /** Актуальный access-токен; если протух и есть refresh — одна попытка обновиться. */
    suspend fun accessToken(provider: AuthProvider): String? {
        val link = store.value.link(provider) ?: return null
        val stored = secure.get(SecureStore.Keys.access(provider.name))
        if (!link.isExpired && !stored.isNullOrBlank()) return stored
        if (!link.canRefresh) return null
        val token = runCatching { refreshInternal(provider) }.getOrNull() ?: return null
        secure.set(SecureStore.Keys.access(provider.name), token.accessToken)
        mutate { s ->
            s.copy(
                links = s.links.map {
                    if (it.provider == provider) it.copy(expiresAt = token.expiresAt, canRefresh = token.refreshToken != null) else it
                },
            )
        }
        return token.accessToken
    }

    /** TikTok-статистика по сохранённому токену (для вкладки «Рост»). */
    suspend fun tiktokFollowers(): Long? {
        val token = accessToken(AuthProvider.TIKTOK) ?: return null
        return runCatching { tiktok.stats(token)?.followers }.getOrNull()
    }

    suspend fun revoke(provider: AuthProvider) {
        val token = secure.get(SecureStore.Keys.access(provider.name))
        if (provider == AuthProvider.GOOGLE && !token.isNullOrBlank()) google.revoke(token)
        secure.remove(SecureStore.Keys.access(provider.name))
        secure.remove(SecureStore.Keys.refresh(provider.name))
        if (provider == AuthProvider.PASSWORD) {
            secure.remove(SecureStore.Keys.FIREBASE_ID_TOKEN)
            secure.remove(KEY_FIREBASE_REFRESH)
        }
        mutate { it.copy(links = it.links.filterNot { l -> l.provider == provider }) }
    }

    // ─── служебное ────────────────────────────────────────────────────────────

    private fun mutate(block: (Session) -> Session) {
        store.update(block)
        _state.value = store.value
    }

    companion object {
        const val KEY_FIREBASE_REFRESH = "firebase_refresh"
    }
}
