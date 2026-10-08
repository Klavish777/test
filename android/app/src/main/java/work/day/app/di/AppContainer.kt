package work.day.app.di

import android.app.Application
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import work.day.app.core.PersistedStore
import work.day.app.data.auth.AuthRepository
import work.day.app.data.auth.GoogleOAuth
import work.day.app.data.auth.SecureStore
import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmSettings
import work.day.app.data.llm.OfflineLlm
import work.day.app.data.llm.OpenAiCompatLlm
import work.day.app.data.platform.YouTubeDataApi
import work.day.app.data.platform.YouTubeResearch
import work.day.app.data.repo.GenerationRepository
import work.day.app.data.repo.SettingsRepository
import work.day.app.data.repo.Workspace
import work.day.app.data.repo.WorkspaceRepository
import work.day.app.domain.engine.ShiftEngine
import work.day.app.domain.model.AuthClients
import work.day.app.domain.model.GenerationState
import work.day.app.domain.model.Session

/**
 * Ручной DI: один объект на приложение. Держит хранилища, клиентов, авторизацию и движок смены.
 * Hilt/Koin сюда не просится: граф из восьми объектов дешевле, чем плагин аннотационной обработки.
 */
class AppContainer(private val app: Application) {

    val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    private val rootScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val settings = SettingsRepository(app)

    private val store: PersistedStore<Workspace> by lazy {
        PersistedStore(
            file = File(app.filesDir, "work_day/workspace.json"),
            serializer = Workspace.serializer(),
            json = json,
            scope = rootScope,
        ) { Workspace() }
    }

    val workspace: WorkspaceRepository by lazy { WorkspaceRepository(store) }

    private val sessionStore: PersistedStore<Session> by lazy {
        PersistedStore(
            file = File(app.filesDir, "work_day/auth_session.json"),
            serializer = Session.serializer(),
            json = json,
            scope = rootScope,
        ) { Session() }
    }

    private val clientsStore: PersistedStore<AuthClients> by lazy {
        PersistedStore(
            file = File(app.filesDir, "work_day/auth_clients.json"),
            serializer = AuthClients.serializer(),
            json = json,
            scope = rootScope,
        ) { AuthClients() }
    }

    val authClients: StateFlow<AuthClients> by lazy { clientsStore.state }

    private val secureStore: SecureStore by lazy { SecureStore(app, rootScope) }

    val auth: AuthRepository by lazy {
        AuthRepository(
            store = sessionStore,
            secure = secureStore,
            clients = { clientsStore.value },
            scope = rootScope,
        ).also { repo ->
            // цифры канала из Google применяются к профилю автора: агенты начинают работать на них
            repo.onGoogleChannel = { channel -> applyGoogleChannel(channel) }
        }
    }

    val session: StateFlow<Session> by lazy { auth.state }

    val offlineLlm = OfflineLlm()
    val remoteLlm by lazy { OpenAiCompatLlm { _llmSettings.value } }

    private val _llmSettings = MutableStateFlow(LlmSettings())
    val llmSettings: StateFlow<LlmSettings> = _llmSettings.asStateFlow()

    val youtube = YouTubeDataApi()

    val engine: ShiftEngine by lazy { ShiftEngine(this, rootScope) }

    // ─── «Генерация»: темы, скелеты роликов, правки монтажёра, рецепты сборки ───

    private val generationStore: PersistedStore<GenerationState> by lazy {
        PersistedStore(
            file = File(app.filesDir, "work_day/generation.json"),
            serializer = GenerationState.serializer(),
            json = json,
            scope = rootScope,
        ) { GenerationState() }
    }

    private val researchClient = YouTubeResearch()

    val generation: GenerationRepository by lazy {
        GenerationRepository(generationStore, settings, workspace, { llm() }, researchClient)
    }

    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    /**
     * Ошибка входа отдельным состоянием: экран входа и экран замка рисуются до Scaffold,
     * поэтому снакбар там физически не смонтирован и сообщение просто исчезало.
     */
    private val _authError = MutableStateFlow<String?>(null)
    val authError: StateFlow<String?> = _authError.asStateFlow()

    fun authError(text: String?) {
        _authError.value = text
    }

    fun notifyAuth(text: String) {
        _messages.tryEmit(text)
    }

    /** Модель или офлайн-движок: выбор вынесен в чистую функцию и покрыт тестом. */
    fun llm(): LlmClient = when (llmSourceFor(_llmSettings.value.isUsable)) {
        LlmClient.Source.REMOTE -> remoteLlm
        LlmClient.Source.OFFLINE -> offlineLlm
    }

    fun start() {
        rootScope.launch {
            settings.llmSettings.collect { _llmSettings.value = it }
        }
    }

    /** Чем защищены токены на этом устройстве — показываем честно, без «всё хорошо». */
    fun tokenStorageLabel(): String =
        if (secureStore.degraded()) "приватный файл (Keystore недоступен)" else "Android Keystore"

    fun saveAuthClients(clients: AuthClients) {
        clientsStore.replace(clients)
    }

    private fun applyGoogleChannel(channel: GoogleOAuth.GoogleChannel) {
        if (channel.channelId.isBlank()) return
        workspace.updateProfile { profile ->
            profile.copy(
                youtubeChannelId = channel.channelId,
                youtubeTitle = channel.title.ifBlank { profile.youtubeTitle },
                youtubeSubscribers = channel.subscribers,
            )
        }
        notifyAuth("YouTube: ${channel.title} · подписчиков ${channel.subscribers} · роликов ${channel.videos}")
    }

    /** Тиканье смены не должно молча использовать протухший токен: раз в смену сверяем срок. */
    suspend fun refreshTokenIfNeeded() {
        work.day.app.domain.model.AuthProvider.entries.forEach { provider ->
            if (session.value.link(provider)?.isExpired == true) auth.accessToken(provider)
        }
    }

    fun persistFlush() {
        store.flush()
        sessionStore.flush()
        clientsStore.flush()
        generationStore.flush()
    }

    fun exportJson(): String = json.encodeToString(Workspace.serializer(), store.value)

    /** Экспорт настроек входа: намеренно без токенов и паролей. */
    fun exportAuth(): Session = sessionStore.value.let {
        it.copy(passwordHash = "", passwordSalt = "")
    }

    /** Полный сброс: включая клиенты авторизации — в них живёт TikTok client secret. */
    fun wipeAll() {
        store.replace(Workspace())
        sessionStore.replace(Session())
        clientsStore.replace(AuthClients())
        generationStore.replace(GenerationState())
        secureStore.clear()
        _authError.value = null
        persistFlush()
    }
}

/**
 * Выбор движка генерации вынесен в чистую функцию, чтобы это было покрыто тестом:
 * без ключа — офлайн-движок, с ключом — модель.
 */
fun llmSourceFor(usable: Boolean): LlmClient.Source =
    if (usable) LlmClient.Source.REMOTE else LlmClient.Source.OFFLINE
