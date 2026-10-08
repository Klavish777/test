package work.day.app.di

import android.app.Application
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import work.day.app.core.PersistedStore
import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmSettings
import work.day.app.data.llm.OfflineLlm
import work.day.app.data.llm.OpenAiCompatLlm
import work.day.app.data.platform.YouTubeDataApi
import work.day.app.data.repo.Workspace
import work.day.app.data.repo.WorkspaceRepository
import work.day.app.domain.engine.ShiftEngine

/**
 * Ручной DI: один объект на приложение. Держит хранилища, клиентов и движок смены.
 * Hilt/Koin сюда не просится — граф из шести объектов дешевле, чем плагин аннотационной обработки.
 */
class AppContainer(private val app: Application) {

    val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    private val rootScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val settings = work.day.app.data.repo.SettingsRepository(app)

    private val store: PersistedStore<Workspace> by lazy {
        PersistedStore(
            file = File(app.filesDir, "work_day/workspace.json"),
            serializer = Workspace.serializer(),
            json = json,
            scope = rootScope,
        ) { Workspace() }
    }

    val workspace: WorkspaceRepository by lazy { WorkspaceRepository(store) }

    val offlineLlm = OfflineLlm()
    val remoteLlm by lazy { OpenAiCompatLlm { _llmSettings.value } }

    private val _llmSettings = MutableStateFlow(LlmSettings())
    val llmSettings: StateFlow<LlmSettings> = _llmSettings.asStateFlow()

    val youtube = YouTubeDataApi()

    val engine: ShiftEngine by lazy { ShiftEngine(this, rootScope) }

    val lastMessage = MutableStateFlow<String?>(null)

    fun say(text: String) {
        lastMessage.value = text
        rootScope.launch { lastMessage.value = null }
    }

    /** Модель или офлайн-движок: выбор вынесен в llmSourceFor, он покрыт тестом. */
    fun llm(): LlmClient = when (llmSourceFor(_llmSettings.value.isUsable)) {
        LlmClient.Source.REMOTE -> remoteLlm
        LlmClient.Source.OFFLINE -> offlineLlm
    }

    fun start() {
        rootScope.launch {
            settings.llmSettings.collect { _llmSettings.value = it }
        }
    }

    fun persistFlush() = store.flush()

    fun exportJson(): String = json.encodeToString(Workspace.serializer(), store.value)

    fun wipeAll() {
        store.replace(Workspace())
        persistFlush()
    }
}

/**
 * Выбор движка генерации вынесен в чистую функцию, чтобы это было покрыто тестом:
 * без ключа — офлайн-движок, с ключом — модель.
 */
fun llmSourceFor(usable: Boolean): work.day.app.data.llm.LlmClient.Source =
    if (usable) work.day.app.data.llm.LlmClient.Source.REMOTE else work.day.app.data.llm.LlmClient.Source.OFFLINE
