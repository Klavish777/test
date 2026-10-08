package work.day.app.domain.engine

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.CoroutineScope
import kotlinx.serialization.Serializable
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import work.day.app.data.llm.LlmClient
import work.day.app.data.llm.LlmException
import work.day.app.di.AppContainer
import work.day.app.domain.agent.AgentRegistry
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.AgentTask
import work.day.app.domain.model.Artifact
import work.day.app.domain.model.Autonomy
import work.day.app.domain.model.ChannelProfile
import work.day.app.domain.model.DailyMetrics
import work.day.app.domain.model.EventKind
import work.day.app.domain.model.ModelSource
import work.day.app.domain.model.Platform
import work.day.app.domain.model.PublishItem
import work.day.app.domain.model.PublishState
import work.day.app.domain.model.Risk
import work.day.app.domain.model.ShiftEvent
import work.day.app.domain.model.TaskKind
import work.day.app.domain.model.TaskStatus

enum class ShiftPhase(val label: String) {
    IDLE("Смена не идёт"),
    PLANNING("Распределяем задачи"),
    WORKING("Идёт смена"),
    PAUSED("Пауза"),
    REPORTING("Пишем отчёт"),
    FINISHED("Смена закрыта"),
}

/** Состояние одного агента внутри смены — то, что видно на карточке. */
data class AgentRuntime(
    val agent: AgentId,
    val busy: Boolean = false,
    val currentTaskId: String = "",
    val currentTaskTitle: String = "",
    val progress: Float = 0f,
    val tasksDone: Int = 0,
    val artifacts: Int = 0,
    val waiting: Int = 0,
    val lastOutput: String = "",
    val message: String = "ожидает старта",
)

data class ShiftSnapshot(
    val phase: ShiftPhase = ShiftPhase.IDLE,
    val day: String = "",
    val clock: Int = 9 * 60,
    val speed: Int = 1,
    val agents: Map<AgentId, AgentRuntime> = AgentId.ordered.associateWith { AgentRuntime(it) },
    val tasks: List<AgentTask> = emptyList(),
    val artifacts: List<Artifact> = emptyList(),
    val events: List<ShiftEvent> = emptyList(),
    val report: ShiftReport? = null,
    val metrics: List<DailyMetrics> = emptyList(),
    val publishQueue: List<PublishItem> = emptyList(),
    val profile: ChannelProfile = ChannelProfile(),
) {
    val plannedTasks: Int get() = tasks.size
    val doneTasks: Int get() = tasks.count { it.status == TaskStatus.DONE || it.status == TaskStatus.QUEUED }
    val pendingApproval: Int get() = tasks.count { it.status == TaskStatus.NEEDS_APPROVAL }
    val runningCount: Int get() = tasks.count { it.status == TaskStatus.RUNNING }
    val shiftProgress: Float
        get() {
            val total = (SHIFT_END - SHIFT_START).toFloat()
            return ((clock - SHIFT_START) / total).coerceIn(0f, 1f)
        }

    fun agent(agent: AgentId): AgentRuntime = agents[agent] ?: AgentRuntime(agent)
}

/** Итог смены по каждому агенту — то, что человек читает вечером. */
@Serializable
data class ShiftReport(
    val day: String,
    val perAgent: List<AgentLine>,
    val summary: String,
    val generatedBy: ModelSource,
) {
    val totalDone: Int get() = perAgent.sumOf { it.done }
    val totalWaiting: Int get() = perAgent.sumOf { it.waiting }
}

@Serializable
data class AgentLine(
    val agent: AgentId,
    val done: Int,
    val waiting: Int,
    val artifacts: Int,
    val score: Int,
    val highlight: String,
    val tomorrow: String,
)

/**
 * Движок смены.
 *
 * Модель работы: сутки канала сжимаются в «смену» 09:00–18:00. Каждые 250 мс тика проходит
 * 6 минут смены; агент ведёт задачу, по завершении дергает LlmClient и отдаёт материал.
 * Всё, что касается наружности (Risk != LOW), останавливается на статусе NEEDS_APPROVAL —
 * дальше решение только человека. Автоматической публикации в приложении нет и не будет.
 */
class ShiftEngine(
    private val container: AppContainer,
    private val scope: CoroutineScope,
) {

    private val mutex = Mutex()
    private var job: Job? = null

    private val _state = MutableStateFlow(ShiftSnapshot())
    val state: StateFlow<ShiftSnapshot> = _state.asStateFlow()

    // ─── управление ───────────────────────────────────────────────────────────

    fun start() {
        if (job?.isActive == true && _state.value.phase != ShiftPhase.IDLE) return
        scope.launch {
            val profile = container.workspace.profile
            val metrics = container.workspace.metricsDays(60)
            val startClock = container.settings.shiftStartMinutes()
            val tag = LocalDate.now().format(DateTimeFormatter.ISO_LOCAL_DATE)
            update { it.copy(day = tag, clock = startClock, phase = ShiftPhase.PLANNING, profile = profile, metrics = metrics, events = emptyList(), report = null) }
            emit(null, EventKind.SHIFT_START, "Смена ${clockLabel(startClock)} · набираем план")
            plan()
            update { it.copy(phase = ShiftPhase.WORKING) }
            job = launchLoop()
        }
    }

    fun pause() {
        scope.launch {
            update { it.copy(phase = ShiftPhase.PAUSED) }
            emit(null, EventKind.INFO, "Смена на паузе")
        }
    }

    fun resume() {
        scope.launch {
            if (_state.value.phase == ShiftPhase.PAUSED) {
                update { it.copy(phase = ShiftPhase.WORKING) }
                if (job?.isActive != true) job = launchLoop()
                emit(null, EventKind.INFO, "Продолжаем смену")
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
        scope.launch {
            update { it.copy(phase = ShiftPhase.IDLE, agents = AgentId.ordered.associateWith { a -> AgentRuntime(a) }) }
            emit(null, EventKind.INFO, "Смена остановлена, задачи сохранены")
        }
    }

    fun setSpeed(multiplier: Int) {
        scope.launch { update { it.copy(speed = multiplier.coerceIn(1, 8)) } }
    }

    // ─── очередь и одобрение ──────────────────────────────────────────────────

    fun approve(taskId: String) {
        scope.launch {
            val task = _state.value.tasks.firstOrNull { it.id == taskId } ?: return@launch
            val profile = container.workspace.profile
            val autonomy = container.workspace.agentConfig(task.agent).autonomy
            val item = PublishItem(
                id = "pub-$taskId",
                taskId = taskId,
                agent = task.agent,
                platform = task.kind.platforms.firstOrNull() ?: Platform.YOUTUBE,
                title = task.title,
                body = _state.value.artifacts.filter { it.taskId == taskId }
                    .joinToString("\n\n") { it.body }
                    .ifBlank { task.kind.deliverable },
                slotMinutes = task.slotMinutes,
            )
            update { state ->
                state.copy(
                    tasks = state.tasks.map {
                        if (it.id == taskId) it.copy(status = TaskStatus.QUEUED, finishedAt = System.currentTimeMillis()) else it
                    },
                    publishQueue = listOf(item) + state.publishQueue,
                )
            }
            emit(task.agent, EventKind.DONE, "Одобрено. Пакет «${task.title}» → очередь публикации (${clockLabel(task.slotMinutes)}, ${item.platform.label})")
            if (autonomy == Autonomy.SCHEDULE) {
                emit(task.agent, EventKind.INFO, "Автономия «Планировщик»: напомним в слот, публикуешь ты сам")
            }
            container.workspace.enqueue(item)
        }
    }

    fun skip(taskId: String) {
        scope.launch {
            update { state ->
                state.copy(tasks = state.tasks.map {
                    if (it.id == taskId) it.copy(status = TaskStatus.SKIPPED, finishedAt = System.currentTimeMillis()) else it
                })
            }
            emit(null, EventKind.SKIP, "Задача $taskId убрана из плана дня")
        }
    }

    fun markPublished(itemId: String) {
        container.workspace.markPublished(itemId)
        scope.launch {
            update { state ->
                state.copy(publishQueue = state.publishQueue.map {
                    if (it.id == itemId) it.copy(state = PublishState.PUBLISHED) else it
                })
            }
            emit(null, EventKind.DONE, "Отметил публикацию — агент учтёт это в следующих замерах")
        }
    }

    fun drop(itemId: String) {
        container.workspace.dropItem(itemId)
        scope.launch {
            update { state -> state.copy(publishQueue = state.publishQueue.filterNot { it.id == itemId }) }
        }
    }

    fun toggleArtifactStar(artifactId: String) {
        container.workspace.toggleArtifactStar(artifactId)
        scope.launch {
            update { state ->
                state.copy(artifacts = state.artifacts.map {
                    if (it.id == artifactId) it.copy(starred = !it.starred) else it
                })
            }
        }
    }

    /** Ручная правка цели агента/настроек во время смены. */
    fun reloadConfig() {
        scope.launch {
            val profile = container.workspace.profile
            update { it.copy(profile = profile) }
            emit(null, EventKind.INFO, "Настройки перечитаны")
        }
    }

    // ─── планирование ─────────────────────────────────────────────────────────

    private suspend fun plan() {
        val snapshot = _state.value
        val day = LocalDate.now().toEpochDay()
        AgentId.ordered.forEach { agentId ->
            val config = container.workspace.agentConfig(agentId)
            val agent = AgentRegistry.get(agentId)
            val window = ShiftWindowFactory.of(snapshot.day, day, container.settings.shiftStartMinutes(), container.settings.shiftEndMinutes())
            val tasks = agent.plan(config, snapshot.profile, window)
            if (tasks.isEmpty()) {
                emit(agentId, EventKind.PLAN, if (!config.enabled) "агент выключен" else "нет включённых плейбуков — смена без задач")
            } else {
                update { state ->
                    state.copy(tasks = state.tasks + tasks)
                }
                emit(agentId, EventKind.PLAN, "план: ${tasks.size} задач · ${tasks.map { it.kind.title }.distinct().size} типов работ")
            }
        }
        container.workspace.replaceTasks(_state.value.tasks)
    }

    // ─── цикл смены ───────────────────────────────────────────────────────────

    private fun launchLoop(): Job = scope.launch {
        while (isActive) {
            val snapshot = _state.value
            if (snapshot.phase != ShiftPhase.WORKING) {
                delay(TICK_MS)
                continue
            }
            val nextClock = snapshot.clock + TICK_MINUTES
            if (nextClock >= SHIFT_END) {
                finishShift()
                break
            }
            update { it.copy(clock = nextClock) }
            tickWork(nextClock)
            delay(TICK_MS / _state.value.speed.coerceAtLeast(1))
        }
    }

    private suspend fun tickWork(clock: Int) {
        AgentId.ordered.forEach { agentId ->
            val config = container.workspace.agentConfig(agentId)
            if (!config.enabled) return@forEach
            val snapshot = _state.value
            val runtime = snapshot.agent(agentId)

            // 1. доводим текущую задачу
            if (runtime.busy) {
                val task = snapshot.tasks.firstOrNull { it.id == runtime.currentTaskId }
                if (task == null) {
                    updateAgent(agentId) { it.copy(busy = false, currentTaskId = "", progress = 0f) }
                    return@forEach
                }
                val step = 6f / task.kind.effortMin.toFloat() * config.intensity / 3f
                val progress = (task.progress + step).coerceIn(0f, 1f)
                val minutes = task.minutesSpent + 6
                if (progress < 1f) {
                    mutateTask(task.id) { it.copy(progress = progress, minutesSpent = minutes) }
                    if (progress > 0.55 && runtime.lastOutput.isBlank()) {
                        emit(agentId, EventKind.START, "пишу «${task.kind.deliverable}»…")
                    }
                    return@forEach
                }
                runTask(task, profile = snapshot.profile, clock = clock)
                return@forEach
            }

            // 2. берём новую задачу по слоту
            val next = snapshot.tasks
                .filter { it.agent == agentId && it.status == TaskStatus.PLANNED && it.slotMinutes <= clock }
                .minByOrNull { it.slotMinutes }
                ?: return@forEach
            mutateTask(next.id) { it.copy(status = TaskStatus.RUNNING) }
            updateAgent(agentId) { it.copy(busy = true, currentTaskId = next.id, currentTaskTitle = next.title, progress = 0f, message = "делает «${next.kind.title}»") }
            emit(agentId, EventKind.START, "взял «${next.title}» (${clockLabel(clock)})")
        }
    }

    /** Исполнение: запрос к модели → артефакт → либо одобрение, либо закрытие. */
    private suspend fun runTask(task: AgentTask, profile: ChannelProfile, clock: Int) {
        val agent = AgentRegistry.get(task.agent)
        val brief = agent.brief(task, profile)
        val llm: LlmClient = container.llm()
        val result = runCatching { llm.complete(brief) }

        result.exceptionOrNull()?.let { error ->
            if (llm.source == LlmClient.Source.REMOTE) {
                emit(task.agent, EventKind.WARNING, "модель не ответила (${error.message?.take(90)}), довожу офлайн-движком")
                val fallback = runCatching { container.offlineLlm.complete(brief) }
                if (fallback.isFailure) {
                    mutateTask(task.id) { it.copy(status = TaskStatus.FAILED, finishedAt = System.currentTimeMillis()) }
                    emit(task.agent, EventKind.WARNING, "офлайн-движок тоже не смог: ${fallback.exceptionOrNull()?.message?.take(80)}")
                    updateAgent(task.agent) { it.copy(busy = false, currentTaskId = "", progress = 0f, message = "ошибка генерации") }
                    return
                }
                publish(task, fallback.getOrThrow().text, ModelSource.OFFLINE, clock)
                return
            }
            mutateTask(task.id) { it.copy(status = TaskStatus.FAILED, finishedAt = System.currentTimeMillis()) }
            emit(task.agent, EventKind.WARNING, "ошибка: ${error.message?.take(120)}")
            updateAgent(task.agent) { it.copy(busy = false, currentTaskId = "", progress = 0f, message = "ошибка") }
            return
        }

        publish(task, result.getOrThrow().text, source(result.getOrThrow().source), clock)
    }

    private fun source(s: LlmClient.Source): ModelSource =
        if (s == LlmClient.Source.REMOTE) ModelSource.REMOTE else ModelSource.OFFLINE

    private suspend fun publish(task: AgentTask, text: String, source: ModelSource, clock: Int) {
        val artifact = Artifact(
            id = "art-${task.id}",
            taskId = task.id,
            agent = task.agent,
            kind = task.kind,
            title = task.kind.title,
            body = text,
            platforms = task.kind.platforms.toList(),
            createdAt = System.currentTimeMillis(),
            source = source,
        )
        val needsApproval = task.requiresApproval
        update { state ->
            state.copy(
                artifacts = listOf(artifact) + state.artifacts,
                tasks = state.tasks.map { current ->
                    if (current.id != task.id) return@map current
                    current.copy(
                        status = if (needsApproval) TaskStatus.NEEDS_APPROVAL else TaskStatus.DONE,
                        progress = 1f,
                        finishedAt = System.currentTimeMillis(),
                        artifactIds = listOf(artifact.id),
                    )
                },
            )
        }
        updateAgent(task.agent) {
            it.copy(
                busy = false,
                currentTaskId = "",
                progress = 1f,
                tasksDone = it.tasksDone + if (needsApproval) 0 else 1,
                waiting = it.waiting + if (needsApproval) 1 else 0,
                artifacts = it.artifacts + 1,
                lastOutput = text.lineSequence().map { l -> l.trim() }.filter { l -> l.isNotBlank() }.joinToString(" ").take(240),
                message = if (needsApproval) "ждёт твоего одобрения" else "задача закрыта",
            )
        }
        if (needsApproval) {
            emit(task.agent, EventKind.NEED_APPROVAL, "готово «${task.title}» — риск ${task.kind.risk.label}, жду OK (слот ${clockLabel(clock)})")
        } else {
            emit(task.agent, EventKind.OUTPUT, "готово «${task.title}» → ${task.kind.deliverable}")
        }
        container.workspace.appendArtifact(artifact)
    }

    private suspend fun finishShift() {
        update { it.copy(phase = ShiftPhase.REPORTING) }
        emit(null, EventKind.SHIFT_END, "18:00 — подбиваем итоги дня")
        val report = buildReport()
        container.workspace.saveReport(report)
        update { it.copy(phase = ShiftPhase.FINISHED, report = report) }
    }

    private suspend fun buildReport(): ShiftReport {
        val snapshot = _state.value
        val lines = AgentId.ordered.map { agentId ->
            val runtime = snapshot.agent(agentId)
            val tasks = snapshot.tasks.filter { it.agent == agentId }
            val impact = tasks.filter { it.status == TaskStatus.DONE || it.status == TaskStatus.NEEDS_APPROVAL }
                .sumOf { it.kind.impact }
            AgentLine(
                agent = agentId,
                done = runtime.tasksDone,
                waiting = runtime.waiting,
                artifacts = runtime.artifacts,
                score = ((impact / 4.0) * 100).toInt().coerceIn(0, 100),
                highlight = tasks.firstOrNull { it.status != TaskStatus.SKIPPED }?.kind?.title ?: "—",
                tomorrow = nextHint(agentId, snapshot),
            )
        }
        val summary = buildString {
            appendLine("Смена ${snapshot.day}: закрыто ${snapshot.doneTasks} из ${snapshot.plannedTasks} задач, на одобрении ${snapshot.pendingApproval}.")
            appendLine("Материалов подготовлено: ${snapshot.artifacts.size}. В очереди публикации: ${snapshot.publishQueue.size}.")
            appendLine("Публикации агент не делает — только пакеты и напоминания в слоты.")
            val best = lines.maxByOrNull { it.score }
            if (best != null) append("Самый плотный день у «${best.agent.codename}» (оценка ${best.score}). Завтра начни с него: ${best.tomorrow}")
        }.trim()
        return ShiftReport(day = snapshot.day, perAgent = lines, summary = summary, generatedBy = ModelSource.OFFLINE)
    }

    private fun nextHint(agentId: AgentId, snapshot: ShiftSnapshot): String {
        val kinds = snapshot.tasks.filter { it.agent == agentId && it.status == TaskStatus.SKIPPED }
            .map { it.kind }
        return when {
            kinds.isNotEmpty() -> "догнать пропущенное: ${kinds.joinToString(", ") { it.title }}"
            agentId == AgentId.SPARK -> "первый час после публикации: 20 ответов и опрос в комьюнити-посте"
            agentId == AgentId.BOOSTER -> "сверить эксперимент недели и вынести вердикт"
            agentId == AgentId.SCOUT -> "нарезать 4 вертикальных ролика из последнего длинного"
            else -> "проверить CTR вчерашних обложек и добить воронку подписки"
        }
    }

    // ─── примитивы состояния ──────────────────────────────────────────────────

    private suspend fun update(block: (ShiftSnapshot) -> ShiftSnapshot) = mutex.withLock {
        _state.value = block(_state.value)
    }

    private suspend fun mutateTask(taskId: String, block: (AgentTask) -> AgentTask) = mutex.withLock {
        _state.value = _state.value.copy(tasks = _state.value.tasks.map { if (it.id == taskId) block(it) else it })
    }

    private suspend fun updateAgent(agentId: AgentId, block: (AgentRuntime) -> AgentRuntime) = mutex.withLock {
        _state.value = _state.value.copy(agents = _state.value.agents + (agentId to block(_state.value.agent(agentId))))
    }

    private suspend fun emit(agent: AgentId?, kind: EventKind, text: String, taskId: String = "") {
        val clock = clockLabel(_state.value.clock)
        val event = ShiftEvent(System.currentTimeMillis(), clock, agent, kind, text, taskId)
        mutex.withLock { _state.value = _state.value.copy(events = (listOf(event) + _state.value.events).take(200)) }
        container.workspace.appendEvent(event)
    }

    companion object {
        const val SHIFT_START = 9 * 60
        const val SHIFT_END = 18 * 60
        const val TICK_MS = 250L
        const val TICK_MINUTES = 6

        fun clockLabel(totalMinutes: Int): String {
            val m = totalMinutes.coerceIn(0, 24 * 60 - 1)
            return "%02d:%02d".format(m / 60, m % 60)
        }
    }
}

private object ShiftWindowFactory {
    fun of(tag: String, daySeed: Long, start: Int, end: Int) = work.day.app.domain.agent.ShiftWindow(
        tag = tag,
        daySeed = daySeed,
        startMinutes = start.coerceIn(0, 20 * 60),
        endMinutes = end.coerceIn(start + 60, 23 * 60 + 30),
    )
}
