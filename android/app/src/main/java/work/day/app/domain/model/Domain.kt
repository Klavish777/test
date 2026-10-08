package work.day.app.domain.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Всё, что агенты знают о канале. Из этого они строят план смены. */
@Serializable
data class ChannelProfile(
    val youtubeChannelId: String = "",
    val youtubeTitle: String = "",
    val youtubeSubscribers: Long = 0,
    val tiktokHandle: String = "",
    val tiktokFollowers: Long = 0,
    val niche: String = "",
    val audience: String = "",
    val language: String = "ru",
    val tone: String = "спокойно, по делу, с юмором без иронии над зрителем",
    val keywords: List<String> = emptyList(),
    val cadencePerWeek: Int = 4,
    val publishWindows: List<String> = listOf("Вт 19:00", "Пт 18:30", "Вс 12:00"),
    val bannedWords: List<String> = listOf("успей", "шок", "только не говори"),
) {
    val isConfigured: Boolean get() = youtubeChannelId.isNotBlank() || tiktokHandle.isNotBlank()

    /** Строка контекста для промпта — чем она точнее, тем полезнее выход агента. */
    fun promptContext(): String = buildString {
        appendLine("Ниша: ${niche.ifBlank { "не указана" }}")
        appendLine("Аудитория: ${audience.ifBlank { "не описана" }}")
        appendLine("Язык контента: $language")
        appendLine("Тон автора: $tone")
        if (keywords.isNotEmpty()) appendLine("Ключевые фразы: ${keywords.joinToString(", ")}")
        appendLine("Ритм публикаций: $cadencePerWeek роликов в неделю, слоты: ${publishWindows.joinToString(", ")}")
        if (bannedWords.isNotEmpty()) appendLine("Слова-табу: ${bannedWords.joinToString(", ")}")
        appendLine("YouTube: ${if (youtubeSubscribers > 0) "${youtubeSubscribers} подписчиков" else "не подключен"}")
        appendLine("TikTok: ${if (tiktokFollowers > 0) "${tiktokFollowers} подписчиков" else "не подключен"}")
    }
}

/** Настройка одного агента внутри рабочего дня. */
@Serializable
data class AgentConfig(
    val agent: AgentId,
    val enabled: Boolean = true,
    val autonomy: Autonomy = Autonomy.PREPARE,
    /** 1–5: сколько задач агент берёт в смену и как быстро они множатся. */
    val intensity: Int = 3,
    val enabledPlaybooks: Set<String> = emptySet(),
    val dailyLimit: Int = 12,
    val notes: String = "",
)

@Serializable
data class AgentTask(
    val id: String,
    val agent: AgentId,
    val kind: TaskKind,
    val title: String,
    val target: String,
    val status: TaskStatus = TaskStatus.PLANNED,
    val progress: Float = 0f,
    /** Слот смены в минутах от полуночи. */
    val slotMinutes: Int = 9 * 60,
    val createdAt: Long = 0L,
    val finishedAt: Long = 0L,
    val artifactIds: List<String> = emptyList(),
    val minutesSpent: Int = 0,
    val approvalNote: String = "",
) {
    val requiresApproval: Boolean get() = kind.risk != Risk.LOW
}

@Serializable
data class Artifact(
    val id: String,
    val taskId: String,
    val agent: AgentId,
    val kind: TaskKind,
    val title: String,
    val body: String,
    val platforms: List<Platform>,
    val createdAt: Long,
    val source: ModelSource,
    val starred: Boolean = false,
)

@Serializable
enum class ModelSource(val label: String) {
    @SerialName("remote") REMOTE("Твоя модель"),
    @SerialName("offline") OFFLINE("Офлайн-движок");
}

@Serializable
data class PublishItem(
    val id: String,
    val taskId: String,
    val agent: AgentId,
    val platform: Platform,
    val title: String,
    val body: String,
    val slotMinutes: Int,
    val state: PublishState = PublishState.READY,
)

@Serializable
enum class PublishState(val label: String) {
    @Serializable @kotlinx.serialization.SerialName("ready") READY("Готово к публикации"),
    @Serializable @kotlinx.serialization.SerialName("published") PUBLISHED("Опубликовано вручную"),
    @Serializable @kotlinx.serialization.SerialName("dropped") DROPPED("Отклонено"),
}

@Serializable
data class ShiftEvent(
    val at: Long,
    val clock: String,
    val agent: AgentId?,
    val kind: EventKind,
    val text: String,
    val taskId: String = "",
)

@Serializable
data class DailyMetrics(
    val date: String,
    val platform: Platform,
    val subscribers: Long = 0,
    val views: Long = 0,
    val retentionPct: Double = 0.0,
    val likes: Long = 0,
    val comments: Long = 0,
    val shares: Long = 0,
    val newAudiencePct: Double = 0.0,
    val impressions: Long = 0,
    val ctrPct: Double = 0.0,
) {
    val engagementPct: Double
        get() = if (views <= 0) 0.0 else (likes + comments + shares) * 100.0 / views
}
