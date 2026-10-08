package work.day.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import work.day.app.WorkDayApp
import work.day.app.data.llm.OfflineLlm
import work.day.app.data.llm.OpenAiCompatLlm
import work.day.app.data.platform.AnalyticsImporter
import work.day.app.data.platform.YouTubeDataApi
import work.day.app.domain.agent.LlmBrief
import work.day.app.domain.model.AgentConfig
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.Autonomy
import work.day.app.domain.model.ChannelProfile
import work.day.app.domain.engine.ShiftPhase
import work.day.app.data.repo.GrowthGoals

/**
 * Один ViewModel на все вкладки: состояние смены и рабочего пространства уже живут
 * в одноэкранных потоках контейнера, здесь только команды и обратная связь.
 */
class WorkDayViewModel(application: Application) : AndroidViewModel(application) {

    private val container get() = (getApplication() as WorkDayApp).container

    val shift = container.engine.state
    val workspace = container.workspace.state
    val llmSettings = container.llmSettings

    val session = container.session
    val authClients = container.authClients

    /** Сообщения — из контейнера: их генерируют и ViewModel, и OAuthRedirectActivity. */
    val messages: SharedFlow<String> = container.messages

    // ─── смена ────────────────────────────────────────────────────────────────

    // ─── вход и привязка площадок ─────────────────────────────────────────────

    fun link(provider: work.day.app.domain.model.AuthProvider) {
        viewModelScope.launch {
            container.auth.beginLink(provider)
                .onSuccess { url ->
                    if (work.day.app.OAuthRedirectActivity.open(getApplication(), url)) {
                        _status("Открываю страницу согласия ${provider.label} — вернёшься в приложение сам")
                    } else {
                        container.auth.cancelLink("не чем открыть страницу согласия")
                        _status("${provider.label}: нужен браузер (Chrome/Firefox) — на устройстве не найдено приложение для ссылок")
                    }
                }
                .onFailure { _status("${provider.label}: ${it.message?.take(180)}") }
        }
    }

    fun signIn(email: String, password: String) = viewModelScope.launch {
        container.auth.signIn(email, password)
            .onSuccess { _status("Вход выполнен") }
            .onFailure { _status("Вход не получился: ${it.message?.take(180)}") }
    }

    fun register(email: String, password: String, confirm: String) = viewModelScope.launch {
        container.auth.register(email, password, confirm)
            .onSuccess { _status(if (authClients.value.readyForFirebase) "Аккаунт создан в Firebase" else "Пароль установлен, приложение под замком") }
            .onFailure { _status("Регистрация не удалась: ${it.message?.take(180)}") }
    }

    fun resetPassword(email: String) = viewModelScope.launch {
        container.auth.requestPasswordReset(email)
            .onSuccess { _status("Письмо для сброса отправлено на $email") }
            .onFailure { _status(it.message?.take(180).orEmpty()) }
    }

    fun continueAsGuest() = container.auth.continueAsGuest()
    fun tokenStorage(): String = container.tokenStorageLabel()
    fun signOut() = viewModelScope.launch {
        container.auth.signOut()
        notify("Вышли; токены отозваны")
    }
    fun unlock(password: String): Boolean = container.auth.verifyLock(password)
    fun revoke(provider: work.day.app.domain.model.AuthProvider) = viewModelScope.launch {
        container.auth.revoke(provider)
        _status("Отвязано: ${provider.label}")
    }

    fun saveLock(enabled: Boolean, password: String?) = viewModelScope.launch {
        container.auth.setLock(enabled, password)
            .onSuccess { _status(if (enabled) "Замок включён" else "Замок снят") }
            .onFailure { _status(it.message?.take(180).orEmpty()) }
    }

    fun saveAuthClients(clients: work.day.app.domain.model.AuthClients) {
        container.saveAuthClients(clients)
        _status("Клиенты авторизации сохранены на устройстве")
    }

    /** TikTok-статистика, если токен жив — обновляет followers в профиле. */
    fun refreshTikTokStats() = viewModelScope.launch {
        val followers = container.auth.tiktokFollowers()
        if (followers == null) {
            _status("TikTok: нет актуального токена или scope user.info.stats не одобрен")
        } else {
            container.workspace.updateProfile { it.copy(tiktokFollowers = followers) }
            _status("TikTok: подписчиков $followers")
        }
    }

    fun startShift() {
        val state = shift.value
        when (state.phase) {
            ShiftPhase.PAUSED -> container.engine.resume()
            ShiftPhase.WORKING -> notify("Смена уже идёт")
            else -> container.engine.start()
        }
    }

    fun pauseShift() = container.engine.pause()
    fun stopShift() = container.engine.stop()
    fun setSpeed(multiplier: Int) = container.engine.setSpeed(multiplier)

    fun approve(taskId: String) {
        container.engine.approve(taskId)
        notify("Пакет в очереди публикации. Опубликуй вручную в слот — агент проверит результат")
    }

    fun skip(taskId: String) {
        container.engine.skip(taskId)
        notify("Убрал задачу из плана дня")
    }

    fun markPublished(itemId: String) = container.engine.markPublished(itemId)
    fun dropItem(itemId: String) = container.engine.drop(itemId)
    fun star(artifactId: String) = container.engine.toggleArtifactStar(artifactId)

    // ─── настройки агентов ────────────────────────────────────────────────────

    fun updateProfile(profile: ChannelProfile) {
        container.workspace.updateProfile { profile }
        notify("Профиль канала сохранён — агенты перестроят план")
    }

    fun updateGoals(goals: GrowthGoals) {
        container.workspace.updateGoals { goals }
    }

    fun setAgentEnabled(agent: AgentId, enabled: Boolean) =
        container.workspace.updateAgentConfig(agent) { it.copy(enabled = enabled) }

    fun setAutonomy(agent: AgentId, autonomy: Autonomy) =
        container.workspace.updateAgentConfig(agent) { it.copy(autonomy = autonomy) }

    fun setIntensity(agent: AgentId, intensity: Int) =
        container.workspace.updateAgentConfig(agent) { it.copy(intensity = intensity.coerceIn(1, 5)) }

    fun togglePlaybook(agent: AgentId, playbookId: String) =
        container.workspace.updateAgentConfig(agent) { config ->
            val current = config.enabledPlaybooks
            val next = if (current.isEmpty()) {
                work.day.app.domain.model.Playbooks.forAgent(agent).map { it.id }.toSet()
            } else if (playbookId in current) {
                current - playbookId
            } else {
                current + playbookId
            }
            config.copy(enabledPlaybooks = next)
        }

    fun setDailyLimit(agent: AgentId, limit: Int) =
        container.workspace.updateAgentConfig(agent) { it.copy(dailyLimit = limit.coerceIn(1, 40)) }

    fun agentConfig(agent: AgentId): AgentConfig = container.workspace.agentConfig(agent)

    // ─── модель и площадки ────────────────────────────────────────────────────

    fun saveLlm(enabled: Boolean, baseUrl: String, apiKey: String, model: String) {
        viewModelScope.launch {
            container.settings.setLlm(enabled, baseUrl, apiKey, model)
            notify(if (enabled && apiKey.isNotBlank()) "Модель подключена: $model" else "Агенты работают на офлайн-движке")
        }
    }

    fun testLlm(prompt: String) {
        viewModelScope.launch {
            val settings = container.settings.llmNow()
            if (!settings.isUsable) {
                val offline = OfflineLlm().complete(LlmBrief("Тест", prompt, 0.5, 200))
                notify("Модель не настроена, офлайн-движок ответил: ${offline.text.take(80)}…")
                return@launch
            }
            runCatching {
                OpenAiCompatLlm { settings }.complete(LlmBrief("Ты отвечаешь одним предложением.", prompt, 0.5, 120))
            }.onSuccess { notify("Ответ модели: ${it.text.take(140)}") }
                .onFailure { notify("Модель не ответила: ${it.message?.take(140)}") }
        }
    }

    fun connectYoutube() {
        viewModelScope.launch {
            val token = container.auth.accessToken(work.day.app.domain.model.AuthProvider.GOOGLE)
            val key = container.settings.youtubeApiKey()
            val channelId = container.workspace.profile.youtubeChannelId
            if (token == null && key.isBlank()) {
                _status("Нужен вход через Google или ключ YouTube Data API")
                return@launch
            }
            notify("Запрашиваю статистику канала ${if (token != null) "по токену входа" else "по API-ключу"}…")
            YouTubeDataApi().fetchChannelStats(key, channelId, token)
                .onSuccess { stats ->
                    container.workspace.updateProfile { container.youtube.applyTo(stats, it) }
                    notify("YouTube: ${stats.title}, подписчиков ${stats.subscribers}, просмотров ${stats.views}")
                }
                .onFailure { notify("YouTube API: ${it.message?.take(160)}") }
        }
    }

    fun setYoutubeApiKey(key: String) {
        viewModelScope.launch {
            container.settings.setYoutubeApiKey(key)
            notify("Ключ YouTube Data API сохранён в памяти устройства")
        }
    }

    fun importMetrics(csv: String) {
        viewModelScope.launch {
            AnalyticsImporter.parse(csv)
                .onSuccess { rows ->
                    container.workspace.importMetrics(rows)
                    notify("Импортировано строк: ${rows.size}. График и отчёты теперь на твоих данных")
                }
                .onFailure { notify("Импорт не удался: ${it.message?.take(160)}") }
        }
    }

    fun setShiftWindow(startMinutes: Int, endMinutes: Int) {
        viewModelScope.launch {
            container.settings.setShift(startMinutes, endMinutes)
            notify("Рабочий день: ${startMinutes / 60}:00 – ${endMinutes / 60}:00")
        }
    }

    fun export(): String = container.exportJson()

    fun resetAll() {
        container.engine.stop()
        container.wipeAll()
        notify("Данные очищены")
    }

    private fun notify(text: String) = _status(text)

    private fun _status(text: String) = container.notifyAuth(text)
}
