package work.day.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import work.day.app.domain.model.TopicCandidate
import work.day.app.domain.model.VideoFormat
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
    val authError = container.authError

    val generation: StateFlow<work.day.app.domain.model.GenerationState> = container.generation.state

    private val _generationBusy = MutableStateFlow(false)
    val generationBusy: StateFlow<Boolean> = _generationBusy.asStateFlow()

    /** Сообщения — из контейнера: их генерируют и ViewModel, и OAuthRedirectActivity. */
    val messages: SharedFlow<String> = container.messages

    // ─── смена ────────────────────────────────────────────────────────────────

    // ─── вход и привязка площадок ─────────────────────────────────────────────

    fun link(provider: work.day.app.domain.model.AuthProvider) {
        viewModelScope.launch {
            container.auth.beginLink(provider)
                .onSuccess { url ->
                    if (work.day.app.OAuthRedirectActivity.open(getApplication(), url)) {
                        container.authError(null)
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
            .onSuccess {
                container.authError(null)
                _status("Вход выполнен")
            }
            .onFailure {
                container.authError("Вход не получился: ${it.message?.take(180)}")
                _status("Вход не получился: ${it.message?.take(180)}")
            }
    }

    fun register(email: String, password: String, confirm: String) = viewModelScope.launch {
        container.auth.register(email, password, confirm)
            .onSuccess {
                container.authError(null)
                _status(if (authClients.value.readyForFirebase) "Аккаунт создан в Firebase" else "Пароль установлен, приложение под замком")
            }
            .onFailure {
                val text = "Регистрация не удалась: ${it.message?.take(180)}"
                container.authError(text)
                _status(text)
            }
    }

    fun resetPassword(email: String) = viewModelScope.launch {
        container.auth.requestPasswordReset(email)
            .onSuccess {
                container.authError(null)
                _status("Письмо для сброса отправлено на $email")
            }
            .onFailure {
                container.authError(it.message?.take(180).orEmpty())
                _status(it.message?.take(180).orEmpty())
            }
    }

    /** Ошибку снимает ввод: иначе человек правит поле, а красный текст уже не про него. */
    fun clearAuthError() = container.authError(null)

    fun continueAsGuest() {
        container.authError(null)
        container.auth.continueAsGuest()
    }
    fun tokenStorage(): String = container.tokenStorageLabel()
    fun signOut() = viewModelScope.launch {
        container.auth.signOut()
        notify("Вышли; токены отозваны")
    }
    fun unlock(password: String): Boolean {
        val ok = container.auth.verifyLock(password)
        container.authError(if (ok) null else "Пароль не подошёл")
        return ok
    }
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

    // ─── генерация роликов ───────────────────────────────────────────────────

    fun genNiche(name: String) = container.generation.setNiche(name)

    fun genFormat(format: VideoFormat) = container.generation.setFormat(format)

    fun genDuration(seconds: Int) = container.generation.setDuration(seconds)

    fun genSuggestDuration(): Int = container.generation.suggestedDuration()

    fun genAvailableFormats(): List<VideoFormat> = VideoFormat.entries

    /** Шаг 1. Тема + длительность — то, что отдаёт нажатие «Сгенерировать». */
    fun generate() = viewModelScope.launch {
        _generationBusy.value = true
        container.generation.generate()
            .onSuccess { topics ->
                _status(
                    if (topics.isEmpty()) "Генерация вернула пустой список — проверь нишу"
                    else "Тем: ${topics.size}. Дольше всех держит: ${topics.first().title.take(48)}"
                )
            }
            .onFailure { _status("Генерация не удалась: ${it.message?.take(160)}") }
        _generationBusy.value = false
    }

    /** Шаг 2. Скелет по битам + правки агента-монтажёра + проверка прав + рецепт ffmpeg. */
    fun buildPlan(topic: TopicCandidate) = viewModelScope.launch {
        _generationBusy.value = true
        container.generation.build(topic)
            .onSuccess { plan ->
                val verdict = if (plan.compliance.allowedToPublish) "к публикации допущен"
                else "блокеров: ${plan.compliance.blockers.size}"
                _status("Собран ${plan.totalSec}с · балл ${plan.scoreBefore.total}→${plan.scoreAfter.total} · $verdict")
            }
            .onFailure { _status("Сборка не удалась: ${it.message?.take(160)}") }
        _generationBusy.value = false
    }

    fun reEditPlan() = viewModelScope.launch {
        _generationBusy.value = true
        container.generation.reEdit()
            .onSuccess { _status("Монтажёр прошёл ещё раз: балл ${it.scoreAfter.total}") }
            .onFailure { _status("Правок больше нет: ${it.message?.take(120)}") }
        _generationBusy.value = false
    }

    fun researchNow() = viewModelScope.launch {
        _generationBusy.value = true
        container.generation.refreshResearch()
            .onSuccess { _status(if (it == 0) "Ключа YouTube API нет — считаю по демо-приорам нишы" else "Статистика нишы: $it роликов") }
            .onFailure { _status("YouTube не ответил: ${it.message?.take(160)}") }
        _generationBusy.value = false
    }

    fun enqueueGenerated() {
        val plan = generation.value.plan ?: return _status("Сначала собери ролик")
        if (!plan.compliance.allowedToPublish) {
            _status("В очередь не пущу: сначала закрой блокирующие проверки (${plan.compliance.blockers.first().rule})")
            return
        }
        container.generation.enqueueToChannel(plan)
        _status("Положил в очередь публикаций: ${plan.title.take(40)} — выкладываешь руками")
    }

    fun exportRecipe(): String = generation.value.plan?.let { container.generation.exportRecipe(it) }.orEmpty()

    /**
     * Сохранить рецепт рядом с рабочими файлами, чтобы забрать его на компьютер
     * (файловый менеджер или adb pull) и там запустить render.sh. Рендер на телефоне
     * не делаем сознательно: склейка — работа ffmpeg, а не приложения.
     */
    fun saveRecipe() {
        val plan = generation.value.plan
        if (plan == null) {
            _status("Сначала собери ролик — сохранять пока нечего")
            return
        }
        runCatching {
            val dir = java.io.File(container.appContext.filesDir, "work_day").apply { mkdirs() }
            val file = java.io.File(dir, "recipe-${plan.id}.txt")
            file.writeText(container.generation.exportRecipe(plan))
            file.absolutePath
        }.onSuccess { _status("Рецепт сохранён: $it") }
            .onFailure { _status("Не сохранилось: ${it.message?.take(120)}") }
    }

    fun generationNiches(): List<String> = container.generation.niches

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
