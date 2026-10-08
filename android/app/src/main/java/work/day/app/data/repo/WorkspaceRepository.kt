package work.day.app.data.repo

import java.time.LocalDate
import kotlinx.coroutines.CoroutineScope
import work.day.app.core.PersistedStore
import work.day.app.domain.model.AgentConfig
import work.day.app.domain.model.AgentId
import work.day.app.domain.model.AgentTask
import work.day.app.domain.model.Artifact
import work.day.app.domain.model.ChannelProfile
import work.day.app.domain.model.DailyMetrics
import work.day.app.domain.model.PublishItem
import work.day.app.domain.model.PublishState
import work.day.app.domain.model.ShiftEvent
import work.day.app.domain.engine.ShiftReport
import kotlinx.serialization.Serializable

/** Цели дня/недели — агент отчитывается именно против них. */
@Serializable
data class GrowthGoals(
    val newSubscribersPerWeek: Int = 350,
    val postsPerWeek: Int = 5,
    val retentionPct: Double = 45.0,
    val engagementPct: Double = 6.0,
    val repliesPerDay: Int = 20,
    val responseMinutes: Int = 60,
)

/** Всё рабочее состояние приложения в одном файле. */
@Serializable
data class Workspace(
    val profile: ChannelProfile = ChannelProfile(),
    val agents: List<AgentConfig> = AgentId.ordered.map { AgentConfig(it) },
    val goals: GrowthGoals = GrowthGoals(),
    val tasks: List<AgentTask> = emptyList(),
    val artifacts: List<Artifact> = emptyList(),
    val events: List<ShiftEvent> = emptyList(),
    val queue: List<PublishItem> = emptyList(),
    val reports: List<ShiftReport> = emptyList(),
    val importedMetrics: List<DailyMetrics> = emptyList(),
)

class WorkspaceRepository(
    private val store: PersistedStore<Workspace>,
) {

    val state = store.state
    val profile: ChannelProfile get() = store.value.profile
    val goals: GrowthGoals get() = store.value.goals
    val queue: List<PublishItem> get() = store.value.queue

    fun agentConfig(agent: AgentId): AgentConfig =
        store.value.agents.firstOrNull { it.agent == agent } ?: AgentConfig(agent)

    fun agentConfigs(): List<AgentConfig> =
        AgentId.ordered.map { agent -> agentConfig(agent) }

    fun updateProfile(block: (ChannelProfile) -> ChannelProfile) =
        store.update { it.copy(profile = block(it.profile)) }

    fun updateGoals(block: (GrowthGoals) -> GrowthGoals) =
        store.update { it.copy(goals = block(it.goals)) }

    fun updateAgentConfig(agent: AgentId, block: (AgentConfig) -> AgentConfig) =
        store.update { state ->
            val current = state.agents.firstOrNull { it.agent == agent } ?: AgentConfig(agent)
            val updated = block(current).copy(agent = agent)
            state.copy(
                agents = state.agents.filterNot { it.agent == agent } + updated,
            )
        }

    fun replaceTasks(tasks: List<AgentTask>) =
        store.update { it.copy(tasks = tasks.takeLast(TASK_CAP)) }

    fun appendArtifact(artifact: Artifact) =
        store.update { it.copy(artifacts = (listOf(artifact) + it.artifacts).take(ARTIFACT_CAP)) }

    fun toggleArtifactStar(id: String) =
        store.update { state -> state.copy(artifacts = state.artifacts.map { a -> if (a.id == id) a.copy(starred = !a.starred) else a }) }

    fun appendEvent(event: ShiftEvent) =
        store.update { it.copy(events = (listOf(event) + it.events).take(EVENT_CAP)) }

    fun enqueue(item: PublishItem) =
        store.update { it.copy(queue = (listOf(item) + it.queue).take(QUEUE_CAP)) }

    fun markPublished(id: String) =
        store.update { state -> state.copy(queue = state.queue.map { item -> if (item.id == id) item.copy(state = PublishState.PUBLISHED) else item }) }

    fun dropItem(id: String) =
        store.update { it.copy(queue = it.queue.filterNot { item -> item.id == id }) }

    fun saveReport(report: ShiftReport) =
        store.update { it.copy(reports = (listOf(report) + it.reports).take(REPORT_CAP)) }

    fun importMetrics(rows: List<DailyMetrics>) =
        store.update { it.copy(importedMetrics = (it.importedMetrics + rows).distinctBy { r -> r.date + r.platform.name }.sortedBy { r -> r.date }.takeLast(365)) }

    fun clearMetricsImport() = store.update { it.copy(importedMetrics = emptyList()) }

    /**
     * История для графика роста: сначала то, что реально импортировано (YouTube Data API,
     * CSV из TikTok Analytics), а до этого — синтетические данные демо-режима, чтобы
     * интерфейс имел форму и не выглядел пустым.
     */
    fun metricsDays(days: Int = 60): List<DailyMetrics> {
        val imported = store.value.importedMetrics
        if (imported.size >= days / 2) return imported.takeLast(days)
        val synthetic = SampleMetrics.series(days = (days - imported.size).coerceAtLeast(14), today = LocalDate.now())
        return (synthetic + imported).sortedBy { it.date }.takeLast(days)
    }

    companion object {
        private const val TASK_CAP = 400
        private const val ARTIFACT_CAP = 250
        private const val EVENT_CAP = 600
        private const val QUEUE_CAP = 60
        private const val REPORT_CAP = 30
    }
}
