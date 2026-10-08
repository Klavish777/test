package work.day.app.domain.model

import kotlinx.serialization.Serializable

/** Четыре агента Work Day. Каждый отвечает за одно направление продвижения. */
@Serializable
enum class AgentId(
    val key: String,
    val codename: String,
    val direction: String,
    val mission: String,
    val kpi: String,
    val accent: Long,
    val emoji: String,
) {
    MAGNET(
        key = "magnet", codename = "Магнит", direction = "Прирост аудитории",
        mission = "Превращать показы в подписчиков: находируемость, упаковка, воронка подписки.",
        kpi = "Чистый прирост подписчиков в неделю · CTR обложек · подписчики на 1000 просмотров",
        accent = 0xFF5B5CFF, emoji = "🧲",
    ),
    SCOUT(
        key = "scout", codename = "Разведчик", direction = "Привлечение аудитории",
        mission = "Приводить новых зрителей извне: нарезки, коллаборации, посевы, локализация.",
        kpi = "Охват · доля новой аудитории · переходы Shorts → длинное · внешние источники",
        accent = 0xFF12B886, emoji = "🛰️",
    ),
    BOOSTER(
        key = "booster", codename = "Ускоритель", direction = "Ускорение роста",
        mission = "Находить то, что уже работает, и масштабировать это: эксперименты, ритм, репаковка.",
        kpi = "Скорость роста (неделя к неделе) · удержание · стабильность публикаций",
        accent = 0xFFFF8A3D, emoji = "⚡",
    ),
    SPARK(
        key = "spark", codename = "Искра", direction = "Стимулирование активности",
        mission = "Раскачивать комьюнити, чтобы отклик был в первый час после публикации.",
        kpi = "ER · комментариев на ролик · ответы ≤ 1 часа · сохранения и репосты",
        accent = 0xFFFFD23F, emoji = "✨",
    );

    companion object {
        val ordered: List<AgentId> get() = listOf(MAGNET, SCOUT, BOOSTER, SPARK)
        fun byKey(key: String): AgentId = entries.first { it.key == key }
    }
}
